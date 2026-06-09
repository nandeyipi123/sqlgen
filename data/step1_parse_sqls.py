"""
Step 1: 解析常用 SQL 文件
========================
输入: data/合并.sql (以及可选的达州模板 SQL)
输出: parsed_sqls.json

对每条 SQL 提取:
- title: SQL 标题
- sql: 清洗后的 SQL
- tables: 涉及的表名列表
- m_p_code_mappings: 从 m_p_code 字典表关联中提取的 {code_type: [values]}
- case_when_mappings: 从 CASE WHEN 硬编码中提取的 {field: {value: label}}
- keywords: 从列别名、注释中提取的业务关键词
"""

import json
import re
import os
import sys


def split_sql_blocks(content: str) -> list[dict]:
    """按 '-- 文件名：' 切分 SQL 文件，返回 [{title, sql}] 列表"""
    # 标准化换行
    content = content.replace('\r\n', '\n').replace('\r', '\n')

    blocks = []
    # 按 "-- 文件名：" 分割
    parts = re.split(r'--\s*文件名[：:]\s*', content)

    for part in parts:
        if not part.strip():
            continue

        lines = part.split('\n')
        title = lines[0].strip().rstrip('.sql')

        # 跳过 ====== 分隔线和标题行，提取 SQL
        sql_lines = []
        for line in lines[1:]:
            line_stripped = line.strip()
            if line_stripped.startswith('====') or line_stripped.startswith('==='):
                continue
            if line_stripped.startswith('--') and '文件名' in line_stripped:
                continue
            sql_lines.append(line)

        sql_text = '\n'.join(sql_lines).strip()
        if not sql_text:
            continue

        blocks.append({"title": title, "sql": sql_text})

    return blocks


def split_statements(sql_text: str) -> list[str]:
    """将多语句 SQL 拆分为独立语句（按 ; 分号拆分，过滤空语句和非 SELECT 语句）"""
    # 先保护字符串中的分号
    # 简单策略：按 ; 拆分后过滤
    raw_parts = sql_text.split(';')
    statements = []
    for part in raw_parts:
        part = part.strip()
        if not part:
            continue
        # 过滤纯 SET/UPDATE/DELETE 语句（但保留以供参考）
        statements.append(part)
    return statements


def extract_tables(sql: str) -> list[str]:
    """从 SQL 中提取所有涉及的表名"""
    tables = set()

    # 匹配 FROM/JOIN 后的表名
    # 支持: FROM table, FROM db.table, JOIN table, LEFT JOIN table 等
    patterns = [
        r'\bFROM\s+`?([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)`?',
        r'\bJOIN\s+`?([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)`?',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, sql, re.IGNORECASE)
        for m in matches:
            # 如果是 db.table 格式，只取 table 部分
            if '.' in m:
                parts = m.split('.')
                # 跳过临时表 (tmp_xxx)
                if not parts[0].startswith('tmp_'):
                    tables.add(parts[0])
                tables.add(m)  # 保留完整引用
            else:
                tables.add(m)

    # 过滤掉 SQL 关键字误匹配
    sql_keywords = {'select', 'from', 'where', 'join', 'left', 'right', 'inner',
                    'outer', 'cross', 'on', 'as', 'and', 'or', 'not', 'in', 'is',
                    'null', 'like', 'between', 'exists', 'case', 'when', 'then',
                    'else', 'end', 'group', 'order', 'by', 'having', 'limit',
                    'union', 'all', 'distinct', 'set', 'update', 'delete', 'insert'}
    tables = {t for t in tables if t.lower() not in sql_keywords}

    # 过滤掉纯数字和太短的
    tables = {t for t in tables if not t.isdigit() and len(t) > 1}

    return sorted(tables)


def extract_m_p_code_mappings(sql: str) -> list[dict]:
    """从 SQL 中提取 m_p_code 字典表的 code_type → value 映射"""
    mappings = []

    # 匹配 pX.code_type='xxx' and pX.value=table.field 或类似模式
    # 模式1: pX.code_type='codeType' and pX.value=xxx
    pattern1 = re.findall(
        r"code_type\s*=\s*'([^']+)'\s+and\s+\w+\.\s*`?value`?\s*=\s*(\w+\.\w+)",
        sql, re.IGNORECASE
    )
    for code_type, field_ref in pattern1:
        mappings.append({"code_type": code_type, "field_ref": field_ref})

    # 模式2: 子查询中 SELECT name from m_p_code cd where cd.code_type='xxx' and cd.value=...
    pattern2 = re.findall(
        r"code_type\s*=\s*'([^']+)'\s+and\s+\w+\.\s*`?value`?\s*=\s*(\w+\.\w+)",
        sql, re.IGNORECASE
    )

    # 去重
    seen = set()
    unique_mappings = []
    for m in mappings:
        key = (m["code_type"], m["field_ref"])
        if key not in seen:
            seen.add(key)
            unique_mappings.append(m)

    return unique_mappings


