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
import time
from typing import List, Dict, Optional

import pymysql
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
    get_chroma_db_path,
)
from logger import get_logger

_log = get_logger(__name__)


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

def _fetch_table_ddl(table_name: str) -> dict:
    """从数据库下载单张表的字段信息（SHOW CREATE TABLE + 解析）。
    返回 {"table_name": str, "fields": [{"field_name": str, "comment": str}]} 或 None"""
    db = get_current_db_config()
    try:
        conn = pymysql.connect(
            host=db.host, port=db.port, user=db.user,
            password=db.password, database=db.database,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=10, read_timeout=30,
        )
        with conn.cursor() as cursor:
            cursor.execute(f"SHOW CREATE TABLE `{table_name}`")
            result = cursor.fetchone()
        conn.close()

        if not result:
            _log.warning("_fetch_table_ddl: %s 表不存在", table_name)
            return None

        ddl = result.get("Create Table", "")
        fields = []
        for line in ddl.split('\n'):
            line = line.strip()
            if not line or line.startswith('CREATE') or line.startswith(')') or \
               line.startswith('PRIMARY') or line.startswith('KEY') or \
               line.startswith('UNIQUE') or line.startswith('INDEX') or \
               line.startswith('CONSTRAINT') or line.startswith('ENGINE') or \
               line.startswith('/*'):
                continue
            m = re.match(r"`(\w+)`\s+(\w+(?:\([^)]*\))?)\s*(.*)", line)
            if m:
                col_name = m.group(1)
                col_type = m.group(2)
                rest = m.group(3)
                comment = ""
                cm = re.search(r"COMMENT\s+'([^']*)'", rest, re.IGNORECASE)
                if cm:
                    comment = cm.group(1)
                if not comment:
                    comment = f"{col_name} ({col_type})"
                fields.append({"field_name": col_name, "comment": comment})

        _log.info("_fetch_table_ddl: %s 下载成功 (%d 字段)", table_name, len(fields))
        return {"table_name": table_name, "fields": fields}
    except Exception as e:
        _log.warning("_fetch_table_ddl: %s 下载失败: %s", table_name, e)
        return None


def _ensure_schema_tables(tables: List[str]) -> None:
    """检查表是否在 Schema JSON 中，缺失的从数据库下载并缓存到 JSON + ChromaDB"""
    schema_path = get_schema_json_path()
    try:
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema = json.load(f)
    except Exception:
        schema = []

    existing_names = {s.get("table_name", "").lower() for s in schema}
    missing = [t for t in tables if t.lower() not in existing_names]

    if not missing:
        return

    _log.info("_ensure_schema_tables: 发现 %d 张新表，开始下载 DDL: %s", len(missing), missing)

    new_tables = []
    for table_name in missing:
        ddl = _fetch_table_ddl(table_name)
        if ddl:
            schema.append(ddl)
            new_tables.append(ddl)

    if not new_tables:
        return

    # 1. 写入 Schema JSON
    os.makedirs(os.path.dirname(schema_path), exist_ok=True)
    with open(schema_path, 'w', encoding='utf-8') as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)
    _log.info("_ensure_schema_tables: Schema JSON 已更新 (+%d 表)", len(new_tables))

    # 使 retriever 模块级缓存失效
    try:
        import retriever
        retriever._SCHEMA_CACHE = None
    except Exception:
        pass

    # 2. 增量添加到 Schema ChromaDB
    try:
        embeddings = OllamaEmbeddings(model="qwen3-embedding:8b", base_url=OLLAMA_BASE_URL)
        docs = []
        for table in new_tables:
            table_name = table.get("table_name", "unknown")
            fields = table.get("fields", [])
            lines = [f"【表名】: {table_name}", "【字段及枚举说明】:"]
            for f in fields:
                lines.append(f"- {f.get('field_name', '')}: {f.get('comment', '')}")
            docs.append(Document(
                page_content="\n".join(lines),
                metadata={"table_name": table_name, "field_count": len(fields)},
            ))
        store = Chroma(
            collection_name="electric_sql_schema",
            embedding_function=embeddings,
            persist_directory=get_chroma_db_path(),
        )
        store.add_documents(docs)
        _log.info("_ensure_schema_tables: Schema ChromaDB 已更新 (+%d 表)", len(new_tables))
    except Exception as e:
        _log.warning("_ensure_schema_tables: Schema ChromaDB 更新失败: %s（JSON 已保存）", e)


