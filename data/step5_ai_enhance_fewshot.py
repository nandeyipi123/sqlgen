"""
Step 5: AI 增强 Few-Shot 样本
==============================
输入: parsed_sqls.json + final_super_schema_by_ai.json
输出: few_shot_examples.json

与旧流程的区别:
- 旧: 仅从 SQL 反向推测 question + business_rules
- 新: 有增强 Schema 做上下文，AI 能更准确地理解 SQL 中的表结构和枚举值含义
- 新增字段: tables_used (涉及的表), keywords (检索关键词), complexity (复杂度)
"""

import json
import os
import sys
import time
from dotenv import load_dotenv
from openai import OpenAI


def load_inputs(data_dir: str) -> tuple[list[dict], list[dict]]:
    """加载 parsed_sqls 和 final_super_schema"""
    sql_path = os.path.join(data_dir, "parsed_sqls.json")
    schema_path = os.path.join(data_dir, "final_super_schema_by_ai.json")

    with open(sql_path, 'r', encoding='utf-8') as f:
        parsed_sqls = json.load(f)

    with open(schema_path, 'r', encoding='utf-8') as f:
        schema = json.load(f)

    return parsed_sqls, schema


def build_schema_summary(schema: list[dict], tables: list[str]) -> str:
    """为指定的表列表构建 Schema 摘要（用作 AI 上下文）"""
    schema_index = {s["table_name"]: s for s in schema}

    summaries = []
    for table_name in tables:
        if table_name in schema_index:
            s = schema_index[table_name]
            fields = s.get("fields", [])
            # 只取有意义的字段（有注释的）
            meaningful_fields = [f for f in fields if f.get("comment") and len(f["comment"]) > 5]
            field_lines = []
            for f in meaningful_fields[:20]:  # 最多20个字段
                comment = f["comment"][:80]  # 截断长注释
                field_lines.append(f"    {f['field_name']}: {comment}")
            summaries.append(f"【{table_name}】:\n" + "\n".join(field_lines))
        else:
            summaries.append(f"【{table_name}】: (无 Schema 信息)")

    return "\n\n".join(summaries)


def deduplicate_sqls(parsed_sqls: list[dict]) -> list[dict]:
    """去重：移除 SQL 高度相似的条目"""
    seen_signatures = set()
    unique = []

    for item in parsed_sqls:
        # 生成签名：前100个字符 + 长度
        sql = item.get("sql", "")
        sig = f"{sql[:100].strip().upper()}|{len(sql)}"

        if sig not in seen_signatures:
            seen_signatures.add(sig)
            unique.append(item)

    return unique


def build_fewshot_prompt(sql_item: dict, schema_summary: str, index: int, total: int) -> str:
    """构建单条 Few-Shot 生成的 AI prompt"""
    sql = sql_item.get("sql", "")
    title = sql_item.get("title", "未知查询")
    tables = sql_item.get("tables", [])
    keywords = sql_item.get("keywords", [])

    prompt = f"""你是深谙电网业务的数据架构师。请对以下 SQL 进行"反向工程"，生成高质量的 Few-Shot 样本。

【SQL 标题】: {title}
【涉及的表】: {', '.join(tables) if tables else '(未识别)'}
【从列别名提取的关键词】: {', '.join(keywords) if keywords else '(无)'}

【数据库表结构参考】:
{schema_summary}

【SQL 代码】:
{sql}

【任务】:
1. 推测业务人员最初问的自然语言问题 (question) — 要包含具体的筛选条件、字段名
2. 提炼业务规则 (business_rules) — 表关联逻辑、枚举值翻译、状态码含义、特殊计算逻辑
3. 提取检索关键词 (search_keywords) — 5~10个最能描述此查询的词语，用于向量检索匹配
4. 评估复杂度 (complexity): simple / medium / complex

【输出格式】:
严格 JSON（不要 markdown 代码块）:
{{
  "question": "自然语言问题",
  "business_rules": "1. 规则一。2. 规则二。...",
  "search_keywords": ["关键词1", "关键词2", ...],
  "complexity": "simple|medium|complex",
  "sql": "原封不动的原始 SQL"
}}"""

    return prompt


