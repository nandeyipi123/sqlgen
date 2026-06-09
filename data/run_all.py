"""
一键运行完整数据清洗流水线
==========================

Usage:
    python run_all.py                    # 运行全部 6 步
    python run_all.py --step 1           # 只运行第 1 步
    python run_all.py --step 1,2,3       # 运行第 1-3 步
    python run_all.py --skip-step 4,5    # 跳过第 4-5 步 (AI 步骤)
    python run_all.py --dry-run          # 只打印计划，不执行
"""

import os
import sys
import subprocess
import argparse
import json


STEPS = {
    1: {
        "name": "解析 SQL 文件",
        "script": "step1_parse_sqls.py",
        "input": "../data/合并.sql",
        "output": "parsed_sqls.json",
        "description": "从合并.sql 中提取结构化 SQL 信息（表名、映射、关键词）"
    },
    2: {
        "name": "提取字段值映射",
        "script": "step2_extract_mappings.py",
        "input": "parsed_sqls.json",
        "output": "field_value_mappings.json",
        "description": "从 CASE WHEN 和 m_p_code 中提取字段→值映射"
    },
    3: {
        "name": "下载数据库 DDL",
        "script": "step3_download_ddl.py",
        "input": "parsed_sqls.json + MySQL",
        "output": "raw_ddl.json",
        "description": "从 MySQL 下载 SHOW CREATE TABLE"
    },
    4: {
        "name": "AI 增强 Schema",
        "script": "step4_ai_enhance_schema.py",
        "input": "raw_ddl.json + field_value_mappings.json + DeepSeek API",
        "output": "final_super_schema_by_ai.json",
        "description": "AI 将 DDL 与 SQL 提取的映射融合，生成增强 Schema"
    },
    5: {
        "name": "AI 增强 Few-Shot",
        "script": "step5_ai_enhance_fewshot.py",
        "input": "parsed_sqls.json + final_super_schema_by_ai.json + DeepSeek API",
        "output": "few_shot_examples.json",
        "description": "AI 反向工程 SQL，生成高质量 Few-Shot 样本"
    },
    6: {
        "name": "构建向量数据库",
        "script": "step6_build_vectors.py",
        "input": "final_super_schema_by_ai.json + few_shot_examples.json + Ollama",
        "output": "schema_chroma_db/ + few_shot_chroma_db/",
        "description": "构建 ChromaDB 向量库，部署到 app/ 目录"
    },
}


def check_prerequisites(step_num: int) -> bool:
    """检查前置条件"""
    data_dir = os.path.dirname(os.path.abspath(__file__))

    if step_num == 1:
        input_file = os.path.join(data_dir, "..", "data", "合并.sql")
        return os.path.exists(input_file)

    prereqs = {
        2: ["parsed_sqls.json"],
        3: ["parsed_sqls.json"],
        4: ["raw_ddl.json", "field_value_mappings.json"],
        5: ["parsed_sqls.json", "final_super_schema_by_ai.json"],
        6: ["final_super_schema_by_ai.json"],
    }

    for prereq in prereqs.get(step_num, []):
        if not os.path.exists(os.path.join(data_dir, prereq)):
            print(f"  ⚠️ 缺少前置文件: {prereq}，请先运行前面的步骤")
            return False
    return True


def run_step(step_num: int, data_dir: str) -> bool:
    """运行单个步骤"""
    step = STEPS[step_num]
    script_path = os.path.join(data_dir, step["script"])

    if not os.path.exists(script_path):
        print(f"  ❌ 脚本不存在: {script_path}")
        return False

    if not check_prerequisites(step_num):
        return False

    print(f"\n{'=' * 60}")
    print(f"Step {step_num}: {step['name']}")
    print(f"  📝 {step['description']}")
    print(f"  📥 输入: {step['input']}")
    print(f"  📤 输出: {step['output']}")
    print(f"{'=' * 60}")

    try:
        result = subprocess.run(
            [sys.executable, script_path],
            cwd=data_dir,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            capture_output=False
        )
        if result.returncode == 0:
            print(f"✅ Step {step_num} 完成")
            return True
        else:
            print(f"❌ Step {step_num} 失败 (退出码: {result.returncode})")
            return False
    except Exception as e:
        print(f"❌ Step {step_num} 异常: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="SQL 知识库数据清洗流水线")
    parser.add_argument("--step", type=str, default=None,
                        help="只运行指定步骤 (如: 1 或 1,2,3)")
    parser.add_argument("--skip-step", type=str, default=None,
                        help="跳过指定步骤 (如: 4,5)")
    parser.add_argument("--dry-run", action="store_true",
                        help="只打印计划，不执行")
    parser.add_argument("--from-step", type=int, default=1,
                        help="从第几步开始 (默认: 1)")
    args = parser.parse_args()

    data_dir = os.path.dirname(os.path.abspath(__file__))

    # 决定要运行的步骤
    if args.step:
        steps_to_run = [int(s.strip()) for s in args.step.split(",")]
    else:
        steps_to_run = list(range(args.from_step, 7))

    if args.skip_step:
        skip_steps = set(int(s.strip()) for s in args.skip_step.split(","))
        steps_to_run = [s for s in steps_to_run if s not in skip_steps]

    # 验证步骤编号
    steps_to_run = [s for s in steps_to_run if 1 <= s <= 6]

    print("🚀 SQL 知识库数据清洗流水线")
    print(f"📋 执行计划: Step {', '.join(map(str, steps_to_run))}")
    print(f"📁 工作目录: {data_dir}")

    if args.dry_run:
        print("\n📋 详细计划:")
        for s in steps_to_run:
            step = STEPS[s]
            print(f"  Step {s}: {step['name']}")
            print(f"    输入: {step['input']}")
            print(f"    输出: {step['output']}")
            print(f"    描述: {step['description']}")
        print("\n💡 移除 --dry-run 参数以执行")
        return

    # 执行
    results = {}
    for s in steps_to_run:
        success = run_step(s, data_dir)
        results[s] = success
        if not success and s < 4:  # Step 1-3 失败则停止
            print(f"\n⛔ Step {s} 失败，流水线中断")
            break

    # 总结
    print(f"\n{'=' * 60}")
    print("📊 执行总结:")
    for s, success in results.items():
        status = "✅" if success else "❌"
        print(f"  {status} Step {s}: {STEPS[s]['name']}")

    # 检查输出文件
    print(f"\n📁 输出文件:")
    for s in steps_to_run:
        output = STEPS[s]["output"]
        # 可能有多个输出
        for out in output.split(" + "):
            out = out.strip()
            if "/" in out:  # 目录
                out_path = os.path.join(data_dir, out.rstrip('/'))
                if os.path.exists(out_path):
                    print(f"  ✅ {out_path}/")
                else:
                    print(f"  ❌ {out_path}/ (不存在)")
            else:
                out_path = os.path.join(data_dir, out)
                if os.path.exists(out_path):
                    size = os.path.getsize(out_path)
                    print(f"  ✅ {out} ({size:,} bytes)")
                else:
                    print(f"  ❌ {out} (不存在)")


if __name__ == "__main__":
    main()
