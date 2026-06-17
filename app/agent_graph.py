from typing import TypedDict, List, Optional, Literal
import re
import json
import os
from concurrent.futures import ThreadPoolExecutor
from langgraph.graph import StateGraph, END

from retriever import init_ensemble_retriever, init_few_shot_retriever, get_exact_ddls
from agent import get_llm, get_llm_no_stream, get_sql_fix_chain, get_planner_chain, get_coder_chain, get_reviewer_chain, get_schema_linker_chain, get_table_discovery_chain
from database import extract_and_clean_sql, get_explain_plan
from domain_validator import validate, format_validation_message
from logger import get_logger

_log = get_logger(__name__)


# ============================================================
# 模块级缓存：同义词词典 & 表关系知识库
# ============================================================
_SYNONYMS_CACHE = None
_TABLE_KNOWLEDGE_CACHE = None


def _load_synonyms():
    """加载同义词词典（运行时查询扩展用）"""
    global _SYNONYMS_CACHE
    if _SYNONYMS_CACHE is None:
        try:
            synonyms_path = os.path.join(os.path.dirname(__file__), "..", "data", "domain_synonyms.json")
            with open(synonyms_path, 'r', encoding='utf-8') as f:
                _SYNONYMS_CACHE = json.load(f)
            _log.info("同义词词典已加载: %d 组", len([k for k in _SYNONYMS_CACHE if not k.startswith('_')]))
        except Exception as e:
            _log.warning("同义词词典加载失败: %s", e)
            _SYNONYMS_CACHE = {}
    return _SYNONYMS_CACHE


def _load_table_knowledge():
    """加载表关系领域知识库"""
    global _TABLE_KNOWLEDGE_CACHE
    if _TABLE_KNOWLEDGE_CACHE is None:
        try:
            knowledge_path = os.path.join(os.path.dirname(__file__), "..", "data", "table_relationships.json")
            with open(knowledge_path, 'r', encoding='utf-8') as f:
                _TABLE_KNOWLEDGE_CACHE = json.load(f)
            tables = [k for k in _TABLE_KNOWLEDGE_CACHE if not k.startswith('_')]
            _log.info("表关系知识库已加载: %d 张表", len(tables))
        except Exception as e:
            _log.warning("表关系知识库加载失败: %s", e)
            _TABLE_KNOWLEDGE_CACHE = {}
    return _TABLE_KNOWLEDGE_CACHE


def expand_query(question: str) -> str:
    """运行时查询扩展：匹配同义词并追加到查询字符串，提高检索命中率"""
    synonyms = _load_synonyms()
    expanded_terms = []

    for root_term, variants in synonyms.items():
        if root_term.startswith('_'):
            continue
        # 检查用户问题是否包含该组任一词汇
        all_terms = [root_term] + list(variants)
        matched = any(term in question for term in all_terms)
        if matched:
            # 追加该组中不在原问题中的词汇
            new_terms = [t for t in all_terms if t not in question]
            expanded_terms.extend(new_terms)

    if expanded_terms:
        expanded = question + " " + " ".join(expanded_terms)
        _log.info("查询扩展: +%d 个词 → %s", len(expanded_terms),
                  expanded[:120] + "..." if len(expanded) > 120 else expanded)
        return expanded
    return question


# ================= 1. 定义状态（新增 domain_knowledge_context） =================
class AgentState(TypedDict):
    question: str
    model_name: str
    temperature: float
    few_shot_context: str
    required_tables: List[str]
    exact_schema_context: str
    domain_knowledge_context: str
    found_tables: List[str]
    sql: Optional[str]
    sql_candidates: List[str]             # 候选 SQL（coder 生成 2 个）
    error_msg: Optional[str]
    warnings: List[str]                   # 非致命警告（API 降级等），展示给用户
    loop_count: int


# ================= 2. 节点定义 =================

