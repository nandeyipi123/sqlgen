"""
Step 2: 从 SQL 中提取字段→值映射
================================
输入: parsed_sqls.json
输出: field_value_mappings.json

核心逻辑:
1. 从 CASE WHEN 中提取硬编码映射 → 这是最可靠的来源
2. 从 m_p_code 关联中提取 code_type → field 的关系
3. 聚合去重，按表名+字段名分组
4. 归一化 code_type 的大小写
"""

import json
import re
import os
from collections import defaultdict


def load_parsed_sqls(file_path: str) -> list[dict]:
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def normalize_code_type(code_type: str) -> str:
    """归一化 code_type 的大小写——SQL 中的 code_type 大小写不一致"""
    # 常见映射表
    known_aliases = {
        'statuscode': 'statusCode',
        'electypecode': 'elecTypeCode',
        'custsortcode': 'custSortCode',
        'psvoltcode': 'psVoltCode',
        'tradecode': 'tradeCode',
        'measmode': 'measMode',
        'calcmode': 'calcMode',
        'mpstatus': 'mpStatus',
        'mpattrcode': 'mpAttrCode',
        'llcalcmode': 'llCalcMode',
        'pfevalmode': 'pfEvalMode',
        'pfstdcode': 'pfStdCode',
        'pubprivflag': 'pubPrivFlag',
        'ctlmode': 'ctlMode',
        'readtypecode': 'readTypeCode',
        'wiringmode': 'wiringMode',
        'settlemode': 'settleMode',
        'paymode': 'payMode',
        'ruralconscode': 'ruralConsCode',
        'notetypecode': 'noteTypeCode',
        'usagetypecode': 'usageTypeCode',
        'phasecode': 'phaseCode',
        'notifymode': 'notifyMode',
        'shiftno': 'shiftNo',
        'sidecode': 'sideCode',
        'psnumcode': 'psNumCode',
        'psswitchmode': 'psSwitchMode',
        'pstypecode': 'psTypeCode',
        'sparepowerflag': 'sparePowerFlag',
        'interlockmode': 'interlockMode',
        'protectmode': 'protectMode',
        'lodeattrcode': 'lodeAttrCode',
        'rriocode': 'rrioCode',
        'transerflag': 'transferFlag',
        'msflag': 'msFlag',
        'mdtypecode': 'mdTypeCode',
        'lineinmode': 'lineInMode',
        'runmode': 'runMode',
        'freezemode': 'freezeMode',
        'busiscale': 'busiScale',
        'hecindustrycode': 'hecIndustryCode',
        'periodcode': 'periodCode',
        'mrmodecode': 'mrModeCode',
        'prepaycode': 'prepayCode',
        'relasortcode': 'relaSortCode',
        'bacalcmode': 'baCalcMode',
        'prpoint': 'prPoint',
        'psattr': 'psAttr',
    }
    return known_aliases.get(code_type.lower(), code_type)


