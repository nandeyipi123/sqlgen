import json
from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain_community.retrievers import BM25Retriever
from langchain_classic.retrievers import EnsembleRetriever
from config import OLLAMA_BASE_URL, JSON_SCHEMA_PATH, CHROMA_DB_PATH, FEW_SHOT_DB_PATH


# ============================================================
# Schema JSON 缓存 (避免每次检索重复加载 373KB 文件)
# ============================================================
_SCHEMA_CACHE = None


def _load_schema():
    """加载 Schema JSON，模块级缓存"""
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is None:
        with open(JSON_SCHEMA_PATH, 'r', encoding='utf-8') as f:
            _SCHEMA_CACHE = json.load(f)
    return _SCHEMA_CACHE


def get_exact_ddls(table_names_list):
    """
    根据 Planner 规划出的表名集合，去 JSON 里精准提取毫无杂质的 DDL
    返回: (拼装好的上下文字符串, 成功找到的表名列表)
    """
    schema_data = _load_schema()

    exact_docs = []
    found_tables = []

    # 将要找的表名统一转小写，防止大小写匹配失败
    target_tables = list(set(str(t).strip().lower() for t in table_names_list))

    for table in schema_data:
        table_name = table.get("table_name", "").lower()
        if table_name in target_tables:
            found_tables.append(table_name)
            fields = table.get("fields", [])
            content_lines = [f"【表名】: {table_name}", "【字段及枚举说明】:"]
            for field in fields:
                content_lines.append(f"- {field.get('field_name', '')}: {field.get('comment', '')}")
            exact_docs.append("\n".join(content_lines))

    return "\n\n".join(exact_docs), found_tables


def init_ensemble_retriever():
    """初始化混合检索器"""
    # A. 向量检索
    embeddings = OllamaEmbeddings(model="qwen3-embedding:8b", base_url=OLLAMA_BASE_URL)
    vector_store = Chroma(
        collection_name="electric_sql_schema",
        embedding_function=embeddings,
        persist_directory=CHROMA_DB_PATH
    )
    chroma_retriever = vector_store.as_retriever(search_kwargs={"k": 3})

    # B. BM25 关键词检索 (复用缓存的 Schema)
    schema_data = _load_schema()
    documents = []
    for table in schema_data:
        table_name = table.get("table_name", "unknown_table")
        fields = table.get("fields", [])
        content_lines = [f"【表名】: {table_name}", "【字段及枚举说明】:"]
        for field in fields:
            content_lines.append(f"- {field.get('field_name', '')}: {field.get('comment', '')}")
        doc = Document(page_content="\n".join(content_lines), metadata={"table_name": table_name})
        documents.append(doc)

    bm25_retriever = BM25Retriever.from_documents(documents)
    bm25_retriever.k = 2

    # C. 混合检索
    return EnsembleRetriever(retrievers=[chroma_retriever, bm25_retriever], weights=[0.5, 0.5])

def init_few_shot_retriever():
    """初始化历史 SQL 案例检索器（纯相似度 + 表重叠重排序）"""
    embeddings = OllamaEmbeddings(model="qwen3-embedding:8b", base_url=OLLAMA_BASE_URL)
    vector_store = Chroma(
        collection_name="few_shot_sql",
        embedding_function=embeddings,
        persist_directory=FEW_SHOT_DB_PATH
    )
    # 纯相似度检索 20 条候选，后续在 retrieve_and_plan_node 中按表重叠度重排序取前 5
    # 不用 MMR：MMR 追求多样性，会把同场景的相似案例挤掉
    return vector_store.as_retriever(
        search_kwargs={"k": 20}
    )