def _build_table_list() -> str:
    """构建全部可用表清单（表名 + 一句话描述），供 LLM 表发现用"""
    from retriever import _load_schema
    schema = _load_schema()
    lines = []
    for t in schema:
        name = t.get("table_name", "")
        # 取第一个字段的注释作为表描述
        fields = t.get("fields", [])
        desc = fields[0].get("comment", "")[:60] if fields else ""
        lines.append(f"  {name} — {desc}")
    return "\n".join(lines)


# 模块级缓存表清单
_TABLE_LIST_CACHE = None


def _get_table_list() -> str:
    global _TABLE_LIST_CACHE
    if _TABLE_LIST_CACHE is None:
        _TABLE_LIST_CACHE = _build_table_list()
    return _TABLE_LIST_CACHE


def _discover_tables(question: str) -> tuple:
    """LLM 表发现：从问题直接推理需要的表，补充 few-shot 检索可能遗漏的表。
    返回 (tables: list, error_msg: str) — error_msg 为空表示成功。"""
    try:
        llm = get_llm("deepseek-v4-flash", 0.0)
        chain = get_table_discovery_chain(llm)
        raw = chain.invoke({"question": question, "table_list": _get_table_list()})
        raw = re.sub(r'```\w*\s*', '', raw).strip()
        tables = json.loads(raw)
        if isinstance(tables, list) and tables:
            _log.info("LLM 表发现: +%d 张表 → %s", len(tables), tables)
            return tables, ""
    except Exception as e:
        _log.warning("LLM 表发现失败: %s", e)
    return [], "LLM 表发现失败（DeepSeek API 连接异常），已跳过，可能遗漏部分表"


# ============================================================
# 查询 → 场景匹配（用于 few-shot 检索的场景加权）
# ============================================================
_QUERY_SCENE_KEYWORDS = [
    ("月电费查询", ["月电费", "电费明细", "电费汇总", "应收", "电费统计", "月度",
                    "rcvbl_ym", "应收电费", "实收电费", "欠费"]),
    ("收费明细", ["收费明细", "收费台账", "逐笔", "收款记录", "缴费记录", "到账"]),
    ("电量查询", ["电量", "抄表", "表底", "有功", "峰平谷", "分时电量", "峰谷",
                  "有功总", "有功峰", "有功平", "有功谷", "read_type"]),
    ("电价查询", ["电价", "目录电价", "峰谷电价", "分时电价", "电价策略"]),
    ("用户档案", ["用户信息", "用户档案", "客户资料", "联系电话", "电话号码",
                  "证件", "身份证"]),
    ("计量点查询", ["计量点", "计费点", "受电点", "mp"]),
    ("采集点查询", ["采集", "终端", "集抄", "采集点"]),
    ("线损统计", ["线损", "线损率"]),
    ("发票票据", ["发票", "票据", "票据类型"]),
    ("台区管理", ["台区", "变压器"]),
    ("发电管理", ["发电", "光伏", "新能源"]),
    ("合同管理", ["合同", "协议", "业扩"]),
]


def _guess_query_scene(question: str) -> str:
    """根据用户问题关键词映射到场景标签"""
    for tag, keywords in _QUERY_SCENE_KEYWORDS:
        if any(kw in question for kw in keywords):
            return tag
    return "综合查询"


# ============================================================
# 关键词 → 表补充（问题包含特定关键词时，自动补充关键表）
# ============================================================
_KEYWORD_TABLE_HINTS = {
    '联系电话': ['m_c_cust'],
    '电话': ['m_c_cust'],
    '手机': ['m_c_cust'],
    '联系方式': ['m_c_cust'],
    '联系人': ['m_c_cust'],
    '信用代码': ['m_c_cust'],
    '身份证': ['m_c_cert', 'm_c_cons_cert_rela'],
    '证件': ['m_c_cert', 'm_c_cons_cert_rela'],
    '票据类型': ['m_a_inv'],
    '发票': ['m_a_inv'],
    '两保户': ['m_c_cont_info'],
    '五保户': ['m_c_cont_info'],
    '低保户': ['m_c_cont_info'],
    '低保': ['m_c_cont_info'],
    '五保': ['m_c_cont_info'],
    '两保': ['m_c_cont_info'],
}

