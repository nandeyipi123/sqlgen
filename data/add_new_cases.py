"""
增量追加新案例
==============
当你有新的 SQL 案例需要加入知识库时，用这个脚本增量追加，
不需要重跑全部 6 个步骤。

支持三种输入方式:
  方式A: 新的 SQL 文件 (--sql-file)
  方式B: 直接把 SQL 追加到 data/合并.sql 末尾 (--from-merged-sql)
  方式C: 命令行直接输入 SQL (--sql "SELECT ...")

工作流程:
  1. 解析新 SQL → 追加到 parsed_sqls.json
  2. 提取新的字段映射 → 合并到 field_value_mappings.json
  3. 检查是否有新表 → 提示是否需要重下 DDL
  4. AI 反向工程新案例 → 追加到 few_shot_examples.json
  5. (可选) 重建向量库

Usage:
  # 从新的 SQL 文件添加
  python add_new_cases.py --sql-file "../data/新案例.sql"

  # 合并.sql 末尾有了新案例，增量解析
  python add_new_cases.py --from-merged-sql

  # 直接输入 SQL
  python add_new_cases.py --sql "select ... from m_c_cons ..." --title "新查询"

  # 只做离线解析，不调 AI
  python add_new_cases.py --sql-file "新案例.sql" --skip-ai

  # 添加后自动重建向量库
  python add_new_cases.py --sql-file "新案例.sql" --build-vectors
"""

import json
import os
import sys
import argparse
import re
import time
from dotenv import load_dotenv
from openai import OpenAI

# 导入 step1 的解析函数
sys.path.insert(0, os.path.dirname(__file__))
from step1_parse_sqls import (
    parse_sql_file, split_sql_blocks, split_statements,
    extract_tables, extract_m_p_code_mappings, extract_case_when_mappings,
    extract_aliases, clean_sql
)
from step2_extract_mappings import (
    extract_field_code_type_mapping, extract_hardcoded_enum_mappings,
    merge_mappings, normalize_code_type
)

DATA_DIR = os.path.dirname(os.path.abspath(__file__))


# ============================================================
# 1. 加载现有数据
# ============================================================

def load_json(filename):
    path = os.path.join(DATA_DIR, filename)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def save_json(data, filename):
    path = os.path.join(DATA_DIR, filename)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  💾 已保存: {filename}")


# ============================================================
# 2. 解析新 SQL
# ============================================================

def parse_new_sqls(sql_text: str, title: str = None) -> list[dict]:
    """解析新的 SQL 文本，返回与 step1 相同格式的列表"""
    cleaned = clean_sql(sql_text)
    statements = split_statements(cleaned)
    select_stmts = [s for s in statements if s.upper().strip().startswith('SELECT')]

    if not select_stmts:
        select_stmts = [cleaned] if cleaned else []

    results = []
    for stmt in select_stmts:
        if len(stmt) < 20:
            continue

        results.append({
            "title": title or "手动添加",
            "sql": stmt,
            "tables": extract_tables(stmt),
            "m_p_code_mappings": extract_m_p_code_mappings(stmt),
            "case_when_mappings": extract_case_when_mappings(stmt),
            "keywords": extract_aliases(stmt)
        })

    return results


def append_to_parsed_sqls(new_entries: list[dict]):
    """将新条目追加到 parsed_sqls.json（自动去重）"""
    existing = load_json("parsed_sqls.json") or []

    # 去重：用 SQL 前 100 字符的签名判断
    existing_sigs = set()
    for e in existing:
        sig = f"{e['sql'][:100].strip().upper()}|{len(e['sql'])}"
        existing_sigs.add(sig)

    added = 0
    for entry in new_entries:
        sig = f"{entry['sql'][:100].strip().upper()}|{len(entry['sql'])}"
        if sig not in existing_sigs:
            existing.append(entry)
            existing_sigs.add(sig)
            added += 1

    save_json(existing, "parsed_sqls.json")
    print(f"  ✅ parsed_sqls.json: 新增 {added} 条 (总共 {len(existing)} 条)")

    return existing


# ============================================================
# 3. 更新字段映射
# ============================================================

