"""
同义词扩展脚本
==============
从 domain_synonyms.json 读取领域同义词词典，
对 few_shot_examples.json 中的每个案例做关键词扩展，
输出 expanded_few_shot_examples.json。

用法:
  python expand_keywords.py                      # 扩展 data/ 内的 few_shot_examples.json
  python expand_keywords.py --input ../app/few_shot_examples.json --output ../app/few_shot_expanded.json
"""

import json
import os
import sys
import argparse

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
SYNONYM_FILE = os.path.join(DATA_DIR, "domain_synonyms.json")
INPUT_FILE = os.path.join(DATA_DIR, "few_shot_examples.json")
OUTPUT_FILE = os.path.join(DATA_DIR, "expanded_few_shot_examples.json")


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(data, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def build_synonym_map(synonyms_dict: dict) -> dict:
    """
    将同义词词典展开为双向映射:
      key → [synonyms...]   (原始)
      synonym → key         (反向，用于识别变体)
    """
    reverse = {}
    for root, variants in synonyms_dict.items():
        if root.startswith("_"):
            continue
        for v in variants:
            reverse[v] = root
    return reverse


def expand_keywords_for_example(example: dict, synonyms: dict, reverse_map: dict) -> list[str]:
    """
    对单个案例做关键词扩展:
    1. 收集案例自身文本 (question + business_rules + search_keywords)
    2. 若文本中出现同义词词典的 key 或其 variant → 加入该组的所有同义词
    3. 去重返回
    """
    text = " ".join([
        example.get("question", ""),
        example.get("business_rules", ""),
        " ".join(example.get("search_keywords", []))
    ])

    existing_kw = set(example.get("search_keywords", []))
    expanded = set(existing_kw)

    # 遍历每个根词及其变体
    for root, variants in synonyms.items():
        if root.startswith("_"):
            continue
        # 把根词自身也加入匹配范围
        all_terms = [root] + variants
        hit = any(term in text for term in all_terms)
        if hit:
            expanded.update(variants)
            expanded.add(root)

    # 也通过反向映射检查：如果文本中出现某个 variant，找到其 root 并展开
    for variant, root in reverse_map.items():
        if variant in text and variant not in existing_kw:
            # 把该组所有词加入
            expanded.add(root)
            if root in synonyms:
                expanded.update(synonyms[root])

    return sorted(expanded)


def main():
    parser = argparse.ArgumentParser(description="扩展 few-shot 案例的 search_keywords")
    parser.add_argument("--input", type=str, default=INPUT_FILE, help="输入 JSON 路径")
    parser.add_argument("--output", type=str, default=OUTPUT_FILE, help="输出 JSON 路径")
    parser.add_argument("--synonyms", type=str, default=SYNONYM_FILE, help="同义词词典路径")
    parser.add_argument("--dry-run", action="store_true", help="只预览，不写入")
    args = parser.parse_args()

    # 加载
    synonyms = load_json(args.synonyms)
    examples = load_json(args.input)
    reverse_map = build_synonym_map(synonyms)

    # 过滤掉注释字段
    synonyms = {k: v for k, v in synonyms.items() if not k.startswith("_")}

    print(f"词典: {len(synonyms)} 个词根")
    print(f"案例: {len(examples)} 条")
    print(f"反向映射: {len(reverse_map)} 个变体 → 词根")
    print()

    # 扩展
    stats = {"expanded": 0, "unchanged": 0, "total_added": 0}
    for example in examples:
        old_kw = set(example.get("search_keywords", []))
        new_kw = expand_keywords_for_example(example, synonyms, reverse_map)
        added = len(new_kw) - len(old_kw)
        example["search_keywords"] = new_kw
        if added > 0:
            stats["expanded"] += 1
            stats["total_added"] += added
            title = example.get("title", "?")
            added_kws = set(new_kw) - old_kw
            print(f"  +{added:3d} 关键词 | {title:<20s} | 新增: {', '.join(sorted(added_kws)[:5])}...")
        else:
            stats["unchanged"] += 1

    print()
    print(f"已扩展: {stats['expanded']} 条, 未变化: {stats['unchanged']} 条, 共新增 {stats['total_added']} 个关键词")

    if args.dry_run:
        print("\n[Dry-run] 不写入文件。移除 --dry-run 以执行。")
    else:
        save_json(examples, args.output)
        print(f"已保存至: {args.output}")


if __name__ == "__main__":
    main()
