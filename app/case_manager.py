"""
案例管理模块
===========
处理 SQL 案例的 AI 反向工程、暂存、后台训练发布、向量库热切换。
设计原则：写入与训练分离，新旧知识库无缝切换，不影响其他用户查询。

流程:
  用户粘贴SQL → AI逆向生成 → 逐条确认 → 写入暂存区(staging.json)
  → 用户触发发布 → 后台线程在新目录构建向量库 → os.rename原子替换
"""
import json
import os
import re
import shutil
import threading
import time
from typing import List, Dict, Optional

from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings

from config import (
    OLLAMA_BASE_URL,
    get_current_db_config,
    get_few_shot_json_path,
    get_staging_json_path,
    get_few_shot_db_path,
    get_schema_json_path,
)
from logger import get_logger

_log = get_logger(__name__)

# 发布状态: "idle" | "training" | "done" | "error"
_publish_status = "idle"
_publish_message = ""
_publish_status_lock = threading.Lock()


# ============================================================
# SQL 文本拆分
# ============================================================

def split_sql_text(text: str) -> List[Dict[str, str]]:
    """将粘贴的 SQL 文本拆分为独立语句列表。
    策略: 1) 按 '-- 文件名：' 切分  2) 按 ; 拆分  3) 单条
    返回 [{"title": str, "sql": str}]"""
    text = text.strip()
    if not text:
        return []

    # 策略1: 按 -- 文件名：切分
    if re.search(r'--\s*文件名[：:]', text):
        blocks = []
        parts = re.split(r'--\s*文件名[：:]\s*', text)
        for part in parts:
            part = part.strip()
            if not part:
                continue
            lines = part.split('\n')
            title = lines[0].strip().rstrip('.sql')
            sql_lines = []
            for line in lines[1:]:
                stripped = line.strip()
                if stripped.startswith('====') or stripped.startswith('==='):
                    continue
                sql_lines.append(line)
            sql_text_block = '\n'.join(sql_lines).strip()
            if sql_text_block:
                blocks.append({"title": title, "sql": sql_text_block})
        if blocks:
            return blocks

    # 策略2: 按 ; 拆分
    parts = [p.strip() for p in text.split(';') if p.strip()]
    if len(parts) > 1:
        result = []
        for i, p in enumerate(parts):
            if len(p) > 20:
                # 尝试从 SQL 注释中提取标题
                title_match = re.search(r'--\s*(.+)', p)
                title = title_match.group(1).strip()[:40] if title_match else f"SQL_{i+1}"
                result.append({"title": title, "sql": p})
        if result:
            return result

    # 策略3: 单条
    title_match = re.search(r'--\s*(.+)', text)
    title = title_match.group(1).strip()[:40] if title_match else "手动导入"
    return [{"title": title, "sql": text}]


def _extract_tables_from_sql(sql: str) -> List[str]:
    """从 SQL 中提取表名（简单正则，覆盖 FROM/JOIN）"""
    tables = set()
    for pattern in [r'\bFROM\s+`?(\w[\w.]*)`?', r'\bJOIN\s+`?(\w[\w.]*)`?']:
        for m in re.findall(pattern, sql, re.IGNORECASE):
            tbl = m.split('.')[-1].strip('`').lower()
            if tbl not in ('select', 'where', 'on', 'as', 'and', 'or', 'limit'):
                tables.add(tbl)
    return sorted(tables)


# ============================================================
# AI 反向工程
# ============================================================

def _build_schema_summary(tables: List[str]) -> str:
    """为指定的表列表构建 Schema 摘要（用作 AI 上下文）"""
    schema_path = get_schema_json_path()
    try:
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema = json.load(f)
    except Exception:
        return "(Schema 文件未找到)"

    schema_index = {s.get("table_name", "").lower(): s for s in schema}
    summaries = []
    for table_name in tables:
        s = schema_index.get(table_name.lower())
        if s:
            fields = s.get("fields", [])
            meaningful = [f for f in fields if f.get("comment") and len(f.get("comment", "")) > 3]
            field_lines = []
            for f in meaningful[:20]:
                comment = f["comment"][:80]
                field_lines.append(f"    {f['field_name']}: {comment}")
            summaries.append(f"【{table_name}】:\n" + "\n".join(field_lines))
        else:
            summaries.append(f"【{table_name}】: (无 Schema 信息)")
    return "\n\n".join(summaries)


