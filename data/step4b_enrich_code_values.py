"""
Step 4b: 从 m_p_code 表查询码值，注入到 final_super_schema_by_ai.json 字段注释中
=================================================================================
输入: field_value_mappings.json (table→field→code_types 映射) + m_p_code 表
输出: final_super_schema_by_ai.json (comments 中追加码值枚举)

效果: 当 Agent 检索到表结构时，码值直接出现在字段注释中，无需额外查询
"""

import json
import os
import re
import pymysql
from collections import defaultdict


def load_mappings(file_path: str) -> dict:
    """加载 field_value_mappings，构建 {table: {field: [code_types]}} 索引"""
    with open(file_path, 'r', encoding='utf-8') as f:
        mappings = json.load(f)

    index = {}
    for t in mappings:
        fields_map = {}
        for f in t['fields']:
            if f['code_types']:
                fields_map[f['field_name'].lower()] = f['code_types']
        if fields_map:
            index[t['table_name'].lower()] = fields_map

    return index


def query_m_p_code(conn, code_type: str) -> dict:
    """查询 m_p_code 获取 code_type 的所有 value→name 映射"""
    cur = conn.cursor()
    cur.execute(
        "SELECT value, name FROM m_p_code WHERE code_type=%s AND take_effect_flag=1 ORDER BY value",
        (code_type,)
    )
    result = {}
    for value, name in cur.fetchall():
        result[value] = name
    return result


def load_schema(file_path: str) -> tuple[list[dict], dict]:
    """加载 schema 并构建 table→index 映射"""
    with open(file_path, 'r', encoding='utf-8') as f:
        schema = json.load(f)

    # {table_name: position_in_schema}
    index = {t['table_name'].lower(): i for i, t in enumerate(schema)}
    return schema, index


def enrich_comment(existing_comment: str, code_values: dict, code_type: str) -> str:
    """
    在已有注释末尾追加码值枚举。
    如果已有枚举值信息，替换为更完整的版本。

    格式: [原注释] 。字典: code_type。枚举: 01=值1, 02=值2, ...
    """
    values_str = ', '.join(f'{v}={n}' for v, n in code_values.items())
    new_part = f' 字典: {code_type}。枚举: {values_str}'

    existing = existing_comment.strip() if existing_comment else ''

    # 如果已有"字典:"相关内容，检查是否已包含相同 code_type
    if f'字典: {code_type}' in existing:
        # 替换已有的该 code_type 内容
        existing = re.sub(
            rf'字典: {re.escape(code_type)}。枚举: [^。]*',
            f'字典: {code_type}。枚举: {values_str}',
            existing
        )
        return existing

    # 如果已有其他字典，追加
    if '字典:' in existing:
        return f'{existing}；字典: {code_type}。枚举: {values_str}'

    # 否则直接追加
    if existing:
        return f'{existing}。字典: {code_type}。枚举: {values_str}'
    else:
        return f'字典: {code_type}。枚举: {values_str}'


def main():
    data_dir = os.path.dirname(os.path.abspath(__file__))

    # 加载数据
    mapping_index = load_mappings(os.path.join(data_dir, 'field_value_mappings.json'))
    schema, schema_index = load_schema(os.path.join(data_dir, 'final_super_schema_by_ai.json'))

    print(f'📖 加载: {len(schema)} 张表 schema, {len(mapping_index)} 张表有码值映射')

    # 收集所有需要查询的 code_type
    all_cts = set()
    ct_to_fields = defaultdict(list)  # {code_type: [(table, field), ...]}

    for table_lower, fields in mapping_index.items():
        for field, code_types in fields.items():
            for ct in code_types:
                all_cts.add(ct)
                ct_to_fields[ct].append((table_lower, field))

    print(f'🔍 需要查询 {len(all_cts)} 个 code_type')

    # 连接数据库，批量查询码值
    conn = pymysql.connect(
        host='10.11.0.95', port=10050,
        user='readonlyuser', password='reAd0n1@eR',
        database='epmp', charset='utf8mb4'
    )

    ct_values = {}  # {code_type: {value: name}}
    for ct in sorted(all_cts):
        values = query_m_p_code(conn, ct)
        if values:
            ct_values[ct] = values
            print(f'  ✅ {ct}: {len(values)} 个枚举值')
        else:
            print(f'  ⚠️ {ct}: 无数据')

    conn.close()

    # 注入码值到 schema 注释
    enriched_count = 0
    skipped_count = 0

    for table_lower, fields in mapping_index.items():
        if table_lower not in schema_index:
            # 表不在 schema 中（可能是别名）
            skipped_count += len(fields)
            continue

        schema_entry = schema[schema_index[table_lower]]

        for schema_field in schema_entry['fields']:
            field_name = schema_field['field_name'].lower()
            if field_name not in fields:
                continue

            code_types = fields[field_name]
            old_comment = schema_field.get('comment', '')

            for ct in code_types:
                if ct not in ct_values:
                    continue

                new_comment = enrich_comment(old_comment, ct_values[ct], ct)
                if new_comment != old_comment:
                    schema_field['comment'] = new_comment
                    old_comment = new_comment
                    enriched_count += 1

    print(f'\n📊 注入结果: {enriched_count} 个字段富化, {skipped_count} 个跳过（表不在schema中）')

    # 保存
    output_file = os.path.join(data_dir, 'final_super_schema_by_ai.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)

    print(f'💾 已保存至: {output_file}')

    # 打印几个样例
    print('\n📋 样例:')
    for t in schema[:5]:
        for f in t['fields']:
            if '字典:' in (f.get('comment', '') or ''):
                print(f'  [{t["table_name"]}] {f["field_name"]}: {f["comment"][:200]}...' if len(f['comment']) > 200 else f'  [{t["table_name"]}] {f["field_name"]}: {f["comment"]}')
                break


if __name__ == '__main__':
    main()