def extract_field_code_type_mapping(parsed_sqls: list[dict]) -> dict:
    """
    从 m_p_code 关联中提取: {table_name: {field_name: [code_type1, code_type2, ...]}}

    识别模式:
    - LEFT JOIN m_p_code pX ON pX.code_type='xxx' AND pX.value=table.field
    - 子查询中 (SELECT name FROM m_p_code WHERE code_type='xxx' AND value=table.field)
    """
    # 结果: {table: {field: set of code_types}}
    table_field_code_types = defaultdict(lambda: defaultdict(set))

    for item in parsed_sqls:
        sql = item["sql"]
        tables = item["tables"]

        # 模式1: pX.code_type='xxx' and pX.value=alias.field
        # 先找 alias → table 的映射
        alias_to_table = {}
        alias_pattern = re.findall(
            r'\b(?:FROM|JOIN)\s+`?(\w[\w.]*)`?\s+(?:AS\s+)?(\w+)\b',
            sql, re.IGNORECASE
        )
        for table_name, alias in alias_pattern:
            if alias.lower() not in ('on', 'and', 'where', 'left', 'right',
                                       'inner', 'outer', 'join', 'cross', 'case',
                                       'when', 'then', 'else', 'end', 'select',
                                       'from', 'group', 'order', 'having', 'limit',
                                       'union', 'exists', 'between', 'like', 'in',
                                       'is', 'not', 'null', 'as', 'or', 'set'):
                # 清理表名
                clean_table = table_name.split('.')[-1] if '.' in table_name else table_name
                clean_table = clean_table.strip('`')
                alias_to_table[alias.lower()] = clean_table.lower()

        # 模式1a: pX.code_type='xxx' and pX.value=alias.field
        code_field_pattern = re.findall(
            r"(\w+)\.\s*`?code_type`?\s*=\s*'([^']+)'\s+and\s+\1\.\s*`?value`?\s*=\s*(\w+)\.(\w+)",
            sql, re.IGNORECASE
        )
        for p_alias, code_type, field_alias, field_name in code_field_pattern:
            normalized_ct = normalize_code_type(code_type)
            # 通过 alias 找到表名
            table = alias_to_table.get(field_alias.lower())
            if table:
                table_field_code_types[table][field_name.lower()].add(normalized_ct)
            else:
                # 可能 field_alias 就是表名
                table_field_code_types[field_alias.lower()][field_name.lower()].add(normalized_ct)

        # 模式1b: 子查询形式 (SELECT name from m_p_code cd where cd.code_type='xxx' and cd.value=table.field)
        subquery_pattern = re.findall(
            r"code_type\s*=\s*'([^']+)'\s+and\s+\w+\.\s*`?value`?\s*=\s*(\w+)\.(\w+)",
            sql, re.IGNORECASE
        )
        for code_type, field_alias, field_name in subquery_pattern:
            normalized_ct = normalize_code_type(code_type)
            table = alias_to_table.get(field_alias.lower())
            if table:
                table_field_code_types[table][field_name.lower()].add(normalized_ct)
            else:
                table_field_code_types[field_alias.lower()][field_name.lower()].add(normalized_ct)

    # 转换 set 为 list
    result = {}
    for table, fields in table_field_code_types.items():
        result[table] = {field: sorted(list(cts)) for field, cts in fields.items()}

    return result


def extract_hardcoded_enum_mappings(parsed_sqls: list[dict]) -> dict:
    """
    从 CASE WHEN 中提取硬编码枚举值: {table_name: {field_name: {value: label}}}

    同时也从子查询中提取:
    (SELECT name FROM m_p_code WHERE code_type='xxx' AND value=table.field) AS 列别名
    这里列别名本身就是业务含义的提示
    """
    all_case_mappings = defaultdict(lambda: defaultdict(dict))

    for item in parsed_sqls:
        for cm in item.get("case_when_mappings", []):
            field = cm["field"]
            # 尝试关联到表
            sql = item["sql"]
            tables = item["tables"]

            # 简单策略：找到 CASE WHEN 中的 field 属于哪个表
            # 通过 full_field_ref 推断
            full_ref = cm.get("full_field_ref", "")
            if '.' in full_ref:
                alias = full_ref.split('.')[0].lower()
                # 找 alias 对应的表
                alias_pattern = re.findall(
                    r'\b(?:FROM|JOIN)\s+`?(\w[\w.]*)`?\s+(?:AS\s+)?(\w+)\b',
                    sql, re.IGNORECASE
                )
                alias_to_table = {}
                for table_name, a in alias_pattern:
                    tn = table_name.split('.')[-1].strip('`').lower()
                    alias_to_table[a.lower()] = tn

                table = alias_to_table.get(alias)
                if table:
                    for v, label in cm["values"].items():
                        all_case_mappings[table][field][v] = label
                else:
                    # guess from tables
                    for t in tables:
                        all_case_mappings[t][field].update(cm["values"])
            else:
                # 无法确定表，分配给所有候选表
                for t in tables:
                    all_case_mappings[t][field].update(cm["values"])

    # 转换 defaultdict
    result = {}
    for table, fields in all_case_mappings.items():
        result[table] = {}
        for field, values in fields.items():
            if values:
                result[table][field] = dict(values)

    return result