def extract_case_when_mappings(sql: str) -> list[dict]:
    """从 SQL 的 CASE WHEN 中提取字段→值→标签的映射"""
    mappings = []

    # 匹配 CASE field WHEN 'val1' THEN 'label1' WHEN 'val2' THEN 'label2' ... END
    # 模式: case xxx when '01' then '标签1' when '02' then '标签2' ... end
    case_pattern = re.findall(
        r"case\s+(\w+(?:\.\w+)?)\s+(when\s+'[^']*'\s+then\s+'[^']*'\s*)+(?:else\s+'[^']*'\s*)?end",
        sql, re.IGNORECASE
    )

    for field, when_clause in case_pattern:
        pairs = re.findall(r"when\s+'([^']*)'\s+then\s+'([^']*)'", when_clause, re.IGNORECASE)
        if pairs:
            mappings.append({
                "field": field.split('.')[-1] if '.' in field else field,
                "full_field_ref": field,
                "values": {v: l for v, l in pairs}
            })

    # 也匹配 else 部分
    case_with_else = re.findall(
        r"case\s+(\w+(?:\.\w+)?)\s+((?:when\s+'[^']*'\s+then\s+'[^']*'\s*)+)else\s+'([^']*)'\s*end",
        sql, re.IGNORECASE
    )
    for field, when_clause, else_label in case_with_else:
        pairs = re.findall(r"when\s+'([^']*)'\s+then\s+'([^']*)'", when_clause, re.IGNORECASE)
        if pairs:
            entry = {
                "field": field.split('.')[-1] if '.' in field else field,
                "full_field_ref": field,
                "values": {v: l for v, l in pairs},
                "else_label": else_label
            }
            mappings.append(entry)

    return mappings


def extract_aliases(sql: str) -> list[str]:
    """从 SQL 列别名中提取中文关键词（用于检索增强）"""
    aliases = []
    # 匹配 'xxx' 列别名或 xxx 列别名模式
    # 中文关键词模式
    alias_pattern = re.findall(r"as\s+'([^']*[一-鿿][^']*)'", sql, re.IGNORECASE)
    aliases.extend(alias_pattern)

    # 也匹配双引号别名
    alias_pattern2 = re.findall(r'as\s+"([^"]*[一-鿿][^"]*)"', sql, re.IGNORECASE)
    aliases.extend(alias_pattern2)

    # 匹配反引号别名
    alias_pattern3 = re.findall(r'as\s+`([^`]*[一-鿿][^`]*)`', sql, re.IGNORECASE)
    aliases.extend(alias_pattern3)

    # 也匹配没有 AS 关键字的别名: SELECT expr 别名
    alias_pattern4 = re.findall(r",\s*\n?\s*[a-zA-Z_][\w.]*\s+([一-鿿][一-鿿\w（）()]*)", sql)
    aliases.extend(alias_pattern4)

    return list(set(aliases))


def clean_sql(sql: str) -> str:
    """清洗 SQL：去除注释、压缩空白、标准化"""
    # 去除 # 开头的注释行
    sql = re.sub(r'#.*$', '', sql, flags=re.MULTILINE)
    # 去除 -- 开头的注释行（但保留注释中可能的有效信息）
    sql = re.sub(r'--\s*[^文].*$', '', sql, flags=re.MULTILINE)
    # 压缩多余空白
    sql = re.sub(r'\n\s*\n', '\n', sql)
    sql = re.sub(r'[ \t]+', ' ', sql)
    return sql.strip()


def parse_sql_file(file_path: str) -> list[dict]:
    """主解析函数"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    blocks = split_sql_blocks(content)
    print(f"📦 共识别 {len(blocks)} 个 SQL 块")

    parsed_sqls = []
    skipped = 0

    for block in blocks:
        title = block["title"]
        sql_text = block["sql"]

        # 清洗 SQL
        cleaned = clean_sql(sql_text)

        # 拆分为独立语句
        statements = split_statements(cleaned)

        # 只保留 SELECT 语句作为主要分析对象
        select_stmts = [s for s in statements if s.upper().strip().startswith('SELECT')]

        if not select_stmts:
            # 即使没有 SELECT，也保留原始 SQL 以供参考
            select_stmts = [cleaned] if cleaned else []
            if not cleaned:
                skipped += 1
                continue

        # 对每条 SELECT 语句进行分析
        for stmt in select_stmts:
            if len(stmt) < 20:  # 太短的跳过
                continue

            tables = extract_tables(stmt)
            mp_mappings = extract_m_p_code_mappings(stmt)
            case_mappings = extract_case_when_mappings(stmt)
            aliases = extract_aliases(stmt)

            parsed_sqls.append({
                "title": title,
                "sql": stmt,
                "tables": tables,
                "m_p_code_mappings": mp_mappings,
                "case_when_mappings": case_mappings,
                "keywords": aliases
            })

    print(f"✅ 解析完成: {len(parsed_sqls)} 条有效 SQL (跳过 {skipped} 条)")
    return parsed_sqls


def print_stats(parsed_sqls: list[dict]):
    """打印统计信息"""
    all_tables = set()
    all_code_types = set()
    total_case_mappings = 0

    for item in parsed_sqls:
        all_tables.update(item["tables"])
        for m in item["m_p_code_mappings"]:
            all_code_types.add(m["code_type"])
        total_case_mappings += len(item["case_when_mappings"])

    print(f"\n📊 统计:")
    print(f"  总 SQL 条数: {len(parsed_sqls)}")
    print(f"  涉及表数: {len(all_tables)}")
    print(f"  涉及 m_p_code code_type 数: {len(all_code_types)}")
    print(f"  CASE WHEN 硬编码映射数: {total_case_mappings}")
    print(f"\n📋 表名列表:")
    for t in sorted(all_tables):
        print(f"    - {t}")
    print(f"\n📋 code_type 列表:")
    for ct in sorted(all_code_types):
        print(f"    - {ct}")


if __name__ == "__main__":
    # 默认输入文件
    input_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "合并.sql")

    if not os.path.exists(input_file):
        print(f"❌ 未找到输入文件: {input_file}")
        sys.exit(1)

    print(f"📖 正在解析: {input_file}")
    parsed = parse_sql_file(input_file)
    print_stats(parsed)

    # 输出
    output_file = os.path.join(os.path.dirname(__file__), "parsed_sqls.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)

    print(f"\n💾 已保存至: {output_file}")
