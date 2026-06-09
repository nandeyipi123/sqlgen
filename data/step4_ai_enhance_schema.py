"""
Step 4: AI 增强 Schema（核心重构步骤）
======================================
输入: raw_ddl.json + field_value_mappings.json
输出: final_super_schema_by_ai.json

与旧流程的本质区别:
- 旧: auto_field_map.json 暴力映射 → AI 被迫纠错
- 新: 真实 SQL 提取的映射 + DDL 原始注释 → AI 做"融合"而非"纠错"

AI 的融合规则:
1. 如果 DDL 中字段的 COMMENT 已包含枚举值说明，且与 SQL 提取的一致 → 保持
2. 如果 DDL COMMENT 中没有枚举值，但从 SQL 中提取到了 → 追加到 comment
3. 如果 DDL COMMENT 与 SQL 提取的冲突 → 以 DDL 为准（因为 DDL 是官方定义）
4. 新增字段：从 SQL 中发现的字段（DDL 中可能没有包含的）
"""

import json
import os
import sys
import time
from dotenv import load_dotenv
from openai import OpenAI


def load_inputs(data_dir: str) -> tuple[list[dict], list[dict]]:
    """加载 raw_ddl 和 field_value_mappings"""
    ddl_path = os.path.join(data_dir, "raw_ddl.json")
    mapping_path = os.path.join(data_dir, "field_value_mappings.json")

    with open(ddl_path, 'r', encoding='utf-8') as f:
        ddls = json.load(f)

    with open(mapping_path, 'r', encoding='utf-8') as f:
        mappings = json.load(f)

    return ddls, mappings


def prepare_table_context(ddl_info: dict, mappings: dict) -> dict:
    """
    为每张表准备 AI 输入上下文
    返回: {table_name, ddl_columns, sql_extracted_fields}
    """
    table_name = ddl_info["table_name"]

    # DDL 列信息
    ddl_columns = ddl_info.get("columns", [])

    # SQL 提取的映射（可能为空）
    sql_fields = mappings.get(table_name, {}).get("fields", [])

    return {
        "table_name": table_name,
        "ddl_columns": ddl_columns,
        "sql_extracted_fields": sql_fields
    }


def build_ai_prompt(table_context: dict) -> str:
    """
    构建 AI 增强的 prompt
    核心: 告诉 AI 如何融合两种来源的信息
    """
    table_name = table_context["table_name"]
    ddl_columns = table_context["ddl_columns"]
    sql_fields = table_context["sql_extracted_fields"]

    # 构建 DDL 部分
    ddl_lines = []
    for col in ddl_columns:
        ddl_lines.append(
            f"  - {col['field_name']} ({col['type']}): {col['comment'] or '(无注释)'}"
        )

    # 构建 SQL 提取部分
    sql_lines = []
    for field in sql_fields:
        code_types = field.get("code_types", [])
        hardcoded = field.get("hardcoded_values", {})
        source = field.get("source", "")
        parts = [f"  - {field['field_name']}:"]
        if code_types:
            parts.append(f"关联字典: {', '.join(code_types)}")
        if hardcoded:
            enum_parts = [f"{k}={v}" for k, v in list(hardcoded.items())[:10]]
            parts.append(f"SQL中硬编码枚举值: {{{', '.join(enum_parts)}}}")
        parts.append(f"(来源: {source})")
        sql_lines.append(" ".join(parts))

    prompt = f"""你是电网营销数据库架构师。请为表 `{table_name}` 生成增强版的字段定义。

【DDL 原始列定义】:
{chr(10).join(ddl_lines) if ddl_lines else '(无 DDL 信息)'}

【从真实 SQL 中提取的字段值映射】:
{chr(10).join(sql_lines) if sql_lines else '(无 SQL 提取数据)'}

【融合规则 (严格遵守)】:
1. DDL 的 COMMENT 是权威来源，如果 COMMENT 已包含枚举值说明，不要修改它
2. 如果 COMMENT 中没有枚举值，但从 SQL 中提取到了硬编码枚举值 → 追加到 comment 中，格式: "[原注释] 枚举值: 01=设立, 02=在用, ..."
3. 如果 COMMENT 中提到了"引用国家电网...代码类集:XXXX"，保留原文，并在后面追加 SQL 中实际使用的值作为参考
4. 如果 SQL 中有 m_p_code 关联（code_type），但不清楚具体枚举值 → 在 comment 中标注: "[原注释] 字典类型: code_type_name"
5. 不要自己编造枚举值！只使用 SQL 中提取到的或者 DDL 注释中已有的
6. 如果一个字段在多个 code_type 中出现，全部列出

【输出格式】:
只输出该表的 JSON（不含 markdown 代码块标记）:
{{
  "table_name": "{table_name}",
  "fields": [
    {{
      "field_name": "列名",
      "comment": "增强后的注释"
    }}
  ]
}}"""

    return prompt