def update_field_mappings(new_entries: list[dict]):
    """增量更新 field_value_mappings.json"""
    existing = load_json("field_value_mappings.json") or []

    # 对新条目提取映射
    code_type_mappings = extract_field_code_type_mapping(new_entries)
    hardcoded_enums = extract_hardcoded_enum_mappings(new_entries)
    new_merged = merge_mappings(code_type_mappings, hardcoded_enums)

    # 与现有映射合并
    existing_index = {}
    for t in existing:
        field_index = {}
        for f in t["fields"]:
            field_index[f["field_name"]] = f
        existing_index[t["table_name"]] = field_index

    for table in new_merged:
        table_name = table["table_name"]
        if table_name not in existing_index:
            # 全新表
            existing.append(table)
            existing_index[table_name] = {}
            for f in table["fields"]:
                existing_index[table_name][f["field_name"]] = f
            print(f"  🆕 新表: {table_name} ({len(table['fields'])} 个字段)")
        else:
            # 已存在的表，合并字段
            for new_field in table["fields"]:
                fn = new_field["field_name"]
                if fn not in existing_index[table_name]:
                    existing_index[table_name][fn] = new_field
                    print(f"  ➕ 新字段: {table_name}.{fn}")
                else:
                    # 合并 code_types 和 hardcoded_values
                    old = existing_index[table_name][fn]
                    old_ct = set(old.get("code_types", []))
                    new_ct = set(new_field.get("code_types", []))
                    old_ct.update(new_ct)
                    old["code_types"] = sorted(list(old_ct))

                    old_hv = old.get("hardcoded_values", {})
                    new_hv = new_field.get("hardcoded_values", {})
                    old_hv.update(new_hv)
                    old["hardcoded_values"] = old_hv

                    if old["source"] != "both" and new_field["source"] != old["source"]:
                        old["source"] = "both"

                    if new_ct - old_ct or set(new_hv.keys()) - set(old_hv.keys()):
                        print(f"  🔄 更新字段: {table_name}.{fn}")

    save_json(existing, "field_value_mappings.json")
    return existing


# ============================================================
# 4. 检查新表
# ============================================================

def check_new_tables(new_entries: list[dict]):
    """检查是否有 raw_ddl.json 中不存在的表"""
    raw_ddl = load_json("raw_ddl.json") or []
    existing_tables = {t["table_name"] for t in raw_ddl if t["status"] == "ok"}

    new_tables = set()
    for entry in new_entries:
        new_tables.update(entry.get("tables", []))

    # 过滤掉临时表和 SQL 关键字
    missing = {t for t in new_tables if t not in existing_tables
               and not t.startswith('tmp_') and not t.startswith('xls_')}

    if missing:
        print(f"\n  ⚠️  发现 {len(missing)} 张新表在 raw_ddl.json 中不存在:")
        for t in sorted(missing):
            print(f"    - {t}")
        print(f"  如需下载这些表的 DDL，请运行:")
        print(f"    python step3_download_ddl.py")
        print(f"  然后重新运行 step4: python step4_ai_enhance_schema.py")
    else:
        print(f"  ✅ 所有表都已存在于 raw_ddl.json")

    return missing


# ============================================================
# 5. AI 生成新 Few-Shot
# ============================================================