# ============================================================
# 场景硬过滤：命中场景关键词 + 未命中放行关键词 → 排除
# ============================================================
_SCENE_TABLE_FILTER = [
    # 月电费/汇总场景：不应出现逐笔收费明细表
    (['月电费', '电费明细', '电费汇总', '电费统计', '月汇总', '月度电费', '欠费'],
     ['m_a_rcved_flow'],
     ['收费明细', '收费台账', '逐笔', '收款记录', '缴费记录', '缴费明细']),
    # 非电价查询场景：不应出现电价目录表
    (['月电费', '电费明细', '欠费', '用户'],
     ['m_e_cat_prc'],
     ['电价', '目录电价', '峰谷电价', '分时电价', '电价策略', '电价目录']),
    # 非电价明细场景：不应出现电价电费明细表
    (['月电费', '欠费'],
     ['m_e_cons_prc_amt_arc'],
     ['电价目录', '峰谷', '分时', '电价明细', '按电价']),
]


def _hint_tables_by_keywords(question: str, tables: list) -> list:
    """根据问题关键词自动补充缺失的关键表（如"联系电话"→m_c_cust）"""
    added = []
    tables_lower = [t.lower() for t in tables]
    for keyword, hint_tables in _KEYWORD_TABLE_HINTS.items():
        if keyword in question:
            for ht in hint_tables:
                if ht.lower() not in tables_lower:
                    tables.append(ht)
                    tables_lower.append(ht.lower())
                    added.append(ht)
    if added:
        _log.info("关键词表补充: +%d 张表 → %s", len(added), added)
    return tables


def _filter_tables_by_scene(question: str, tables: list) -> list:
    """根据问题场景硬过滤不应出现的表（如月电费场景排除 m_a_rcved_flow）"""
    removed = []
    for scene_keywords, exclude_tables, allow_keywords in _SCENE_TABLE_FILTER:
        scene_hit = any(kw in question for kw in scene_keywords)
        if not scene_hit:
            continue
        allow_hit = any(kw in question for kw in allow_keywords)
        if allow_hit:
            continue
        for et in exclude_tables:
            for t in list(tables):
                if t.lower() == et.lower():
                    tables.remove(t)
                    removed.append(t)
    if removed:
        _log.info("场景硬过滤: -%d 张表 → %s", len(removed), removed)
    return tables