def merge_mappings(code_type_mappings: dict, hardcoded_enums: dict) -> list[dict]:
    """
    合并两种映射，生成最终的结构化字段值映射

    输出格式:
    [
      {
        "table_name": "m_c_cons",
        "fields": [
          {
            "field_name": "status_code",
            "code_types": ["statusCode"],
            "hardcoded_values": {"0": "正常", "1": "暂停", "9": "销户"},
            "source": "case_when" | "m_p_code" | "both"
          }
        ]
      }
    ]
    """
    all_tables = set(list(code_type_mappings.keys()) + list(hardcoded_enums.keys()))

    result = []
    for table in sorted(all_tables):
        ct_fields = code_type_mappings.get(table, {})
        enum_fields = hardcoded_enums.get(table, {})

        all_fields = set(list(ct_fields.keys()) + list(enum_fields.keys()))

        fields_list = []
        for field in sorted(all_fields):
            code_types = ct_fields.get(field, [])
            hardcoded = enum_fields.get(field, {})

            if code_types and hardcoded:
                source = "both"
            elif hardcoded:
                source = "case_when"
            elif code_types:
                source = "m_p_code"
            else:
                continue

            fields_list.append({
                "field_name": field,
                "code_types": code_types,
                "hardcoded_values": hardcoded,
                "source": source
            })

        if fields_list:
            result.append({
                "table_name": table,
                "fields": fields_list
            })

    return result


def print_mapping_stats(mappings: list[dict]):
    """打印映射统计"""
    total_fields = sum(len(t["fields"]) for t in mappings)
    case_when_count = sum(1 for t in mappings for f in t["fields"] if f["source"] in ("case_when", "both"))
    mp_code_count = sum(1 for t in mappings for f in t["fields"] if f["source"] in ("m_p_code", "both"))

    print(f"\n📊 字段映射统计:")
    print(f"  涉及表数: {len(mappings)}")
    print(f"  涉及字段数: {total_fields}")
    print(f"  有 CASE WHEN 硬编码的字段: {case_when_count}")
    print(f"  有 m_p_code 关联的字段: {mp_code_count}")

    # 打印每张表的详情
    print(f"\n📋 详情:")
    for table in mappings:
        table_name = table["table_name"]
        fields = table["fields"]
        # 找出最有价值的字段（有硬编码值的）
        rich_fields = [f for f in fields if f["hardcoded_values"]]
        code_fields = [f for f in fields if f["code_types"]]

        if rich_fields:
            print(f"\n  [{table_name}] (有 {len(rich_fields)} 个含硬编码值的字段):")
            for f in rich_fields[:5]:  # 最多显示5个
                values_preview = {k: v for k, v in list(f["hardcoded_values"].items())[:3]}
                print(f"    - {f['field_name']}: {values_preview}")

        if code_fields and not rich_fields:
            print(f"  [{table_name}] (有 {len(code_fields)} 个 m_p_code 关联字段):")
            for f in code_fields[:3]:
                print(f"    - {f['field_name']}: code_types={f['code_types'][:3]}")


if __name__ == "__main__":
    input_file = os.path.join(os.path.dirname(__file__), "parsed_sqls.json")

    if not os.path.exists(input_file):
        print(f"❌ 未找到输入文件: {input_file}，请先运行 step1")
        exit(1)

    print("📖 正在加载 parsed_sqls.json ...")
    parsed_sqls = load_parsed_sqls(input_file)
    print(f"   已加载 {len(parsed_sqls)} 条 SQL")

    # 提取 m_p_code 映射
    print("\n🔍 提取 m_p_code 关联映射...")
    code_type_mappings = extract_field_code_type_mapping(parsed_sqls)
    ct_tables = len(code_type_mappings)
    ct_fields = sum(len(fields) for fields in code_type_mappings.values())
    print(f"   提取到 {ct_tables} 张表 {ct_fields} 个字段的 code_type 映射")

    # 提取硬编码枚举值
    print("\n🔍 提取 CASE WHEN 硬编码枚举值...")
    hardcoded_enums = extract_hardcoded_enum_mappings(parsed_sqls)
    he_tables = len(hardcoded_enums)
    he_fields = sum(len(fields) for fields in hardcoded_enums.values())
    print(f"   提取到 {he_tables} 张表 {he_fields} 个字段的硬编码枚举值")

    # 合并
    print("\n🔗 合并映射...")
    merged = merge_mappings(code_type_mappings, hardcoded_enums)
    print_mapping_stats(merged)

    # 保存
    output_file = os.path.join(os.path.dirname(__file__), "field_value_mappings.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"\n💾 已保存至: {output_file}")