def ai_enhance_table(client: OpenAI, table_context: dict, model: str = "deepseek-chat") -> dict:
    """调用 AI 增强单张表"""
    prompt = build_ai_prompt(table_context)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一个严谨的电网数据库架构师。只输出要求的 JSON 格式，不输出任何多余文本。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
        )

        ai_response = response.choices[0].message.content.strip()

        # 解析 JSON
        if ai_response.startswith('```json'):
            ai_response = ai_response[7:-3]
        elif ai_response.startswith('```'):
            ai_response = ai_response[3:-3]

        return json.loads(ai_response, strict=False)

    except json.JSONDecodeError as e:
        print(f"  ⚠️ JSON 解析失败: {e}")
        print(f"  AI 原始返回: {ai_response[:200]}...")
        # 降级：返回原始 DDL 列
        return {
            "table_name": table_context["table_name"],
            "fields": [
                {"field_name": col["field_name"], "comment": col["comment"] or ""}
                for col in table_context["ddl_columns"]
            ]
        }
    except Exception as e:
        print(f"  ❌ API 调用失败: {e}")
        return None


def run_enhancement(data_dir: str, batch_size: int = 5, delay: float = 1.0):
    """
    主流程：逐表调用 AI 增强

    参数:
    - batch_size: 每批处理的表数（打印进度用）
    - delay: 每张表之间的延迟（秒），防止 API 限流
    """
    # 加载环境变量
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'data', '.env'))
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'app', '.env'))
        api_key = os.getenv("DEEPSEEK_API_KEY")

    if not api_key:
        print("❌ 未找到 DEEPSEEK_API_KEY，请检查 .env 文件")
        sys.exit(1)

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    # 加载数据
    ddls, mappings = load_inputs(data_dir)
    print(f"📖 加载了 {len(ddls)} 张表的 DDL 和 {len(mappings)} 张表的字段映射")

    # 构建映射索引
    mapping_index = {m["table_name"]: m for m in mappings}

    final_schema = []
    ok_count = 0
    fail_count = 0
    total = len(ddls)

    for i, ddl_info in enumerate(ddls):
        table_name = ddl_info["table_name"]

        # 跳过没有成功获取 DDL 的表
        if ddl_info["status"] != "ok":
            print(f"  [{i + 1}/{total}] ⏭️ 跳过 {table_name} (DDL 状态: {ddl_info['status']})")
            continue

        print(f"  [{i + 1}/{total}] 🔄 增强 {table_name} ...", end=" ")

        # 准备上下文
        mapping = mapping_index.get(table_name, {"fields": []})
        context = prepare_table_context(ddl_info, mapping)

        # 调用 AI
        enhanced = ai_enhance_table(client, context)

        if enhanced:
            final_schema.append(enhanced)
            ok_count += 1
            field_count = len(enhanced.get("fields", []))
            print(f"✅ ({field_count} 字段)")
        else:
            # 降级：使用原始 DDL
            fallback = {
                "table_name": table_name,
                "fields": [
                    {"field_name": col["field_name"], "comment": col["comment"] or ""}
                    for col in ddl_info.get("columns", [])
                ]
            }
            final_schema.append(fallback)
            fail_count += 1
            print(f"⚠️ 降级使用原始 DDL")

        # 防限流延迟
        time.sleep(delay)

        # 每 10 张表保存一次中间结果
        if (i + 1) % 10 == 0:
            tmp_file = os.path.join(data_dir, "final_super_schema_by_ai.tmp.json")
            with open(tmp_file, 'w', encoding='utf-8') as f:
                json.dump(final_schema, f, ensure_ascii=False, indent=2)
            print(f"  💾 已保存中间结果 ({len(final_schema)} 张表)")

    # 保存最终结果
    output_file = os.path.join(data_dir, "final_super_schema_by_ai.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(final_schema, f, ensure_ascii=False, indent=2)

    print(f"\n📊 完成: {ok_count} 成功, {fail_count} 降级")
    print(f"💾 已保存至: {output_file}")

    return final_schema


if __name__ == "__main__":
    data_dir = os.path.dirname(os.path.abspath(__file__))
    run_enhancement(data_dir)