def retrieve_and_plan_node(state: AgentState) -> dict:
    """检索案例 → 合并表名 → LLM 表发现补充 → 取 DDL"""
    question = state["question"]
    few_shot_retriever = init_few_shot_retriever()

    # 运行时查询扩展：匹配同义词提高召回率
    expanded_query = expand_query(question)
    fs_docs = few_shot_retriever.invoke(expanded_query)

    # ---- 0. 先算全局表频次（20 条候选），用于重排序 ----
    global_table_freq = {}
    for doc in fs_docs:
        try:
            for t in json.loads(doc.metadata.get("tables_used", "[]")):
                global_table_freq[t] = global_table_freq.get(t, 0) + 1
        except Exception:
            pass

    # ---- 0.5 表重叠度重排序 + 场景加权 ----
    query_scene = _guess_query_scene(question)  # 问题→场景映射

    def _doc_score(doc):
        try:
            tables = json.loads(doc.metadata.get("tables_used", "[]"))
            base_score = sum(global_table_freq.get(t, 0) for t in tables)
            # 同场景案例 +30% 加权
            doc_scene = doc.metadata.get("scenario_tag", "")
            scene_bonus = 1.3 if doc_scene == query_scene else 1.0
            return base_score * scene_bonus
        except Exception:
            return 0

    fs_docs = sorted(fs_docs, key=_doc_score, reverse=True)[:5]
    _log.info("查询场景=%s, 检索top5场景=%s",
              query_scene,
              [d.metadata.get("scenario_tag","?") for d in fs_docs])

    # 1. 拼 few_shot_context + 统计表频次（只算重排序后的 5 条）
    few_shot_context = ""
    table_freq = {}
    case_tables = []
    for i, doc in enumerate(fs_docs):
        tables_str = doc.metadata.get("tables_used", "[]")
        few_shot_context += (
            f"\n--- 案例 {i + 1} ---\n"
            f"涉及表: {tables_str}\n"
            f"业务规则: {doc.metadata.get('business_rules')}\n"
            f"正确SQL: {doc.metadata.get('sql')}\n"
        )
        try:
            tables = json.loads(tables_str)
        except Exception:
            tables = []
        case_tables.append(tables)
        for t in tables:
            table_freq[t] = table_freq.get(t, 0) + 1

    # 2. 合并表名: 全部案例统一规则——只收出现≥2次的（不再给案例1特权）
    required_tables = []
    for tables in case_tables:
        for t in tables:
            if t not in required_tables and table_freq.get(t, 0) >= 2:
                required_tables.append(t)

    _log.info("检索合并: %d 案例 → %d 张表 (出现≥2次, 频次: %s)",
              len(fs_docs), len(required_tables),
              {t: table_freq.get(t, 0) for t in required_tables})

    # 2.5a 关键词表补充（如"联系电话"→ m_c_cust）
    required_tables = _hint_tables_by_keywords(question, required_tables)

    # 2.5b 场景硬过滤（如月电费场景排除 m_a_rcved_flow）
    required_tables = _filter_tables_by_scene(question, required_tables)

    # 3. LLM 表发现：补充 few-shot 遗漏的表
    discovered, discover_err = _discover_tables(question)
    required_lower = [t.lower() for t in required_tables]
    for t in discovered:
        if t.lower() not in required_lower:
            required_tables.append(t)
            required_lower.append(t.lower())
    if discovered:
        _log.info("表发现合并后: %d 张表", len(required_tables))

    # 3.5 场景硬过滤（LLM 补充后再次过滤不该出现的表）
    required_tables = _filter_tables_by_scene(question, required_tables)

    # 4. 精准取 DDL（先去重，防止 LLM 表发现或案例合并引入重复表名）
    required_tables = list(dict.fromkeys(required_tables))  # 保序去重
    exact_schema_context, found_tables = get_exact_ddls(required_tables)

    # 5. 兜底：合并后表太少 → 混合检索补充
    if len(found_tables) < 3:
        _log.info("表太少(%d)，触发混合检索补充", len(found_tables))
        retriever = init_ensemble_retriever()
        retrieved_docs = retriever.invoke(question)
        exact_schema_context = "\n\n".join([doc.page_content for doc in retrieved_docs])
        found_tables = list(set([doc.metadata.get("table_name") for doc in retrieved_docs]))

    return {
        "few_shot_context": few_shot_context,
        "required_tables": required_tables,
        "exact_schema_context": exact_schema_context,
        "found_tables": found_tables,
        "warnings": [discover_err] if discover_err else []
    }


# 表关联扩展规则：当检测到关键表时，自动补充桥梁表的 DDL
_TABLE_BRIDGE_EXPANSION = {
    'm_r_coll_obj': ['m_c_sp', 'm_c_meter_mp_rela', 'm_c_meter', 'm_r_cp'],
    'm_r_cp': ['m_r_coll_obj', 'm_c_meter', 'm_c_meter_mp_rela', 'm_c_mp', 'm_c_sp'],
    'm_c_meter': ['m_c_meter_mp_rela', 'm_c_mp', 'm_c_sp'],
    'm_c_meter_mp_rela': ['m_c_mp', 'm_c_sp'],
}


# ============================================================
# Schema Linking 辅助函数：DDL 列裁剪
# ============================================================

