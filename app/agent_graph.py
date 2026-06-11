from typing import TypedDict, List, Optional, Literal
import re
import json
from langgraph.graph import StateGraph, END

from retriever import init_ensemble_retriever, init_few_shot_retriever, get_exact_ddls
from agent import get_llm, get_sql_fix_chain, get_planner_chain, get_coder_chain, get_reviewer_chain
from database import extract_and_clean_sql, get_explain_plan
from logger import get_logger

_log = get_logger(__name__)


# ================= 1. 定义简化后的状态 =================
class AgentState(TypedDict):
    question: str
    model_name: str
    temperature: float
    few_shot_context: str
    required_tables: List[str]
    exact_schema_context: str
    found_tables: List[str]
    sql: Optional[str]
    error_msg: Optional[str]
    loop_count: int


# ================= 2. 节点定义 =================
def retrieve_and_plan_node(state: AgentState) -> dict:
    question = state["question"]
    model_name = state.get("model_name", "deepseek-v4-flash")
    temperature = state.get("temperature", 0.1)
    few_shot_retriever = init_few_shot_retriever()
    fs_docs = few_shot_retriever.invoke(question)
    few_shot_context = ""
    for i, doc in enumerate(fs_docs):
        tables = doc.metadata.get('tables_used', '[]')
        few_shot_context += (
            f"\n--- 案例 {i + 1} ---\n"
            f"涉及表: {tables}\n"
            f"业务规则: {doc.metadata.get('business_rules')}\n"
            f"正确SQL: {doc.metadata.get('sql')}\n"
        )

    llm = get_llm(model_name, temperature)
    planner_chain = get_planner_chain(llm)
    planner_response = planner_chain.invoke({"few_shot_context": few_shot_context, "question": question})

    try:
        # 用 JSON 解析：先提取花括号内容，再 json.loads
        json_match = re.search(r"\{.*\}", planner_response, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group(0), strict=False)
            required_tables = parsed.get("tables", [])
        else:
            required_tables = []
    except Exception:
        _log.warning("Planner 输出解析失败，回退到混合检索; 原始响应: %s", planner_response[:200])
        required_tables = []

    exact_schema_context, found_tables = get_exact_ddls(required_tables)
    if not found_tables:
        retriever = init_ensemble_retriever()
        retrieved_docs = retriever.invoke(question)
        exact_schema_context = "\n\n".join([doc.page_content for doc in retrieved_docs])
        found_tables = list(set([doc.metadata.get("table_name") for doc in retrieved_docs]))

    return {
        "few_shot_context": few_shot_context,
        "required_tables": required_tables,
        "exact_schema_context": exact_schema_context,
        "found_tables": found_tables
    }


def coder_node(state: AgentState) -> dict:
    llm = get_llm(state.get("model_name", "deepseek-v4-flash"), state.get("temperature", 0.1))
    coder_chain = get_coder_chain(llm)
    response = coder_chain.invoke({
        "exact_schema_context": state["exact_schema_context"],
        "few_shot_context": state["few_shot_context"],
        "question": state["question"]
    })
    return {"sql": extract_and_clean_sql(response), "loop_count": state.get("loop_count", 0) + 1}


def dba_reviewer_node(state: AgentState) -> dict:
    current_sql = state["sql"]
    if not current_sql:
        return {"error_msg": "未提取到有效SQL"}

    # EXPLAIN 充当完美的无损语法校验器
    explain_plan, explain_err = get_explain_plan(current_sql)
    if explain_err:
        # 如果是语法错误，直接打回
        return {"error_msg": f"数据库直接拒绝，请检查表名、字段和语法：{explain_err}"}

    llm = get_llm(state.get("model_name", "deepseek-v4-flash"), state.get("temperature", 0.1))
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
    llm = get_llm(state.get("model_name", "deepseek-v4-flash"), state.get("temperature", 0.1))
    fix_chain = get_sql_fix_chain(llm)
    response = fix_chain.invoke({
        "exact_schema_context": state["exact_schema_context"],
        "question": state["question"],
        "wrong_sql": state["sql"],
        "error_msg": state["error_msg"]
    })
    return {"sql": extract_and_clean_sql(response), "loop_count": state["loop_count"] + 1}


# ================= 3. 定义流转逻辑 =================
def route_after_review(state: AgentState) -> Literal["fixer", "__end__"]:
    """核心：有错误且未达上限 → Fixer；否则结束"""
    error_msg = state.get("error_msg")

    if error_msg:
        # SYS_ERROR（连接断开/超时）：给 Fixer 一次机会简化 SQL，第二次再放弃
        if "SYS_ERROR" in error_msg and state["loop_count"] >= 1:
            return "__end__"

        # 已达修复上限（3 次）
        if state["loop_count"] >= 3:
            return "__end__"
        return "fixer"

    return "__end__"


# ================= 4. 组装图 =================
workflow = StateGraph(AgentState)

workflow.add_node("retrieve_and_plan", retrieve_and_plan_node)
workflow.add_node("coder", coder_node)
workflow.add_node("dba_reviewer", dba_reviewer_node)
workflow.add_node("fixer", fixer_node)

workflow.set_entry_point("retrieve_and_plan")
workflow.add_edge("retrieve_and_plan", "coder")
workflow.add_edge("coder", "dba_reviewer")

workflow.add_conditional_edges(
    "dba_reviewer",
    route_after_review,
    {
        "fixer": "fixer",
        "__end__": END
    }
)
workflow.add_edge("fixer", "dba_reviewer")

sql_agent_graph = workflow.compile()
