"""
截断 final_super_schema_by_ai.json 中过大的枚举值列表
超过 30 个值的只保留前 20 个常用值 + 备注
避免 Coder Prompt 因超长枚举值而超 token 限制
"""
import json
import os
import re

MAX_VALUES = 20  # 最多保留的枚举值数量

def truncate():
    data_dir = os.path.dirname(os.path.abspath(__file__))
    schema_path = os.path.join(data_dir, 'final_super_schema_by_ai.json')

    with open(schema_path, 'r', encoding='utf-8') as f:
        schema = json.load(f)

    truncated_count = 0

    for table in schema:
        for field in table.get('fields', []):
            comment = field.get('comment', '') or ''

            # 匹配 "枚举: v1=n1, v2=n2, ..." 部分
            match = re.search(r'枚举: (.+)$', comment)
            if not match:
                continue

            values_str = match.group(1)
            values = values_str.split(', ')

            if len(values) <= MAX_VALUES:
                continue

            # 保留前 MAX_VALUES 个值
            kept = values[:MAX_VALUES]
            removed = len(values) - MAX_VALUES
            new_enum = ', '.join(kept) + f'...等{len(values)}项（完整列表见 m_p_code 表 code_type=对应字典）'

            new_comment = comment[:match.start(1)] + new_enum
            field['comment'] = new_comment
            truncated_count += 1
            print(f'  [{table["table_name"]}] {field["field_name"]}: {len(values)} → {MAX_VALUES}+ (截断 {removed} 项)')

    # 保存
    with open(schema_path, 'w', encoding='utf-8') as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)

    print(f'\n截断完成: {truncated_count} 个字段')
    return schema


if __name__ == '__main__':
    truncate()