def _parse_ddl_to_summary(ddl_text: str) -> dict:
    """将格式化的 DDL 文本解析为 {表名: {字段名: 注释}}"""
    result = {}
    current_table = None
    for line in ddl_text.split('\n'):
        line = line.strip()
        if line.startswith('【表名】:'):
            current_table = line.split(':', 1)[1].strip()
            result[current_table] = {}
        elif line.startswith('- ') and current_table:
            # 格式: "- field_name: comment"
            parts = line[2:].split(':', 1)
            if len(parts) == 2:
                result[current_table][parts[0].strip()] = parts[1].strip()
    return result


def _build_schema_summary(ddl_text: str) -> str:
    """构建精简的表→字段摘要，供 Schema Linker LLM 快速扫描"""
    parsed = _parse_ddl_to_summary(ddl_text)
    lines = []
    for tbl, cols in parsed.items():
        lines.append(f"【{tbl}】({len(cols)} 字段)")
        for col, comment in cols.items():
            # 截断过长注释
            short = comment[:60] + "..." if len(comment) > 60 else comment
            lines.append(f"  - {col}: {short}")
    return "\n".join(lines)


def _filter_ddl_text(ddl_text: str, column_map: dict) -> str:
    """根据 column_map 裁剪 DDL 文本，只保留相关字段"""
    parsed = _parse_ddl_to_summary(ddl_text)
    parts = []
    for tbl, keep_cols in column_map.items():
        if tbl not in parsed or not keep_cols:
            continue
        keep_set = {c.lower() for c in keep_cols}
        lines = [f"【表名】: {tbl}", "【字段及枚举说明】:"]
        for col, comment in parsed[tbl].items():
            if col.lower() in keep_set:
                lines.append(f"- {col}: {comment}")
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def _run_schema_linking(question: str, ddl_text: str, model_name: str = "deepseek-v4-flash") -> tuple:
    """调用 LLM 做列级 Schema Linking，返回 (column_map: dict, error_msg: str)。
    error_msg 为空 = 成功；非空 = 失败，调用方应回退到完整 DDL。"""
    summary = _build_schema_summary(ddl_text)
    if not summary:
        return {}, ""

    llm = get_llm(model_name, 0.0)
    linker_chain = get_schema_linker_chain(llm)
    try:
        raw = linker_chain.invoke({"question": question, "schema_summary": summary})
        raw = re.sub(r'```\w*\s*', '', raw).strip()
        result = json.loads(raw)
        if isinstance(result, dict):
            _log.info("Schema Linking: %d 张表 → %d 个字段被保留",
                      len(_parse_ddl_to_summary(ddl_text)),
                      sum(len(v) for v in result.values()))
            return result, ""
    except Exception as e:
        _log.warning("Schema Linking 失败，回退到完整 DDL: %s", e)
    return {}, "Schema Linking 失败（DeepSeek API 连接异常），已回退到完整 DDL（token 消耗会更大）"