def generate_few_shot(client: OpenAI, sql_items: list[dict], schema: list[dict],
                      delay: float = 1.5, output_file: str = "few_shot_examples.json") -> list[dict]:
    """逐条生成 Few-Shot 样本"""
    few_shots = []
    total = len(sql_items)

    for i, item in enumerate(sql_items):
        title = item.get("title", f"SQL_{i+1}")
        tables = item.get("tables", [])
        sql = item.get("sql", "")

        # 跳过太短的 SQL
        if len(sql) < 30:
            print(f"  [{i + 1}/{total}] ⏭️ 跳过 {title} (SQL 太短: {len(sql)} chars)")
            continue

        print(f"  [{i + 1}/{total}] 🔄 分析 {title} ...", end=" ")

        schema_summary = build_schema_summary(schema, tables)
        prompt = build_fewshot_prompt(item, schema_summary, i + 1, total)

        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是一个深谙电网业务的数据架构师。请严格按照 JSON 格式输出，不要输出任何多余文字。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )

            ai_response = response.choices[0].message.content.strip()
            parsed = json.loads(ai_response, strict=False)

            # 强制保留原始 SQL
            parsed["sql"] = sql
            parsed["title"] = title
            parsed["tables_used"] = tables

            few_shots.append(parsed)
            print(f"✅ (问题: {parsed.get('question', '')[:40]}...)")

            # 实时保存
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(few_shots, f, ensure_ascii=False, indent=2)

        except json.JSONDecodeError as e:
            print(f"⚠️ JSON 解析失败: {e}")
            # 降级：用基本信息构建
            fallback = {
                "question": title,
                "business_rules": "",
                "search_keywords": item.get("keywords", []),
                "complexity": "medium",
                "sql": sql,
                "title": title,
                "tables_used": tables
            }
            few_shots.append(fallback)

        except Exception as e:
            print(f"❌ 失败: {e}")

        time.sleep(delay)

    return few_shots


def run_fewshot_generation(data_dir: str, top_n: int = None):
    """主流程"""
    # 加载环境变量
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'data', '.env'))
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'app', '.env'))
        api_key = os.getenv("DEEPSEEK_API_KEY")

    if not api_key:
        print("❌ 未找到 DEEPSEEK_API_KEY")
        sys.exit(1)

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    # 加载数据
    parsed_sqls, schema = load_inputs(data_dir)
    print(f"📖 加载了 {len(parsed_sqls)} 条 SQL 和 {len(schema)} 张表 Schema")

    # 去重
    unique_sqls = deduplicate_sqls(parsed_sqls)
    print(f"📊 去重后: {len(unique_sqls)} 条 (减少了 {len(parsed_sqls) - len(unique_sqls)} 条)")

    # 按复杂度/长度排序，优先处理有代表性的 SQL
    unique_sqls.sort(key=lambda x: len(x.get("sql", "")), reverse=True)

    # 可选：限制数量
    if top_n:
        unique_sqls = unique_sqls[:top_n]
        print(f"📊 限制处理前 {top_n} 条")

    # 生成
    output_file = os.path.join(data_dir, "few_shot_examples.json")
    print(f"\n⏳ 开始生成 Few-Shot 样本 ({len(unique_sqls)} 条)...\n")

    few_shots = generate_few_shot(client, unique_sqls, schema, output_file=output_file)

    # 最终保存
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(few_shots, f, ensure_ascii=False, indent=2)

    # 统计
    complexities = {}
    for fs in few_shots:
        c = fs.get("complexity", "unknown")
        complexities[c] = complexities.get(c, 0) + 1

    print(f"\n🎉 完成! 生成 {len(few_shots)} 条 Few-Shot 样本")
    print(f"📊 复杂度分布: {complexities}")
    print(f"💾 已保存至: {output_file}")

    return few_shots


if __name__ == "__main__":
    data_dir = os.path.dirname(os.path.abspath(__file__))

    # 检查前置依赖
    schema_path = os.path.join(data_dir, "final_super_schema_by_ai.json")
    if not os.path.exists(schema_path):
        print(f"⚠️ 未找到 {schema_path}，将使用无 Schema 模式生成")
        print(f"   建议先运行 step4_ai_enhance_schema.py")

    run_fewshot_generation(data_dir)