def reverse_engineer_sql(sql_item: dict) -> dict:
    """调用 DeepSeek API 反向生成 question/business_rules/search_keywords/complexity"""
    from agent import get_llm_no_stream

    sql = sql_item["sql"]
    title = sql_item.get("title", "手动导入")
    tables = _extract_tables_from_sql(sql)
    schema_summary = _build_schema_summary(tables)

    prompt = f"""你是深谙电网业务的数据架构师。请对以下 SQL 进行"反向工程"，生成高质量的 Few-Shot 样本。

【SQL 标题】: {title}
【涉及的表】: {', '.join(tables) if tables else '(未识别)'}

【数据库表结构参考】:
{schema_summary}

【SQL 代码】:
{sql}

【任务】:
1. 推测业务人员最初问的自然语言问题 (question) — 要包含具体的筛选条件、字段名
2. 提炼业务规则 (business_rules) — 表关联逻辑、枚举值翻译、特殊计算逻辑
3. 提取检索关键词 (search_keywords) — 5~10个最能描述此查询的词语
4. 评估复杂度 (complexity): simple / medium / complex

【输出格式】:
严格 JSON（不要 markdown 代码块）:
{{
  "question": "自然语言问题",
  "business_rules": "1. 规则一。2. 规则二。...",
  "search_keywords": ["关键词1", "关键词2", ...],
  "complexity": "simple|medium|complex"
}}"""

    try:
        llm = get_llm_no_stream("deepseek-v4-flash", 0.1)
        response = llm.invoke(prompt)
        raw = response.content if hasattr(response, 'content') else str(response)
        # 提取 JSON
        raw = re.sub(r'```\w*\s*', '', raw).strip()
        result = json.loads(raw)
    except Exception as e:
        _log.warning("AI 反向工程失败: %s，使用降级方案", e)
        result = {
            "question": title,
            "business_rules": "",
            "search_keywords": [],
            "complexity": "medium",
        }

    result["sql"] = sql
    result["title"] = title
    result["tables_used"] = tables
    return result


# ============================================================
# 暂存区操作
# ============================================================

def _read_json(path: str) -> list:
    """安全读取 JSON 数组"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _write_json(path: str, data: list):
    """安全写入 JSON 数组"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def stage_case(record: dict) -> bool:
    """将确认的案例写入暂存区（极快，不阻塞）。
    按 SQL 签名去重（前 100 字符 + 长度）。"""
    staging_path = get_staging_json_path()
    existing = _read_json(staging_path)

    sql = record.get("sql", "")
    sig = f"{sql[:100].strip().upper()}|{len(sql)}"
    for ex in existing:
        ex_sql = ex.get("sql", "")
        if f"{ex_sql[:100].strip().upper()}|{len(ex_sql)}" == sig:
            _log.info("暂存区去重: 案例已存在，跳过")
            return False

    existing.append(record)
    _write_json(staging_path, existing)
    _log.info("案例已暂存: %s (%d chars)", record.get("title", ""), len(sql))
    return True


def get_staging_count() -> int:
    """返回暂存区案例数量"""
    return len(_read_json(get_staging_json_path()))


def get_staging_cases() -> list:
    """读取暂存区全部案例"""
    return _read_json(get_staging_json_path())


# ============================================================
# 后台训练 + 热切换
# ============================================================

def _build_fewshot_document(record: dict) -> Document:
    """将案例记录转为 ChromaDB Document"""
    question = record.get("question", "")
    business_rules = record.get("business_rules", "")
    keywords = " ".join(record.get("search_keywords", []))
    scenario_tag = record.get("scenario_tag", "综合查询")

    page_content = (
        f"【查询需求】: {question}\n"
        f"【业务规则】: {business_rules}\n"
        f"【关键词】: {keywords}\n"
        f"【场景】: {scenario_tag}"
    )

    return Document(
        page_content=page_content,
        metadata={
            "title": record.get("title", ""),
            "question": question,
            "business_rules": business_rules,
            "sql": record.get("sql", ""),
            "tables_used": json.dumps(record.get("tables_used", []), ensure_ascii=False),
            "search_keywords": json.dumps(record.get("search_keywords", []), ensure_ascii=False),
            "complexity": record.get("complexity", "medium"),
            "scenario_tag": scenario_tag,
        }
    )


