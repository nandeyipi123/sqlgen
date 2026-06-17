"""
将 new_cases.sql 中的标量子查询批量转换为 LEFT JOIN 风格 (v3)

策略：精准匹配，只转换简单模式，复杂场景保持原样
- 目标: (SELECT col FROM single_table WHERE simple_conditions) alias
- 排除: 派生表、UNION、JOIN、GROUP BY、EXISTS
"""

import re
import os

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = os.path.join(DATA_DIR, "new_cases.sql")
OUTPUT_FILE = os.path.join(DATA_DIR, "new_cases_converted.sql")


def split_cases(content: str) -> list[dict]:
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    parts = re.split(r'--\s*文件名[：:]\s*', content)
    cases = []
    for part in parts:
        if not part.strip():
            continue
        lines = part.split('\n')
        title = lines[0].strip()
        sql_lines = []
        for line in lines[1:]:
            stripped = line.strip()
            if stripped.startswith('====') or stripped.startswith('==='):
                continue
            if stripped.startswith('--') and '文件名' in stripped:
                continue
            sql_lines.append(line)
        sql = '\n'.join(sql_lines).strip()
        if sql and len(sql) > 20:
            cases.append({"title": title, "sql": sql})
    return cases


def find_matching_paren(text: str, start: int) -> int:
    depth = 0
    for i in range(start, len(text)):
        if text[i] == '(':
            depth += 1
        elif text[i] == ')':
            depth -= 1
            if depth == 0:
                return i
    return -1


def is_scalar_subquery(full_sql: str, start: int, end: int) -> bool:
    """
    检查 (SELECT ...) 是否为 SELECT 列表中的标量子查询（而非派生表或 EXISTS）
    """
    inner = full_sql[start+1:end].strip()

    # 排除: 包含 JOIN, UNION, GROUP BY, HAVING (太复杂)
    if re.search(r'\b(join|union|group\s+by|having)\b', inner, re.IGNORECASE):
        return False

    # 排除: 多表查询 (FROM a, b 或 FROM a JOIN b)
    from_count = len(re.findall(r'\bfrom\b\s+\w+', inner, re.IGNORECASE))
    if from_count > 1:
        return False

    # 检查上下文: 在 SELECT 列表中？
    before = full_sql[:start].rstrip()
    # 前面应该是 SELECT、逗号、或换行
    before_clean = before.strip()[-20:].upper() if len(before.strip()) >= 20 else before.strip().upper()
    # 检查前面最近的非空白字符
    before_last = before.strip()[-1:] if before.strip() else ''

    # 不在 FROM/JOIN 子句中
    before_context = full_sql[max(0, start-100):start].lower()
    if re.search(r'\b(from|join)\s*$', before_context.strip()):
        return False

    # 排除 EXISTS / NOT EXISTS
    before_50 = full_sql[max(0, start-50):start].strip().upper()
    if before_50.endswith('EXISTS') or before_50.endswith('NOT EXISTS'):
        return False

    # 核心检查：子查询必须在主 SELECT 列表中（主 FROM 之前）
    # 找到主 FROM（不在任何括号内的第一个 FROM）
    depth = 0
    main_from_pos = -1
    for idx, ch in enumerate(full_sql):
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        elif depth == 0:
            # 在括号外部找 FROM 关键词
            rest = full_sql[idx:idx+5].upper()
            if rest.startswith('FROM') and (idx+4 >= len(full_sql) or not full_sql[idx+4].isalnum()):
                main_from_pos = idx
                break

    # 如果子查询在 FROM 之后，说明它在 WHERE/JOIN 中，不应转换
    if main_from_pos > 0 and start > main_from_pos:
        return False

    # 后面跟的是别名（英文/中文），不是 SQL 关键字
    after = full_sql[end+1:].lstrip()
    after_upper = after[:20].upper()
    for kw in ['FROM', 'JOIN', 'WHERE', 'GROUP', 'ORDER', 'HAVING', 'LIMIT', 'UNION',
               'LEFT', 'RIGHT', 'INNER', 'OUTER', 'CROSS']:
        if after_upper.startswith(kw + ' ') or after_upper.startswith(kw + '\n') or after_upper == kw:
            return False

    return True


