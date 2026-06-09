"""
Step 3: 从数据库下载 DDL
=========================
输入: parsed_sqls.json (提取表名列表) + 数据库连接
输出: raw_ddl.json

从 MySQL 数据库中执行 SHOW CREATE TABLE 获取每张表的完整 DDL
"""

import json
import os
import sys
import pymysql


def load_config():
    """加载数据库配置"""
    # 尝试从 app/config.py 导入
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))
    try:
        from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
    except ImportError:
        # 使用默认配置
        DB_HOST = '10.11.0.95'
        DB_PORT = 10050
        DB_USER = 'readonlyuser'
        DB_PASSWORD = 'reAd0n1@eR'
        DB_NAME = 'epmp'
    return DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME


def extract_table_names(parsed_sqls: list[dict]) -> list[str]:
    """从 parsed_sqls 中提取所有唯一的表名"""
    tables = set()
    for item in parsed_sqls:
        for t in item.get("tables", []):
            # 过滤掉数据库前缀 (db.table → table)
            if '.' in t:
                parts = t.split('.')
                # 保留完整引用
                if not parts[0].startswith('tmp_'):
                    tables.add(parts[0])  # schema/db name
                tables.add(parts[1])  # table name
            else:
                tables.add(t)

    # 过滤明显不是表名的 (SQL关键字、太短的)
    sql_keywords = {'select', 'from', 'where', 'join', 'left', 'right', 'inner',
                    'outer', 'cross', 'on', 'as', 'and', 'or', 'not', 'in', 'is',
                    'null', 'like', 'between', 'exists', 'case', 'when', 'then',
                    'else', 'end', 'group', 'order', 'by', 'having', 'limit',
                    'union', 'all', 'distinct', 'set', 'update', 'delete', 'insert',
                    'into', 'values', 'create', 'alter', 'drop', 'table', 'index',
                    'view', 'primary', 'key', 'foreign', 'references', 'constraint'}
    tables = {t for t in tables if t.lower() not in sql_keywords and len(t) > 1}
    tables = {t for t in tables if not t.isdigit()}

    return sorted(tables)


def get_create_table(connection, table_name: str) -> dict:
    """获取单张表的 CREATE TABLE DDL"""
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"SHOW CREATE TABLE `{table_name}`")
            result = cursor.fetchone()
            if result:
                return {
                    "table_name": table_name,
                    "ddl": result.get("Create Table", ""),
                    "status": "ok"
                }
            else:
                return {
                    "table_name": table_name,
                    "ddl": "",
                    "status": "not_found"
                }
    except pymysql.err.ProgrammingError as e:
        return {
            "table_name": table_name,
            "ddl": "",
            "status": f"error: {str(e)}"
        }
    except Exception as e:
        return {
            "table_name": table_name,
            "ddl": "",
            "status": f"error: {str(e)}"
        }


def download_all_ddls(table_names: list[str], db_config: tuple) -> list[dict]:
    """批量下载所有表的 DDL"""
    host, port, user, password, database = db_config
    ddls = []
    ok_count = 0
    fail_count = 0

    connection = pymysql.connect(
        host=host, port=port, user=user,
        password=password, database=database,
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10,
        read_timeout=30
    )

    print(f"🔗 已连接: {host}:{port}/{database}")
    print(f"📋 共需下载 {len(table_names)} 张表\n")

    try:
        for i, table_name in enumerate(table_names):
            print(f"  [{i + 1}/{len(table_names)}] 下载 {table_name} ...", end=" ")
            ddl_info = get_create_table(connection, table_name)
            ddls.append(ddl_info)

            if ddl_info["status"] == "ok":
                ok_count += 1
                ddl_len = len(ddl_info["ddl"])
                print(f"✅ ({ddl_len} chars)")
            else:
                fail_count += 1
                print(f"❌ {ddl_info['status']}")
    finally:
        connection.close()

    print(f"\n📊 下载完成: {ok_count} 成功, {fail_count} 失败")
    return ddls


def parse_ddl_columns(ddl: str) -> list[dict]:
    """从 DDL 中解析出列信息"""
    columns = []
    lines = ddl.split('\n')

    for line in lines:
        line = line.strip()
        # 跳过非列定义行
        if not line or line.startswith('CREATE') or line.startswith(')') or \
           line.startswith('PRIMARY') or line.startswith('KEY') or \
           line.startswith('UNIQUE') or line.startswith('INDEX') or \
           line.startswith('CONSTRAINT') or line.startswith('ENGINE') or \
           line.startswith('/*'):
            continue

        # 匹配列定义: `column_name` type ... COMMENT 'comment'
        match = re.match(r"`(\w+)`\s+(\w+(?:\([^)]*\))?)\s*(.*)", line)
        if match:
            col_name = match.group(1)
            col_type = match.group(2)
            rest = match.group(3)

            # 提取 COMMENT
            comment = ""
            comment_match = re.search(r"COMMENT\s+'([^']*)'", rest, re.IGNORECASE)
            if comment_match:
                comment = comment_match.group(1)

            # 判断是否可为空
            nullable = "NOT NULL" not in rest.upper()

            # 提取 DEFAULT
            default = None
            default_match = re.search(r"DEFAULT\s+'([^']*)'", rest, re.IGNORECASE)
            if default_match:
                default = default_match.group(1)
            else:
                default_match = re.search(r"DEFAULT\s+(\S+)", rest, re.IGNORECASE)
                if default_match:
                    default = default_match.group(1)

            columns.append({
                "field_name": col_name,
                "type": col_type,
                "comment": comment,
                "nullable": nullable,
                "default": default
            })

    return columns


if __name__ == "__main__":
    import re  # 上面的 parse_ddl_columns 需要 re

    input_file = os.path.join(os.path.dirname(__file__), "parsed_sqls.json")

    if not os.path.exists(input_file):
        print(f"❌ 未找到 {input_file}，请先运行 step1")
        sys.exit(1)

    # 加载 parsed_sqls
    with open(input_file, 'r', encoding='utf-8') as f:
        parsed_sqls = json.load(f)

    # 提取表名
    tables = extract_table_names(parsed_sqls)
    print(f"📦 从 {len(parsed_sqls)} 条 SQL 中提取到 {len(tables)} 张唯一的表")
    print(f"📋 表名列表:\n  " + "\n  ".join(tables[:20]) +
          (f"\n  ... 还有 {len(tables) - 20} 张" if len(tables) > 20 else ""))

    # 加载数据库配置
    db_config = load_config()

    # 下载 DDL
    print(f"\n⏳ 开始下载 DDL...")
    ddls = download_all_ddls(tables, db_config)

    # 解析每张表的列信息
    for ddl_info in ddls:
        if ddl_info["status"] == "ok" and ddl_info["ddl"]:
            ddl_info["columns"] = parse_ddl_columns(ddl_info["ddl"])

    # 保存 raw_ddl
    output_file = os.path.join(os.path.dirname(__file__), "raw_ddl.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(ddls, f, ensure_ascii=False, indent=2)

    print(f"\n💾 已保存至: {output_file}")