def ai_generate_few_shots(new_entries: list[dict], schema: list[dict]) -> list[dict]:
    """用 AI 反向工程新 SQL，生成 Few-Shot 样本"""
    # 加载 API
    load_dotenv(os.path.join(DATA_DIR, '.env'))
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        load_dotenv(os.path.join(DATA_DIR, '..', 'data', '.env'))
        api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        load_dotenv(os.path.join(DATA_DIR, '..', 'app', '.env'))
        api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("  ❌ 未找到 DEEPSEEK_API_KEY")
        return []

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    # 构建 Schema 索引
    schema_index = {s["table_name"]: s for s in schema}

    system_prompt = """你是深谙电网业务的数据架构师。请对以下 SQL 进行"反向工程"。

【输出格式】(严格 JSON):
{
  "question": "推测的自然语言查询需求（包含具体筛选条件）",
  "business_rules": "1. 规则一。2. 规则二。...",
  "search_keywords": ["关键词1", "关键词2", "关键词3", "关键词4", "关键词5"],
  "complexity": "simple|medium|complex"
}"""

    results = []
    for i, entry in enumerate(new_entries):
        title = entry.get("title", f"新案例_{i+1}")
        sql = entry["sql"]
        tables = entry.get("tables", [])

        # 构建 Schema 上下文
        schema_context = []
        for t in tables:
            if t in schema_index:
                fields = schema_index[t].get("fields", [])
                field_lines = []
                for f in fields[:15]:
                    c = f.get("comment", "")[:60]
                    if c:
                        field_lines.append(f"    {f['field_name']}: {c}")
                if field_lines:
                    schema_context.append(f"【{t}】:\n" + "\n".join(field_lines))

        schema_text = "\n\n".join(schema_context) if schema_context else "(无 Schema 信息)"

        print(f"  [{i+1}/{len(new_entries)}] 🔄 AI 分析: {title} ...", end=" ")

        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"""【SQL 标题】: {title}
【涉及的表】: {', '.join(tables) if tables else '(未识别)'}

【数据库表结构参考】:
{schema_text}

【SQL 代码】:
{sql}

请分析这段 SQL 的业务含义。"""}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )

            ai_response = response.choices[0].message.content.strip()
            parsed = json.loads(ai_response, strict=False)
            parsed["sql"] = sql
            parsed["title"] = title
            parsed["tables_used"] = tables
            results.append(parsed)
            print(f"✅")

        except Exception as e:
            print(f"❌ {e}")
            # 降级
            results.append({
                "question": title,
                "business_rules": "",
                "search_keywords": entry.get("keywords", []),
                "complexity": "medium",
                "sql": sql,
                "title": title,
                "tables_used": tables
            })

        time.sleep(0.5)

    return results


def append_to_few_shots(new_few_shots: list[dict]):
    """追加到 few_shot_examples.json（按 SQL 去重）"""
    existing = load_json("few_shot_examples.json") or []

    existing_sigs = set()
    for e in existing:
        sig = f"{e.get('sql', '')[:100].strip().upper()}|{len(e.get('sql', ''))}"
        existing_sigs.add(sig)

    added = 0
    for fs in new_few_shots:
        sig = f"{fs.get('sql', '')[:100].strip().upper()}|{len(fs.get('sql', ''))}"
        if sig not in existing_sigs:
            existing.append(fs)
            existing_sigs.add(sig)
            added += 1

    save_json(existing, "few_shot_examples.json")
    print(f"  ✅ few_shot_examples.json: 新增 {added} 条 (总共 {len(existing)} 条)")

    return existing