def _build_schema_summary(tables: List[str]) -> str:
    """为指定的表列表构建 Schema 摘要（用作 AI 上下文）。
    如果表不在本地 Schema JSON 中，自动从数据库下载并缓存。"""
    _ensure_schema_tables(tables)

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


def _close_chroma_store(store):
    """主动关闭 ChromaDB 内部连接，释放 Windows 文件锁。"""
    try:
        # langchain_chroma.Chroma 内部持有 chromadb.PersistentClient
        client = getattr(store, '_client', None) or getattr(store, '_chroma_client', None)
        if client is not None:
            # PersistentClient._system 是 DuckDB 的 System 对象
            system = getattr(client, '_system', None)
            if system and hasattr(system, 'stop'):
                system.stop()
    except Exception:
        pass


def _copy_tree_replace(src: str, dst: str):
    """逐文件拷贝 src 内容到 dst（覆盖），用于 Windows 上绕过文件锁。"""
    if not os.path.exists(dst):
        os.makedirs(dst, exist_ok=True)
    for root, dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        target_dir = os.path.join(dst, rel) if rel != '.' else dst
        os.makedirs(target_dir, exist_ok=True)
        for fname in files:
            s = os.path.join(root, fname)
            d = os.path.join(target_dir, fname)
            # 先删除旧文件（忽略锁错误）
            if os.path.exists(d):
                try:
                    os.remove(d)
                except PermissionError:
                    pass  # 旧文件被锁时跳过，新文件直接覆盖写入试试
            shutil.copy2(s, d)


def _publish_train(db_cfg):
    """构建新向量库 + 热替换（由 publish_sync 同步调用）。"""
    try:

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

        store = Chroma.from_documents(
            documents=docs,
            embedding=embeddings,
            collection_name="few_shot_sql",
            persist_directory=new_db_path,
        )
        _log.info("新向量库构建完成: %d 条", len(merged))

        # 释放 ChromaDB 文件锁
        _close_chroma_store(store)
        del store, embeddings, docs
        import gc; gc.collect()
        time.sleep(0.5)  # 给系统一点时间释放文件句柄

        # 3. 文件级拷贝替换（绕过 Windows 目录锁）
        _copy_tree_replace(new_db_path, old_db_path)
        shutil.rmtree(new_db_path, ignore_errors=True)
        _log.info("向量库替换完成")

        # 4. 更新 JSON + 清空暂存区
        _write_json(json_path, merged)
        _write_json(staging_path, [])
        _log.info("热切换完成: 共 %d 条案例", len(merged))
    except Exception as e:
        _log.exception("训练失败")
        raise


def publish_sync() -> tuple:
    """同步执行训练+热切换，返回 (ok: bool, message: str)。
    阻塞约 30 秒，期间前端显示 st.spinner。"""
    db_cfg = get_current_db_config()
    try:
        _publish_train(db_cfg)
        return True, "案例已发布到知识库"
    except Exception as e:
        _log.exception("同步训练失败")
        return False, f"训练失败: {str(e)[:100]}"