def schema_augment_node(state: AgentState) -> dict:
    """表扩展 + 领域知识注入 + Schema Linking 列裁剪"""
    required_tables = state.get("required_tables", [])
    knowledge = _load_table_knowledge()
    question = state["question"]

    # ---- 1. 表扩展：补充缺失的桥梁表 DDL ----
    required_lower = [t.lower() for t in required_tables]
    expanded_tables = list(required_tables)
    extra_schema_parts = []

    for key, bridge_tables in _TABLE_BRIDGE_EXPANSION.items():
        if key in required_lower:
            for bt in bridge_tables:
                if bt.lower() not in required_lower:
                    bt_schema, bt_found = get_exact_ddls([bt])
                    if bt_found:
                        expanded_tables.append(bt)
                        required_lower.append(bt.lower())
                        extra_schema_parts.append(bt_schema)
                        _log.info("表扩展: %s 触发了桥梁表 %s 的自动加载", key, bt)

    expanded_schema = state.get("exact_schema_context", "")
    if extra_schema_parts:
        expanded_schema = expanded_schema + "\n\n" + "\n\n".join(extra_schema_parts)

    # ---- 2. 领域知识注入 ----
    domain_context = ""
    if knowledge:
        context_parts = []
        matched_count = 0

        for tbl in required_tables:
            tbl_lower = tbl.lower()
            for key, info in knowledge.items():
                if key.startswith('_'):
                    continue
                if tbl_lower in key.lower() or key.lower() in tbl_lower:
                    if tbl_lower not in [c.split('|')[0] for c in context_parts]:
                        lines = [f"\n### {key} — {info.get('business_role', '')}"]
                        principles = info.get('key_principles', [])
                        if principles:
                            lines.append("  【关键原则】")
                            for p in principles:
                                lines.append(f"    • {p}")
                        anti = info.get('anti_patterns', [])
                        if anti:
                            lines.append("  【常见错误（禁止）】")
                            for a in anti:
                                lines.append(f"    ✗ {a.get('mistake', '')} — {a.get('why_wrong', '')}")
                        context_parts.append(f"{tbl_lower}|" + "\n".join(lines))
                        matched_count += 1
                    break

        domain_context = "\n".join([p.split('|', 1)[1] for p in context_parts])
        if matched_count > 0:
            _log.info("领域知识注入: %d/%d 张表匹配到领域知识",
                      matched_count, len(required_tables))

    # ---- 3. Schema Linking：列级裁剪 ----
    # 仅当表数 ≥ 4 或 DDL 总量较大时才做（少量表时裁剪收益低）
    link_warning = ""
    if len(expanded_tables) >= 4:
        column_map, link_warning = _run_schema_linking(question, expanded_schema)
        if column_map:
            filtered_schema = _filter_ddl_text(expanded_schema, column_map)
            if filtered_schema:
                # 确保 bridges 扩展的表也被包含（它们可能在 filtered_schema 外）
                for bt_schema in extra_schema_parts:
                    if bt_schema not in filtered_schema:
                        filtered_schema += "\n\n" + bt_schema
                expanded_schema = filtered_schema
                _log.info("Schema Linking 完成: DDL 已裁剪")

    # 合并前置节点的 warnings
    prev_warnings = state.get("warnings", [])
    if link_warning:
        prev_warnings.append(link_warning)

    return {
        "domain_knowledge_context": domain_context,
        "exact_schema_context": expanded_schema,
        "warnings": prev_warnings
    }


def coder_node(state: AgentState) -> dict:
    """生成 2 个候选 SQL：
    - 候选A: 低温（保守，严格跟案例1）
    - 候选B: 中温（更灵活，可能找到更好的 JOIN 路径）"""
    model_name = state.get("model_name", "deepseek-v4-flash")

    # 自动追加字典翻译
    question = state["question"]
    auto_suffix = "。字典翻译为中文名称"
    if "字典翻译" not in question and "翻译为中文" not in question:
        question = question.rstrip("。，,. ") + auto_suffix

    ctx = {
        "exact_schema_context": state["exact_schema_context"],
        "few_shot_context": state["few_shot_context"],
        "domain_knowledge_context": state.get("domain_knowledge_context", ""),
        "question": question
    }

    # 并行生成 2 个候选 SQL，减少一半等待时间
    def _gen_candidate(temperature: float, label: str):
        """生成单个候选 SQL"""
        try:
            llm = get_llm_no_stream(model_name, temperature)
            raw = get_coder_chain(llm).invoke(ctx)
            return extract_and_clean_sql(raw), None, label
        except Exception as e:
            _log.warning("Coder 候选%s 生成失败: %s", label, e)
            return None, f"⚠️ Coder 候选{label} 生成失败（API 连接异常），已跳过: {str(e)[:80]}", label

    candidates = []
    coder_warnings = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(_gen_candidate, 0.0, 'A'),
            pool.submit(_gen_candidate, 0.3, 'B'),
        ]
        for f in futures:
            sql, err, label = f.result()
            if err:
                coder_warnings.append(err)
            elif sql:
                candidates.append(sql)
                _log.info("Coder 候选%s(%s): %d 字符", label, model_name, len(sql))

    if not any(c for c in candidates if c):
        # 两个候选都失败 → 无法继续
        return {
            "sql_candidates": [],
            "error_msg": f"Coder 两个候选均生成失败（DeepSeek API 连接异常），请稍后重试。",
            "loop_count": state.get("loop_count", 0) + 1
        }

    _log.info("Coder 生成了 %d 个候选 SQL", len([c for c in candidates if c]))
    result = {
        "sql_candidates": candidates,
        "loop_count": state.get("loop_count", 0) + 1
    }
    if coder_warnings:
        prev_warnings = state.get("warnings", [])
        result["warnings"] = prev_warnings + coder_warnings
    return result


