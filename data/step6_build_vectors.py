"""
Step 6: 构建向量数据库 (委托 buildVector)
==========================================
实际训练逻辑在 buildVector/build_vector_db.py 中。
此脚本作为 data/ 流水线的一部分，直接调用 buildVector。
"""

import os
import sys
import subprocess


def main():
    data_dir = os.path.dirname(os.path.abspath(__file__))
    build_script = os.path.join(data_dir, "..", "buildVector", "build_vector_db.py")

    if not os.path.exists(build_script):
        print(f"❌ 未找到构建脚本: {build_script}")
        sys.exit(1)

    print("🚀 调用 buildVector/build_vector_db.py ...")
    result = subprocess.run(
        [sys.executable, build_script],
        env={**os.environ, "PYTHONIOENCODING": "utf-8"}
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