def rebuild_sync() -> tuple:
    """同步执行全量重建，返回 (ok: bool, message: str)。"""
    try:
        knowledge_dir = get_current_db_config().knowledge_abs
        json_path = os.path.join(knowledge_dir, "few_shot_examples.json")
        old_db_path = os.path.join(knowledge_dir, "few_shot_chroma_db")
        new_db_path = os.path.join(knowledge_dir, "few_shot_chroma_db_new")

        records = _read_json(json_path)
        _log.info("全量重建: %d 条案例", len(records))

        if os.path.exists(new_db_path):
            shutil.rmtree(new_db_path)

        embeddings = OllamaEmbeddings(model="qwen3-embedding:8b", base_url=OLLAMA_BASE_URL)
        docs = [_build_fewshot_document(r) for r in records]

        store = Chroma.from_documents(
            documents=docs, embedding=embeddings,
            collection_name="few_shot_sql", persist_directory=new_db_path,
        )

        _close_chroma_store(store)
        del store, embeddings, docs
        import gc; gc.collect()
        time.sleep(0.5)

        _copy_tree_replace(new_db_path, old_db_path)
        shutil.rmtree(new_db_path, ignore_errors=True)

        return True, f"向量库已重建: {len(records)} 条案例"
    except Exception as e:
        _log.exception("全量重建失败")
        return False, f"重建失败: {str(e)[:100]}"


def get_few_shot_count() -> int:
    """返回当前正式库案例总数"""
    return len(_read_json(get_few_shot_json_path()))


def direct_import(records: list) -> int:
    """导入案例：只写入 JSON，不去碰向量库。
    训练由侧边栏「训练向量库」按钮单独触发，避免并发写入风险。
    返回新增案例数。"""
    json_path = get_few_shot_json_path()
    existing = _read_json(json_path)

    # 去重
    seen_sigs = set()
    for rec in existing:
        sql = rec.get("sql", "")
        seen_sigs.add(f"{sql[:100].strip().upper()}|{len(sql)}")

    new_records = []
    for rec in records:
        sql = rec.get("sql", "")
        sig = f"{sql[:100].strip().upper()}|{len(sql)}"
        if sig not in seen_sigs:
            existing.append(rec)
            seen_sigs.add(sig)
            new_records.append(rec)

    new_count = len(new_records)
    if new_count == 0:
        _log.info("direct_import: 无新案例（全部重复）")
        return 0

    _write_json(json_path, existing)
    _log.info("direct_import: JSON 已写入 (+%d, 共 %d 条)", new_count, len(existing))
    return new_count


def get_json_count() -> int:
    """返回 JSON 中案例总数"""
    return len(_read_json(get_few_shot_json_path()))


def get_vector_db_count() -> int:
    """返回向量库中已训练文档数"""
    try:
        store = Chroma(
            collection_name="few_shot_sql",
            embedding_function=OllamaEmbeddings(model="qwen3-embedding:8b", base_url=OLLAMA_BASE_URL),
            persist_directory=get_few_shot_db_path(),
        )
        return store._collection.count()
    except Exception as e:
        _log.warning("get_vector_db_count 失败: %s", e)
        return 0


def train_incremental() -> tuple:
    """增量训练：只嵌入向量库中缺失的案例（按 JSON 追加顺序）。
    返回 (trained_count: int, message: str)"""
    json_records = _read_json(get_few_shot_json_path())
    trained_count = get_vector_db_count()
    untrained = json_records[trained_count:]

    if not untrained:
        return 0, "✅ 已是最新版本，无需训练"

    try:
        embeddings = OllamaEmbeddings(model="qwen3-embedding:8b", base_url=OLLAMA_BASE_URL)
        docs = [_build_fewshot_document(r) for r in untrained]
        store = Chroma(
            collection_name="few_shot_sql",
            embedding_function=embeddings,
            persist_directory=get_few_shot_db_path(),
        )
        store.add_documents(docs)
        _log.info("train_incremental: 增量训练 %d 条成功", len(untrained))
        return len(untrained), f"✅ 训练成功，新增 {len(untrained)} 条"
    except Exception as e:
        _log.exception("train_incremental 失败")
        return -1, f"❌ 训练失败: {str(e)[:80]}"