def candidate_select_node(state: AgentState) -> dict:
    """验证 2 个候选 SQL 的领域正确性，选最优进入后续流程"""
    candidates = [c for c in state.get("sql_candidates", []) if c]
    question = state["question"]
    tables = state.get("required_tables", [])

    if not candidates:
        return {"error_msg": "Coder 未生成任何有效 SQL 候选", "sql": None}

    # 逐个验证
    results = []
    for sql in candidates:
        r = validate(sql, question, tables)
        results.append(r)
        status = "PASS" if r["passed"] else f"{len(r['errors'])}E/{len(r['warnings'])}W"
        _log.info("候选验证: %s (%d 字段)", status, len(sql))

    # 评分：PASS > 仅WARN > 最少ERROR
    def score(idx):
        r = results[idx]
        if not r: return -999
        if r["passed"]: return 100 - len(r.get("warnings", []))
        return 0 - len(r.get("errors", []))

    scores = [score(i) for i in range(len(results))]
    best_idx = scores.index(max(scores))
    winner = candidates[best_idx]
    winner_result = results[best_idx]

    _log.info("候选选择: 候选%d 胜出 (score=%d)", best_idx + 1, scores[best_idx])

    if not winner_result["passed"]:
        domain_msg = format_validation_message(winner_result)
        return {
            "sql": winner,
            "error_msg": f"领域规则校验不通过：\n{domain_msg}"
        }

    # 记录 warnings
    if winner_result.get("warnings"):
        _log.info("候选选择: %d 个 warnings", len(winner_result["warnings"]))

    return {"sql": winner, "error_msg": None}


def domain_validator_node(state: AgentState) -> dict:
    """领域规则校验（不调 LLM，纯规则匹配 ~5ms）"""
    current_sql = state["sql"]
    if not current_sql:
        return {"error_msg": "未提取到有效SQL，无法进行领域校验"}

    result = validate(
        sql=current_sql,
        question=state["question"],
        tables=state.get("required_tables", [])
    )

    if not result["passed"]:
        # 领域规则错误 → 格式化后送入 Fixer
        domain_msg = format_validation_message(result)
        _log.info("领域规则拦截: %d errors, %d warnings",
                  len(result["errors"]), len(result["warnings"]))
        return {"error_msg": f"领域规则校验不通过：\n{domain_msg}"}

    # 通过 → 记录 warnings（如果有）供 UI 展示
    if result["warnings"]:
        _log.info("领域规则提醒: %d warnings", len(result["warnings"]))

    return {"error_msg": None}


