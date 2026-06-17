"""
Build Vector: 构建向量数据库
============================
位置: buildVector/ (独立训练目录)
输入: buildVector/final_super_schema_by_ai.json + buildVector/few_shot_examples.json
      (从 data/ 训练完成后手动复制过来)
输出: buildVector/schema_chroma_db/ + buildVector/few_shot_chroma_db/
      (手动复制到 app/ 供运行时使用)

架构:
- Schema 向量库: 表结构语义检索 (给 Planner 选表用)
- Few-Shot 向量库: 案例语义检索 (给 Coder 参考用)

文件夹各自独立:
  data/  ──(手动复制JSON)──▶  buildVector/  ──(手动复制DB)──▶  app/
"""

import json
import os
import sys
import shutil
from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings


# ============================================================
# 路径配置 (全部在本文件夹内)
# ============================================================
BUILD_DIR = os.path.dirname(os.path.abspath(__file__))

SCHEMA_JSON = "final_super_schema_by_ai.json"
FEWSHOT_JSON = "few_shot_examples.json"

SCHEMA_DB_NAME = "schema_chroma_db"
FEWSHOT_DB_NAME = "few_shot_chroma_db"

OLLAMA_BASE_URL = "http://127.0.0.1:11434"
EMBEDDING_MODEL = "qwen3-embedding:8b"


# ============================================================
# 数据加载
# ============================================================

def load_json(dir_path: str, filename: str) -> list[dict]:
    path = os.path.join(dir_path, filename)
    if not os.path.exists(path):
        print(f"⚠️ 未找到 {path}")
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


# ============================================================
# Schema → Documents
# ============================================================

def build_schema_documents(schema: list[dict]) -> list[Document]:
    """将增强 Schema 转为 Document 列表"""
    documents = []
    for table in schema:
        table_name = table.get("table_name", "unknown_table")
        fields = table.get("fields", [])

        lines = [f"【表名】: {table_name}", "【字段及枚举说明】:"]
        for f in fields:
            name = f.get("field_name", "")
            comment = f.get("comment", "")
            lines.append(f"- {name}: {comment}")

        doc = Document(
            page_content="\n".join(lines),
            metadata={
                "table_name": table_name,
                "field_count": len(fields)
            }
        )
        documents.append(doc)

    return documents


# ============================================================
# Few-Shot → Documents
# ============================================================

def build_fewshot_documents(few_shots: list[dict]) -> list[Document]:
    """将 Few-Shot 样本转为 Document 列表"""
    documents = []
    for fs in few_shots:
        question = fs.get("question", "")
        business_rules = fs.get("business_rules", "")
        keywords = " ".join(fs.get("search_keywords", []))
        title = fs.get("title", "")

        scenario_tag = fs.get("scenario_tag", "综合查询")

        page_content = (
            f"【查询需求】: {question}\n"
            f"【业务规则】: {business_rules}\n"
            f"【关键词】: {keywords}\n"
            f"【场景】: {scenario_tag}"
        )

        doc = Document(
            page_content=page_content,
            metadata={
                "title": title,
                "question": question,
                "business_rules": business_rules,
                "sql": fs.get("sql", ""),
                "tables_used": json.dumps(fs.get("tables_used", []), ensure_ascii=False),
                "search_keywords": json.dumps(fs.get("search_keywords", []), ensure_ascii=False),
                "complexity": fs.get("complexity", "medium"),
                "scenario_tag": scenario_tag,
            }
        )
        documents.append(doc)

    return documents


# ============================================================
# 构建与验证
# ============================================================

def build_chroma(documents: list[Document], db_path: str,
                 collection_name: str, embeddings: OllamaEmbeddings,
                 label: str) -> Chroma:
    """通用 ChromaDB 构建函数"""
    print(f"🔨 构建 {label} ({len(documents)} 条)...")

    if os.path.exists(db_path):
        shutil.rmtree(db_path)
        print(f"  🗑️  已删除旧库: {db_path}")

    vector_store = Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        collection_name=collection_name,
        persist_directory=db_path
    )

    print(f"  ✅ {label} 已保存至: {db_path}")
    return vector_store


def verify_db(db_path: str, collection_name: str,
              embeddings: OllamaEmbeddings, label: str,
              test_query: str):
    """验证向量库是否正常"""
    if not os.path.exists(db_path):
        print(f"  ⚠️ {label} 库不存在: {db_path}")
        return

    try:
        store = Chroma(
            collection_name=collection_name,
            embedding_function=embeddings,
            persist_directory=db_path
        )
        results = store.similarity_search(test_query, k=3)
        print(f"  ✅ {label} 正常 (检索到 {len(results)} 条)")
        for r in results:
            snippet = r.page_content.replace("\n", " ")[:80]
            print(f"    - {snippet}...")
    except Exception as e:
        print(f"  ❌ {label} 异常: {e}")


# ============================================================
# 主入口
# ============================================================

def main():
    print("=" * 60)
    print("🔨 Build Vector — 构建向量数据库")
    print("=" * 60)
    print(f"  工作目录: {BUILD_DIR}")
    print()

    # 1. 加载数据 (从本文件夹)
    print("📖 加载训练数据...")
    schema = load_json(BUILD_DIR, SCHEMA_JSON)
    few_shots = load_json(BUILD_DIR, FEWSHOT_JSON)

    print(f"  Schema: {len(schema)} 张表")
    print(f"  Few-Shot: {len(few_shots)} 条样本")

    if not schema:
        print("❌ 未找到 final_super_schema_by_ai.json，请先从 data/ 复制过来")
        sys.exit(1)

    # 2. 连接 Ollama
    print(f"\n🔗 连接 Ollama: {OLLAMA_BASE_URL}")
    try:
        embeddings = OllamaEmbeddings(
            model=EMBEDDING_MODEL,
            base_url=OLLAMA_BASE_URL
        )
        _ = embeddings.embed_query("test")
        print("  ✅ Ollama 连接正常")
    except Exception as e:
        print(f"  ❌ Ollama 连接失败: {e}")
        print("  请确保 Ollama 已启动且 qwen3-embedding:8b 模型已安装")
        sys.exit(1)

    # 3. 构建 Schema 向量库
    schema_db_path = os.path.join(BUILD_DIR, SCHEMA_DB_NAME)
    schema_docs = build_schema_documents(schema)
    build_chroma(schema_docs, schema_db_path, "electric_sql_schema",
                 embeddings, "Schema 向量库")

    # 4. 构建 Few-Shot 向量库
    fewshot_db_path = os.path.join(BUILD_DIR, FEWSHOT_DB_NAME)
    if few_shots:
        fewshot_docs = build_fewshot_documents(few_shots)
        build_chroma(fewshot_docs, fewshot_db_path, "few_shot_sql",
                     embeddings, "Few-Shot 向量库")
    else:
        print("⚠️ 无 Few-Shot 数据，跳过")

    # 5. 验证
    print(f"\n🔍 验证向量库...")
    verify_db(schema_db_path, "electric_sql_schema", embeddings,
              "Schema 库", "查询用户信息")
    verify_db(fewshot_db_path, "few_shot_sql", embeddings,
              "Few-Shot 库", "查询电费信息")

    print(f"\n{'=' * 60}")
    print("✅ 全部完成!")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