def extract_simple_scalar(inner_sql: str) -> dict | None:
    """
    从简单的标量子查询中提取: select_col, from_table, where_clause
    例如: 'SELECT NAME FROM m_p_code WHERE code_type = \'statusCode\' AND VALUE = c.status_code'
    """
    # 标准化空白
    flat = re.sub(r'\s+', ' ', inner_sql.strip())

    # 模式: SELECT col1, col2 FROM table [alias] WHERE conditions [LIMIT n]
    m = re.match(
        r"select\s+(.+?)\s+from\s+(\w+)(?:\s+(?:as\s+)?(\w+))?\s+where\s+(.+?)(?:\s+limit\s+\d+)?\s*$",
        flat, re.IGNORECASE
    )
    if not m:
        return None

    select_cols = m.group(1).strip()
    from_table = m.group(2)
    inner_alias = m.group(3) or ""  # 子查询内部给表起的别名
    where_clause = m.group(4).strip()

    # 清理 SELECT 列中的内部表别名引用
    # 例如: 'dd.operator_no' → 'operator_no' (如果 inner_alias = 'dd')
    if inner_alias:
        prefix = inner_alias + '.'
        cols = select_cols.split(',')
        cleaned_cols = []
        for c in cols:
            c = c.strip()
            if c.lower().startswith(prefix.lower()):
                c = c[len(prefix):]
            cleaned_cols.append(c)
        select_cols = ', '.join(cleaned_cols)

    # 过滤关键字别名
    if inner_alias.upper() in ('WHERE', 'AND', 'OR', 'LIMIT', 'ON', 'SET'):
        inner_alias = ""

    return {
        "select_cols": select_cols,
        "from_table": from_table,
        "where_clause": where_clause,
        "inner_alias": inner_alias,
    }


def generate_join(from_table: str, where_clause: str, select_cols: str,
                  outer_alias: str, inner_alias: str, join_counters: dict) -> tuple[str, str, str]:
    """生成 LEFT JOIN 语句和列引用"""

    alias_map = {
        "m_p_code": "p", "ac_org": "o", "m_r_sect": "rs", "m_c_mp": "mp",
        "m_g_line": "gl", "m_g_tg": "gt", "m_c_cert": "crt", "m_g_ll_stat": "lls",
        "m_g_chkunit": "cu", "m_g_subs": "gs", "m_e_cat_prc": "ecp",
        "m_r_oper_activity": "roa", "m_c_cons": "cc", "m_c_mp_info": "cmi",
        "m_r_coll_obj": "rco", "m_r_data": "rd", "m_r_data_arc": "rda",
        "m_e_cons_snap": "ecs", "m_e_cons_snap_arc": "ecsa",
        "m_a_rcvbl_flow": "rf", "m_a_rcvbl_flow_arc": "rfa",
        "m_a_rcved_flow": "rvf", "m_e_cons_prc_amt": "ecpa",
        "m_e_cons_prc_amt_arc": "ecpaa", "m_a_note_info": "ani",
        "m_p_syspara": "mps", "m_a_transit_det": "atd", "m_a_transit": "atr",
        "m_a_pay_flow": "apf", "m_e_price_adjust_tmp": "epat",
        "m_e_mp_para_snap_arc": "empsa", "m_ps_purchase": "psp",
        "m_c_market_actual_variety": "cmav", "m_r_plan_arc": "rpa",
        "ac_user": "au", "m_c_cons_prc": "ccp", "m_c_meter": "cm",
        "m_e_add_pl_prc": "eap", "m_a_inv_print_flow": "aip",
        "m_kb_a_card_classpq": "kcc", "m_e_mp_pq_arc": "empa",
        "m_r_plan": "rp", "m_g_io_mp": "gio", "m_c_contact": "cct",
        "m_c_cons_contact_rela": "cccr", "m_e_Cons_Snap_Arc": "ecsa",
        "m_e_cat_prc_det_items": "ecdi",
    }
    table_lower = from_table.lower()
    base = alias_map.get(table_lower, "t")
    key = f"{table_lower}"
    if key not in join_counters:
        join_counters[key] = 0
    join_counters[key] += 1
    join_alias = f"{base}{join_counters[key]}"

    on_clause = where_clause.strip()
    # 替换子查询内部表别名为新 JOIN 别名
    if inner_alias:
        # 用单词边界匹配替换：dd.field → join_alias.field
        on_clause = re.sub(
            rf'\b{re.escape(inner_alias)}\.',
            f'{join_alias}.',
            on_clause,
            flags=re.IGNORECASE
        )
    # m_p_code 加 take_effect_flag
    if table_lower == "m_p_code" and "take_effect_flag" not in on_clause.lower():
        on_clause += " AND take_effect_flag = 1"

    left_join = f"LEFT JOIN {from_table} {join_alias} ON {on_clause}"

    # 列引用
    if outer_alias:
        col_ref = f"{join_alias}.{select_cols} AS {outer_alias}"
    else:
        col_ref = f"{join_alias}.{select_cols}"

    return join_alias, left_join, col_ref


