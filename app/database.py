import pymysql
import pandas as pd
import re
from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
from logger import get_logger

_log = get_logger(__name__)

# ============================================================
# 安全校验：防止 AI 生成的 DDL/DML 被误执行
# ============================================================
_DANGEROUS_KEYWORDS = [
    'DROP', 'DELETE', 'INSERT', 'UPDATE',
    'CREATE', 'ALTER', 'TRUNCATE', 'GRANT',
    'REVOKE', 'REPLACE', 'LOAD', 'RENAME',
    'EXEC', 'EXECUTE', 'CALL', 'SET',
]

def _is_safe_sql(sql: str) -> tuple[bool, str]:
    """
    校验 SQL 是否安全（只读操作）。
    返回 (is_safe, reason)

    多层防护：
    1. 必须先剥离前导注释，再检查是否以 SELECT 或 EXPLAIN 开头
    2. 不能包含危险的 DDL/DML 关键字
    3. 注意：pymysql 默认 multi=False，已阻止多语句注入
    """
    # 先剥离前导注释（-- / # / /* */），再检查
    stripped = _strip_leading_comments(sql).strip()
    upper = stripped.upper()

    # 第一层：必须以 SELECT / EXPLAIN / WITH 开头
    if not (upper.startswith("SELECT") or upper.startswith("EXPLAIN")
            or upper.startswith("WITH")):
        return False, f"禁止执行非查询语句（仅允许 SELECT/EXPLAIN/WITH），开头为: {stripped[:50]}..."

    # 第二层：关键字黑名单（忽略大小写，使用词边界防止误判）
    for kw in _DANGEROUS_KEYWORDS:
        if re.search(rf'\b{kw}\b', upper):
            # EXPLAIN 后跟 DDL 也要拦截
            return False, f"SQL 包含危险关键字: {kw}，禁止执行"

    return True, "OK"

def _strip_leading_comments(sql: str) -> str:
    """剥离 SQL 前导的 -- / # 注释行、/* */ 块注释和空行，定位真正的 SQL 语句起始位置（用于安全检查）"""
    s = sql
    while s:
        # 跳过前导空白行
        m = re.match(r'^[ \t]*(\r?\n|$)', s)
        if m:
            s = s[m.end():]
            continue
        # 跳过 -- 单行注释（含整行）
        m = re.match(r'^[ \t]*--[^\r\n]*\r?\n', s)
        if m:
            s = s[m.end():]
            continue
        # 跳过 # 单行注释（MySQL 兼容）
        m = re.match(r'^[ \t]*#[^\r\n]*\r?\n', s)
        if m:
            s = s[m.end():]
            continue
        # 跳过 /* ... */ 块注释
        m = re.match(r'^[ \t]*/\*.*?\*/\s*', s, re.DOTALL)
        if m:
            s = s[m.end():]
            continue
        break
    return s


def extract_and_clean_sql(text):
    """提取纯净 SQL，多层兜底确保不丢弃有效候选"""
    raw_sql = None

    # 第一层：标准 markdown 代码块提取
    # ```sql\n...\n```  或  ```sql\n...```（无尾部换行）
    match = re.search(r"```sql\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        raw_sql = match.group(1).strip()

    # 第二层：``` 无语言标记
    if not raw_sql:
        match = re.search(r"```\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
        if match:
            raw_sql = match.group(1).strip()

    # 第三层：直接以 SELECT 或 WITH 开头（LLM 可能不用 markdown 包裹）
    if not raw_sql:
        stripped = text.strip()
        if stripped.upper().startswith("SELECT") or stripped.upper().startswith("WITH"):
            raw_sql = stripped

    # 第四层：文本中任意位置找到 SELECT 语句
    if not raw_sql:
        match = re.search(r'\bSELECT\b.+?\bFROM\b', text, re.DOTALL | re.IGNORECASE)
        if match:
            # 从 SELECT 开始截取到文本末尾
            start = match.start()
            raw_sql = text[start:].strip()

    if not raw_sql:
        return None

    # 安全校验：只拦截真正的危险操作，非 SELECT/WITH 前缀才拒绝
    is_safe, reason = _is_safe_sql(raw_sql)
    if not is_safe:
        _log.warning("安全拦截: %s（原始开头: %.50s）", reason, raw_sql[:50])
        return None

    # 数据隔离规则
    raw_sql = re.sub(r"org_no\s*=\s*'([^']+)'", r"org_no LIKE '\1%'", raw_sql, flags=re.IGNORECASE)
    return raw_sql


def get_explain_plan(sql_query):
    is_safe, reason = _is_safe_sql(sql_query)
    if not is_safe:
        _log.warning("安全拦截 EXPLAIN: %s", reason)
        return None, f"SQL_ERROR: {reason}"

    explain_sql = f"EXPLAIN {sql_query}"
    try:
        connection = pymysql.connect(
            host=DB_HOST, port=DB_PORT, user=DB_USER,
            password=DB_PASSWORD, database=DB_NAME,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=5,
            read_timeout=30
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
        err_code = e.args[0] if e.args else 0
        _log.warning("SQL 语法/字段错误 [%s]: %s", err_code, e)
        return None, f"SQL_ERROR: SQL 语法或字段错误: {str(e)}"
    except pymysql.err.OperationalError as e:
        err_code = e.args[0] if e.args else 0
        # MySQL 错误码 1052-1242 等是语法/字段问题，不应归类为连接异常
        if err_code in (1052, 1054, 1060, 1062, 1064, 1091, 1146, 1242):
            _log.warning("SQL 语法/字段错误(OperationalError包装)[%s]: %s", err_code, e)
            return None, f"SQL_ERROR: SQL 语法或字段错误: {str(e)}"
        _log.error("数据库连接/网络异常 [%s]: %s", err_code, e)
        return None, f"SYS_ERROR: 数据库连接/网络异常: {str(e)}"
    except Exception as e:
        _log.exception("数据库系统未知异常")


def execute_export_sql(sql_query, max_rows=50000):
    """
    【专为大数据导出设计的底层通道】
    不再做 AI 拦截，强制将数据库超时时间拉长至 1200 秒 (20分钟)
    默认上限 50000 行，防止 OOM。
    """
    # 安全校验：拒绝非 SELECT 语句
    is_safe, reason = _is_safe_sql(sql_query)
    if not is_safe:
        _log.warning("安全拦截 EXPORT: %s", reason)
        return None, f"安全拦截: {reason}"

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