def _publish_train(db_cfg):
    """后台线程：构建新向量库 + 原子替换。
    注意：此函数在后台线程中运行，不访问 Streamlit session_state。"""
    global _publish_status, _publish_message

    try:
        with _publish_status_lock:
            _publish_status = "training"
            _publish_message = ""

        knowledge_dir = db_cfg.knowledge_abs
        staging_path = os.path.join(knowledge_dir, "few_shot_examples_staging.json")
        json_path = os.path.join(knowledge_dir, "few_shot_examples.json")
        old_db_path = os.path.join(knowledge_dir, "few_shot_chroma_db")
        new_db_path = os.path.join(knowledge_dir, "few_shot_chroma_db_new")
        old_backup_path = os.path.join(knowledge_dir, "few_shot_chroma_db_old")

        # 1. 合并正式库 + 暂存区
        existing = _read_json(json_path)
        staging = _read_json(staging_path)

        _log.info("后台训练: 正式库 %d 条 + 暂存区 %d 条", len(existing), len(staging))

        # 去重
        seen_sigs = set()
        merged = []
        for rec in existing + staging:
            sql = rec.get("sql", "")
            sig = f"{sql[:100].strip().upper()}|{len(sql)}"
            if sig not in seen_sigs:
                seen_sigs.add(sig)
                merged.append(rec)

        new_count = len(merged) - len(existing)
        _log.info("合并后: %d 条 (%+d 新案例)", len(merged), new_count)

        # 2. 构建新向量库
        if os.path.exists(new_db_path):
            shutil.rmtree(new_db_path)

        embeddings = OllamaEmbeddings(model="qwen3-embedding:8b", base_url=OLLAMA_BASE_URL)
        docs = [_build_fewshot_document(r) for r in merged]

        Chroma.from_documents(
            documents=docs,
            embedding=embeddings,
            collection_name="few_shot_sql",
            persist_directory=new_db_path,
        )
        _log.info("新向量库构建完成: %d 条", len(docs))

        # 3. 原子替换
        # 3a. 备份旧库
        if os.path.exists(old_db_path):
            if os.path.exists(old_backup_path):
                shutil.rmtree(old_backup_path)
            os.rename(old_db_path, old_backup_path)

        # 3b. 新库上线
        os.rename(new_db_path, old_db_path)

        # 3c. 更新 JSON
        _write_json(json_path, merged)

        # 3d. 清空暂存区
        _write_json(staging_path, [])

        # 3e. 清理旧备份
        if os.path.exists(old_backup_path):
            shutil.rmtree(old_backup_path)

        with _publish_status_lock:
            _publish_status = "done"
            _publish_message = f"发布完成: +{new_count} 条新案例已生效 (共 {len(merged)} 条)"

        _log.info("热切换完成: 共 %d 条案例", len(merged))

    except Exception as e:
        _log.exception("后台训练失败")
        with _publish_status_lock:
            _publish_status = "error"
            _publish_message = f"训练失败: {str(e)[:100]}"


def publish_in_background():
    """启动后台线程执行训练+热切换。非阻塞，立即返回。"""
    global _publish_status
    with _publish_status_lock:
        if _publish_status == "training":
            return  # 已在训练中

    db_cfg = get_current_db_config()
    _log.info("启动后台训练: %s", db_cfg.name)
    t = threading.Thread(target=_publish_train, args=(db_cfg,), daemon=True)
    t.start()


def get_publish_status() -> tuple:
    """返回 (status: str, message: str)
    status: "idle" | "training" | "done" | "error"
    """
    global _publish_status, _publish_message
    with _publish_status_lock:
        status = _publish_status
        msg = _publish_message
    return status, msg


def reset_publish_status():
    """将状态从 done/error 重置为 idle（前端消费通知后调用）"""
    global _publish_status, _publish_message
    with _publish_status_lock:
        if _publish_status in ("done", "error"):
            _publish_status = "idle"
            _publish_message = ""


def rebuild_vector_store_from_json():
    """从 JSON 全量重建向量库（容灾按钮，也走后台线程）"""
    global _publish_status

    def _rebuild():
        global _publish_status, _publish_message
        try:
            with _publish_status_lock:
                _publish_status = "training"
                _publish_message = ""

            knowledge_dir = get_current_db_config().knowledge_abs
            json_path = os.path.join(knowledge_dir, "few_shot_examples.json")
            old_db_path = os.path.join(knowledge_dir, "few_shot_chroma_db")
            new_db_path = os.path.join(knowledge_dir, "few_shot_chroma_db_new")
            old_backup_path = os.path.join(knowledge_dir, "few_shot_chroma_db_old")

            records = _read_json(json_path)
            _log.info("全量重建: %d 条案例", len(records))

            if os.path.exists(new_db_path):
                shutil.rmtree(new_db_path)

            embeddings = OllamaEmbeddings(model="qwen3-embedding:8b", base_url=OLLAMA_BASE_URL)
            docs = [_build_fewshot_document(r) for r in records]

            Chroma.from_documents(
                documents=docs,
                embedding=embeddings,
                collection_name="few_shot_sql",
                persist_directory=new_db_path,
            )

            if os.path.exists(old_db_path):
                if os.path.exists(old_backup_path):
                    shutil.rmtree(old_backup_path)
                os.rename(old_db_path, old_backup_path)
            os.rename(new_db_path, old_db_path)
            if os.path.exists(old_backup_path):
                shutil.rmtree(old_backup_path)

            with _publish_status_lock:
                _publish_status = "done"
                _publish_message = f"向量库已重建: {len(records)} 条案例"

        except Exception as e:
            _log.exception("全量重建失败")
            with _publish_status_lock:
                _publish_status = "error"
                _publish_message = f"重建失败: {str(e)[:100]}"

    with _publish_status_lock:
        if _publish_status == "training":
            return

    t = threading.Thread(target=_rebuild, daemon=True)
    t.start()


def get_few_shot_count() -> int:
    """返回当前正式库案例总数"""
    return len(_read_json(get_few_shot_json_path()))