def convert_sql(sql: str) -> str:
    """转换单条 SQL"""

    # 第一步：找出所有标量子查询的位置
    candidates = []
    i = 0
    while i < len(sql):
        if sql[i] == '(':
            after = sql[i+1:].lstrip()
            if after[:6].upper() == 'SELECT':
                end = find_matching_paren(sql, i)
                if end == -1:
                    i += 1
                    continue

                if is_scalar_subquery(sql, i, end):
                    full = sql[i:end+1]
                    inner = full[1:-1].strip()  # 去掉外层括号
                    parsed = extract_simple_scalar(inner)
                    if parsed:
                        # 提取后面的别名（需要原始未 strip 的版本来计算正确偏移）
                        after_raw = sql[end+1:]  # 不 strip
                        after_stripped = after_raw.lstrip()
                        alias_match = re.match(r"['\"]?([^\s,;)'\"]+)", after_stripped)
                        outer_alias = ""
                        alias_len = 0
                        if alias_match:
                            raw = alias_match.group(1).strip("'\"`，,;")
                            if raw.upper() not in ('FROM', 'WHERE', 'GROUP', 'ORDER', 'HAVING',
                                                    'LIMIT', 'UNION', 'LEFT', 'RIGHT', 'INNER',
                                                    'JOIN', 'ON', 'AND', 'OR', 'SET', 'AS', 'SELECT'):
                                outer_alias = raw
                                # alias_len = 空白 + 别名长度
                                leading_ws = len(after_raw) - len(after_stripped)
                                alias_len = leading_ws + alias_match.end()

                        candidates.append({
                            "start": i,
                            "end": end + alias_len,  # 包含别名
                            "parsed": parsed,
                            "outer_alias": outer_alias,
                            "full_match": sql[i:end+1+alias_len],
                        })

                i = end + 1
                continue
        i += 1

    if not candidates:
        return sql

    # 第二步：生成所有 LEFT JOIN，从后往前替换
    join_counters = {}
    all_joins = []

    for c in reversed(candidates):
        join_alias, left_join, col_ref = generate_join(
            c["parsed"]["from_table"],
            c["parsed"]["where_clause"],
            c["parsed"]["select_cols"],
            c["outer_alias"],
            c["parsed"].get("inner_alias", ""),
            join_counters
        )
        all_joins.append(left_join)

        # 替换：直接用列引用替换 (SELECT ...) 别名 部分
        sql = sql[:c["start"]] + col_ref + sql[c["end"]+1:]

    all_joins.reverse()

    # 第三步：插入 LEFT JOIN
    # 找到 WHERE 子句（不在子查询内部的）
    join_block = '\n' + '\n'.join(all_joins)
    result = insert_joins_before_where(sql, join_block)

    return result


def insert_joins_before_where(sql: str, join_block: str) -> str:
    """
    将 LEFT JOIN 块插入到主查询的 WHERE 之前。
    需要避免插入到子查询内部的 WHERE 前面。
    """
    lines = sql.split('\n')

    # 策略：找到最外层（缩进最少）的 WHERE
    best_line = -1
    for i, line in enumerate(lines):
        stripped = line.strip()
        if re.match(r'^WHERE\b', stripped, re.IGNORECASE):
            # 计算缩进
            indent = len(line) - len(line.lstrip())
            if best_line == -1 or indent < best_indent:
                best_line = i
                best_indent = indent

    if best_line == -1:
        # 没找到 WHERE，找 GROUP BY / ORDER BY / HAVING
        for i, line in enumerate(lines):
            stripped = line.strip()
            if re.match(r'^(GROUP|ORDER|HAVING)\b', stripped, re.IGNORECASE):
                indent = len(line) - len(line.lstrip())
                if best_line == -1 or indent < best_indent:
                    best_line = i
                    best_indent = indent

    if best_line >= 0:
        lines.insert(best_line, join_block)
    else:
        lines.append(join_block)

    return '\n'.join(lines)


def main():
    print("=" * 60)
    print("[Convert] Scalar Subquery -> LEFT JOIN (v3)")
    print("=" * 60)

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    cases = split_cases(content)
    print(f"[READ] {len(cases)} cases loaded")

    converted_cases = []
    total_scalar = 0
    total_skipped = 0

    for i, case in enumerate(cases):
        original = case["sql"]

        # 统计标量子查询
        candidates = []
        idx = 0
        while idx < len(original):
            if original[idx] == '(':
                after = original[idx+1:].lstrip()
                if after[:6].upper() == 'SELECT':
                    end = find_matching_paren(original, idx)
                    if end > 0 and is_scalar_subquery(original, idx, end):
                        inner = original[idx+1:end].strip()
                        parsed = extract_simple_scalar(inner)
                        if parsed:
                            candidates.append(parsed["from_table"])
                    idx = end + 1
                    continue
            idx += 1

        total_scalar += len(candidates)

        if candidates:
            converted_sql = convert_sql(original)
            converted_cases.append({"title": case["title"], "sql": converted_sql})
            tables_set = sorted(set(candidates))
            print(f"  [{i+1}/{len(cases)}] {case['title']}: {len(candidates)} -> {', '.join(tables_set)}")
        else:
            converted_cases.append({"title": case["title"], "sql": original})

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for case in converted_cases:
            f.write(f"-- 文件名：{case['title']}\n")
            f.write(case["sql"])
            f.write("\n\n")

    print(f"\n{'=' * 60}")
    print(f"[DONE]")
    print(f"  Total cases: {len(cases)}")
    print(f"  Scalar subqueries converted: {total_scalar}")
    print(f"  Output: {OUTPUT_FILE}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
