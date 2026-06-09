import pymysql
import pandas as pd
import re
from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
from logger import get_logger

_log = get_logger(__name__)

def extract_and_clean_sql(text):
    """提取纯净 SQL，只做 org_no 的安全隔离替换，不强制加 LIMIT"""
    raw_sql = None
    match = re.search(r"```sql\n(.*?)\n```", text, re.DOTALL | re.IGNORECASE)
    if match:
        raw_sql = match.group(1).strip()
    elif text.strip().upper().startswith("SELECT"):
        raw_sql = text.strip()

    if not raw_sql:
        return None

    # 保留数据隔离规则
    raw_sql = re.sub(r"org_no\s*=\s*'([^']+)'", r"org_no LIKE '\1%'", raw_sql, flags=re.IGNORECASE)
    return raw_sql


def get_explain_plan(sql_query):
    if not sql_query.strip().upper().startswith("SELECT"):
        return None, "SQL_ERROR: 非 SELECT 语句，跳过 EXPLAIN 审查。"

    explain_sql = f"EXPLAIN {sql_query}"
    try:
        connection = pymysql.connect(
            host=DB_HOST, port=DB_PORT, user=DB_USER,
            password=DB_PASSWORD, database=DB_NAME,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=5,
            read_timeout=15
        )
        with connection.cursor() as cursor:
            cursor.execute(explain_sql)
            result = cursor.fetchall()
        connection.close()

        if not result:
            return None, "SQL_ERROR: 未获取到执行计划。"

        # ... (解析逻辑保持不变) ...
        plan_str = ""
        for i, row in enumerate(result):
            plan_str += f"步骤 {i + 1}:\n"
            for k, v in row.items():
                plan_str += f"  - {k}: {v}\n"
        return plan_str, None

    except pymysql.err.ProgrammingError as e:
        _log.warning("SQL 语法/字段错误: %s", e)
        return None, f"SQL_ERROR: SQL 语法或字段错误: {str(e)}"
    except pymysql.err.OperationalError as e:
        _log.error("数据库连接/网络异常: %s", e)
        return None, f"SYS_ERROR: 数据库连接/网络异常: {str(e)}"
    except Exception as e:
        _log.exception("数据库系统未知异常")


def execute_export_sql(sql_query, max_rows=50000):
    """
    【专为大数据导出设计的底层通道】
    不再做 AI 拦截，强制将数据库超时时间拉长至 1200 秒 (20分钟)
    默认上限 50000 行，防止 OOM。
    """
    # 安全限制：无 LIMIT 时自动追加
    if "limit" not in sql_query.lower():
        sql_query = sql_query.rstrip().rstrip(';') + f" LIMIT {max_rows}"
    try:
        connection = pymysql.connect(
            host=DB_HOST, port=DB_PORT, user=DB_USER,
            password=DB_PASSWORD, database=DB_NAME,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=10,
            read_timeout=1200  # 👈 核心参数：20分钟无响应才会报超时
        )
        with connection.cursor() as cursor:
            cursor.execute(sql_query)
            result = cursor.fetchall()
        connection.close()

        if not result:
            return pd.DataFrame(), None
        return pd.DataFrame(result), None

    except Exception as e:
        _log.exception("数据库导出执行异常")
        return None, f"数据库导出执行异常: {str(e)}"