# ============================================================
# 6. 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="增量追加新 SQL 案例到知识库")
    parser.add_argument("--sql-file", type=str, help="新的 SQL 文件路径")
    parser.add_argument("--from-merged-sql", action="store_true",
                        help="从 data/合并.sql 增量解析（对比已有条目，只追加新的）")
    parser.add_argument("--sql", type=str, help="直接输入单条 SQL")
    parser.add_argument("--title", type=str, default=None, help="SQL 的标题")
    parser.add_argument("--skip-ai", action="store_true",
                        help="跳过 AI 生成 Few-Shot（只做离线解析）")
    parser.add_argument("--build-vectors", action="store_true",
                        help="添加完成后自动重建向量库")
    parser.add_argument("--dry-run", action="store_true",
                        help="只预览，不实际写入")
    args = parser.parse_args()

    if not any([args.sql_file, args.from_merged_sql, args.sql]):
        print("❌ 请指定输入来源: --sql-file / --from-merged-sql / --sql")
        print("   示例: python add_new_cases.py --sql-file '../data/新案例.sql'")
        sys.exit(1)

    print("=" * 60)
    print("📥 增量追加新案例")
    print("=" * 60)

    # ---- Step A: 解析新 SQL ----
    print("\n🔍 Step A: 解析新 SQL...")
    new_entries = []

    if args.sql_file:
        file_path = args.sql_file
        if not os.path.isabs(file_path):
            file_path = os.path.join(DATA_DIR, file_path)
        if not os.path.exists(file_path):
            print(f"❌ 文件不存在: {file_path}")
            sys.exit(1)
        print(f"  来源: {file_path}")

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 尝试按 -- 文件名： 切分
        if '-- 文件名' in content:
            blocks = split_sql_blocks(content)
            print(f"  检测到 {len(blocks)} 个 SQL 块")
            for block in blocks:
                entries = parse_new_sqls(block["sql"], block["title"])
                new_entries.extend(entries)
        else:
            entries = parse_new_sqls(content, args.title)
            new_entries.extend(entries)

    elif args.from_merged_sql:
        merged_path = os.path.join(DATA_DIR, "..", "data", "合并.sql")
        if not os.path.exists(merged_path):
            print(f"❌ 未找到: {merged_path}")
            sys.exit(1)
        print(f"  来源: {merged_path} (增量模式)")

        # 加载已有 SQL 签名
        existing = load_json("parsed_sqls.json") or []
        existing_sigs = set()
        for e in existing:
            sig = f"{e['sql'][:100].strip().upper()}|{len(e['sql'])}"
            existing_sigs.add(sig)

        # 解析合并.sql 全部内容
        with open(merged_path, 'r', encoding='utf-8') as f:
            content = f.read()
        blocks = split_sql_blocks(content)

        # 只取新增的
        for block in blocks:
            entries = parse_new_sqls(block["sql"], block["title"])
            for entry in entries:
                sig = f"{entry['sql'][:100].strip().upper()}|{len(entry['sql'])}"
                if sig not in existing_sigs:
                    new_entries.append(entry)

        print(f"  发现 {len(new_entries)} 条新 SQL（总共 {len(blocks)} 块）")

    elif args.sql:
        print(f"  来源: 命令行输入")
        entries = parse_new_sqls(args.sql, args.title)
        new_entries.extend(entries)

    if not new_entries:
        print("  ✅ 没有新条目需要添加")
        return

    print(f"  📦 共 {len(new_entries)} 条新 SQL")
    for e in new_entries:
        print(f"    - {e['title']}: {len(e['tables'])} 张表, {len(e['case_when_mappings'])} CASE WHEN")

    if args.dry_run:
        print("\n💡 预览模式，不写入。移除 --dry-run 以执行。")
        return

    # ---- Step B: 追加到 parsed_sqls.json ----
    print("\n📝 Step B: 追加到 parsed_sqls.json...")
    updated_sqls = append_to_parsed_sqls(new_entries)

    # ---- Step C: 更新字段映射 ----
    print("\n🔗 Step C: 更新 field_value_mappings.json...")
    updated_mappings = update_field_mappings(new_entries)

    # ---- Step D: 检查新表 ----
    print("\n🔍 Step D: 检查是否有新表...")
    missing_tables = check_new_tables(new_entries)

    # ---- Step E: AI 生成 Few-Shot ----
    if not args.skip_ai:
        print(f"\n🤖 Step E: AI 生成 Few-Shot ({len(new_entries)} 条)...")
        schema = load_json("final_super_schema_by_ai.json") or []
        new_few_shots = ai_generate_few_shots(new_entries, schema)
        if new_few_shots:
            append_to_few_shots(new_few_shots)
    else:
        print("\n⏭️  跳过 AI 步骤 (--skip-ai)")

    # ---- 总结 ----
    print(f"\n{'=' * 60}")
    print("✅ 增量追加完成！")
    print(f"  parsed_sqls.json: 共 {len(load_json('parsed_sqls.json') or [])} 条")
    print(f"  field_value_mappings.json: 共 {len(load_json('field_value_mappings.json') or [])} 张表")
    print(f"  few_shot_examples.json: 共 {len(load_json('few_shot_examples.json') or [])} 条")

    if missing_tables:
        print(f"\n⚠️  后续步骤:")
        print(f"  1. python step3_download_ddl.py    (下载 {len(missing_tables)} 张新表的 DDL)")
        print(f"  2. python step4_ai_enhance_schema.py  (重新增强 Schema)")

    if args.build_vectors:
        print(f"\n🔨 重建向量库...")
        os.system(f"cd {DATA_DIR} && {sys.executable} step6_build_vectors.py")
    else:
        print(f"\n💡 提示: 加 --build-vectors 参数可在添加后自动重建向量库")

    print(f"\n📋 如果只是新增了 SQL（没有新表），通常只需:")
    print(f"   python add_new_cases.py --sql-file '新案例.sql' --build-vectors")


if __name__ == "__main__":
    main()