def dba_reviewer_node(state: AgentState) -> dict:
    current_sql = state["sql"]
    if not current_sql:
        return {"error_msg": "未提取到有效SQL"}

    # EXPLAIN 充当完美的无损语法校验器
    explain_plan, explain_err = get_explain_plan(current_sql)
    if explain_err:
        # 如果是语法错误，直接打回
        return {"error_msg": f"数据库直接拒绝，请检查表名、字段和语法：{explain_err}"}

    llm = get_llm_no_stream(state.get("model_name", "deepseek-v4-flash"), state.get("temperature", 0.1))
    reviewer_chain = get_reviewer_chain(llm)
    reviewer_response = reviewer_chain.invoke({"sql": current_sql, "explain_plan": explain_plan})

    try:
        # 稳健清除 markdown 代码块标记 (```json ... ``` 或 ``` ... ```)
        clean = re.sub(r'```[\w]*\s*', '', reviewer_response).strip()
        review_result = json.loads(clean, strict=False)
    except Exception:
        _log.warning("Reviewer JSON 解析失败，默认 FAIL; 原始响应: %s", reviewer_response[:300])
        review_result = {"status": "FAIL", "reason": "Reviewer 响应格式异常，无法解析审查结果", "suggestion": "请检查 SQL 语法和表结构"}

    if review_result.get("status") == "FAIL":
        return {"error_msg": f"性能审查失败！原因：{review_result.get('reason')}。建议：{review_result.get('suggestion')}"}
    return {"error_msg": None}


def fixer_node(state: AgentState) -> dict:
    llm = get_llm_no_stream(state.get("model_name", "deepseek-v4-flash"), state.get("temperature", 0.1))
    fix_chain = get_sql_fix_chain(llm)
    response = fix_chain.invoke({
        "exact_schema_context": state["exact_schema_context"],
        "domain_knowledge_context": state.get("domain_knowledge_context", ""),
        "few_shot_context": state["few_shot_context"],
        "question": state["question"],
        "wrong_sql": state["sql"],
        "error_msg": state["error_msg"]
    })
    return {"sql": extract_and_clean_sql(response), "loop_count": state["loop_count"] + 1}


# ================= 3. 定义流转逻辑 =================
# 注意：Fixer 已停用。所有错误路径直接走 dba_reviewer 或 END，不再重试修复。
# 需要重新启用时：取消注释下面的路由，恢复 fixer→domain_validator 边即可。

def route_after_select(state: AgentState) -> Literal["fixer", "dba_reviewer"]:
    """候选选择后：有问题直接进 DBA Review（不再走 Fixer）"""
    # Fixer 已停用：所有路径返回 dba_reviewer
    return "dba_reviewer"


def route_after_validator(state: AgentState) -> Literal["fixer", "dba_reviewer"]:
    """领域校验 → 直接进 DBA Review（不再走 Fixer）"""
    return "dba_reviewer"


def route_after_review(state: AgentState) -> Literal["fixer", "__end__"]:
    """DBA 审查 → 有错误直接结束（不再走 Fixer）"""
    return "__end__"


# ================= 4. 组装图 =================
workflow = StateGraph(AgentState)

workflow.add_node("retrieve_and_plan", retrieve_and_plan_node)
workflow.add_node("schema_augment", schema_augment_node)
workflow.add_node("coder", coder_node)
workflow.add_node("candidate_select", candidate_select_node)   # ← 新增
workflow.add_node("domain_validator", domain_validator_node)   # Fixer 循环内用
workflow.add_node("dba_reviewer", dba_reviewer_node)
workflow.add_node("fixer", fixer_node)

workflow.set_entry_point("retrieve_and_plan")
workflow.add_edge("retrieve_and_plan", "schema_augment")
workflow.add_edge("schema_augment", "coder")
workflow.add_edge("coder", "candidate_select")                 # ← 新边

# 候选选择 → Fixer 或 DBA Review
workflow.add_conditional_edges(
    "candidate_select",
    route_after_select,
    {"fixer": "fixer", "dba_reviewer": "dba_reviewer"}
)

# 领域校验（Fixer 循环内）→ Fixer 或 DBA Review
workflow.add_conditional_edges(
    "domain_validator",
    route_after_validator,
    {"fixer": "fixer", "dba_reviewer": "dba_reviewer"}
)

# DBA Review → Fixer 或 END
workflow.add_conditional_edges(
    "dba_reviewer",
    route_after_review,
    {"fixer": "fixer", "__end__": END}
)

# Fixer 已停用（2026-06-24）。重新启用时取消下行注释：
# workflow.add_edge("fixer", "domain_validator")

sql_agent_graph = workflow.compile()
