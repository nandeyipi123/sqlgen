"""
领域规则校验器 (Domain Validator)
================================
不调 LLM，纯规则匹配（~5ms）。拦截电力营销 SQL 的已知错误模式。

设计原则：
- 每条规则 = 触发条件 + 错误级别 + 修复建议
- ERROR: 阻断流水线，必须 Fixer 修复
- WARN: 放行但记录，供 Reviewer 和用户参考
- 规则可累加：每次发现新错误模式，加一条即可
"""

import re
from typing import List, Dict, Optional
from logger import get_logger

_log = get_logger(__name__)


# ============================================================
# 规则定义
# ============================================================

class DomainRule:
    """一条领域规则"""
    def __init__(self, rule_id: str, name: str, severity: str,
                 description: str, fix_suggestion: str,
                 check_fn):
        self.rule_id = rule_id
        self.name = name
        self.severity = severity  # "ERROR" | "WARN"
        self.description = description
        self.fix_suggestion = fix_suggestion
        self._check = check_fn

    def check(self, sql: str, question: str, tables: List[str]) -> bool:
        """返回 True 表示规则被触发（有问题）"""
        try:
            return self._check(sql, question, tables)
        except Exception as e:
            _log.warning("规则 %s 执行异常: %s", self.rule_id, e)
            return False


# ---- 辅助函数 ----

def _has_table(tables: List[str], target: str) -> bool:
    """检查表列表中是否包含目标表（忽略大小写）"""
    target_lower = target.lower()
    return any(target_lower in t.lower() for t in tables)


def _keyword_in_question(question: str, *keywords: str) -> bool:
    """检查用户问题中是否包含任一关键词"""
    return any(kw in question for kw in keywords)


def _keyword_not_in_question(question: str, *keywords: str) -> bool:
    """检查用户问题中是否不包含任一关键词"""
    return all(kw not in question for kw in keywords)


def _has_derived_table_without_org_no(sql: str) -> bool:
    """检查是否有派生表/子查询内部缺少 org_no LIKE 过滤"""
    # 找到所有 (SELECT ... FROM ...) 子查询
    # 简化检测：找 LEFT JOIN ( 或 JOIN ( 后的 SELECT 块
    subqueries = re.findall(
        r'\(\s*SELECT\s+.*?\bFROM\b\s+(\w+)',
        sql, re.DOTALL | re.IGNORECASE
    )
    # 检查每个子查询的 WHERE 是否包含 org_no
    # 更精确的做法：找完整的子查询块，检查 WHERE
    paren_depth_pattern = re.findall(
        r'\(\s*SELECT\s+.+?\bFROM\b\s+\w+.+?\)',
        sql, re.DOTALL | re.IGNORECASE
    )
    for sub in paren_depth_pattern:
        if 'org_no' not in sub.lower():
            return True
    return False


def _has_exists_on_large_table(sql: str) -> bool:
    """检查是否对 m_r_data_arc 等大表使用了 EXISTS 关联子查询"""
    large_tables = ['m_r_data_arc', 'm_a_rcvbl_flow', 'm_a_rcvbl_flow_arc']
    sql_lower = sql.lower()
    for tbl in large_tables:
        # 找 EXISTS (SELECT ... FROM tbl WHERE ...关联外部...)
        pattern = rf'exists\s*\(\s*select\s+.+?\bfrom\b\s+{tbl}\b'
        if re.search(pattern, sql_lower, re.DOTALL):
            return True
    return False


# ============================================================
# 规则库
# ============================================================

DOMAIN_RULES: List[DomainRule] = [
    # ---- 账务表规则 ----
    DomainRule(
        rule_id="R001",
        name="月汇总场景禁止用 m_a_rcved_flow",
        severity="ERROR",
        description="m_a_rcved_flow 是逐笔收费明细表，月电费汇总应直接从 m_a_rcvbl_flow.rcved_amt 取",
        fix_suggestion="将 m_a_rcved_flow 替换为 (SELECT ... FROM m_a_rcvbl_flow UNION ALL SELECT ... FROM m_a_rcvbl_flow_arc)，使用 rcved_amt 字段按 rcvbl_ym 过滤",
        check_fn=lambda sql, q, tables:
            _has_table(tables, 'm_a_rcved_flow')
            and 'm_a_rcved_flow' in sql.lower()           # ← 必须实际使用了这张表
            and _keyword_in_question(q, '月电费', '汇总', '统计', '月均', '明细')
            and _keyword_not_in_question(q, '收费明细', '收费台账', '逐笔', '收款记录')
    ),
    DomainRule(
        rule_id="R002",
        name="禁止用 rcved_ym 做月度电费过滤",
        severity="ERROR",
        description="rcved_ym 是收款到账月份（用户6月交的是5月电费），月度电费汇总应使用 rcvbl_ym（账单归属月份）",
        fix_suggestion="将 rcved_ym 替换为 rcvbl_ym",
        check_fn=lambda sql, q, tables:
            'rcved_ym' in sql.lower()
            and _keyword_not_in_question(q, '收费明细', '到账', '实收日期', '逐笔', '台账', '缴款日期')
    ),
    DomainRule(
        rule_id="R003",
        name="应收流水表遗漏历史归档表 UNION ALL",
        severity="WARN",
        description="m_a_rcvbl_flow 的已结清账单会定期归档到 m_a_rcvbl_flow_arc，不 UNION ALL 会导致历史数据缺失",
        fix_suggestion="添加 UNION ALL m_a_rcvbl_flow_arc，并复制相同的 WHERE 过滤条件",
        check_fn=lambda sql, q, tables:
            _has_table(tables, 'm_a_rcvbl_flow')
            and not _has_table(tables, 'm_a_rcvbl_flow_arc')
            and _keyword_in_question(q, '汇总', '统计', '总额', '总计', '欠费', '余额', '所有', '全部',
                                    '月电费', '电费明细', '应收', '实收')
    ),
    DomainRule(
        rule_id="R004",
        name="应收流水表按 rcvbl_ym 过滤时遗漏 rg_cd 过滤",
        severity="WARN",
        description="应收账款查询应同时具备 org_no 过滤和 rcvbl_ym 条件",
        fix_suggestion="确保 WHERE 中包含 org_no LIKE 'xxx%' 和 rcvbl_ym = 'YYYYMM'",
        check_fn=lambda sql, q, tables:
            (_has_table(tables, 'm_a_rcvbl_flow') or _has_table(tables, 'm_a_rcvbl_flow_arc'))
            and 'rcvbl_ym' not in sql.lower()
            and _keyword_in_question(q, '202', '月')  # 有时间维度的查询
    ),

    # ---- 快照表规则 ----
    DomainRule(
        rule_id="R005",
        name="m_e_cons_snap_arc 查询必须指定 ym",
        severity="ERROR",
        description="m_e_cons_snap_arc 是按月快照大表（亿级），不带 ym 过滤会导致全表扫描",
        fix_suggestion="在 WHERE 中明确指定 e.ym = 'YYYYMM'（具体月份值）",
        check_fn=lambda sql, q, tables:
            _has_table(tables, 'm_e_cons_snap_arc')
            and not re.search(r'(ym|YM)\s*[=<>]', sql)
    ),
    DomainRule(
        rule_id="R006",
        name="m_e_cons_snap_arc 子查询需要独立 org_no 过滤",
        severity="WARN",
        description="涉及 m_e_cons_snap_arc 的每个子查询都必须独立添加 org_no LIKE 过滤",
        fix_suggestion="在每个使用 m_e_cons_snap_arc 的子查询/派生表中独立添加 org_no LIKE 'xxx%'",
        check_fn=lambda sql, q, tables:
            _has_table(tables, 'm_e_cons_snap_arc')
            and _has_derived_table_without_org_no(sql)
    ),

    # ---- 大表性能规则 ----
    DomainRule(
        rule_id="R007",
        name="大表禁止 EXISTS 关联子查询",
        severity="ERROR",
        description="对 m_r_data_arc、m_a_rcvbl_flow 等亿级大表使用 EXISTS 会导致 DEPENDENT SUBQUERY，逐行扫描数亿行",
        fix_suggestion="改为 INNER JOIN：先用小表（如 m_e_cons_snap_arc）过滤出有效 ID，再 JOIN 大表",
        check_fn=lambda sql, q, tables:
            _has_exists_on_large_table(sql)
    ),

    # ---- 字典表规则 ----
    DomainRule(
        rule_id="R008",
        name="m_p_code 字典 JOIN 缺少 take_effect_flag",
        severity="WARN",
        description="m_p_code 有生效/失效标记，不加 take_effect_flag = 1 可能查到已停用的字典值",
        fix_suggestion="在 JOIN m_p_code 的 ON 条件中添加 AND px.take_effect_flag = 1",
        check_fn=lambda sql, q, tables:
            _has_table(tables, 'm_p_code')
            and 'take_effect_flag' not in sql.lower()
    ),

    # ---- 用户过滤规则 ----
    DomainRule(
        rule_id="R009",
        name="用户列表查询缺少 status_code 过滤",
        severity="WARN",
        description="查询用户列表时未过滤已销户/归档用户（status_code NOT IN ('0','1','2','3')）",
        fix_suggestion="在 WHERE 中添加 a.status_code IN ('0', '1', '2', '3')",
        check_fn=lambda sql, q, tables:
            _has_table(tables, 'm_c_cons')
            and 'status_code' not in sql.lower()
            and _keyword_in_question(q, '用户', '所有', '列表', '查询')
            and _keyword_not_in_question(q, '销户', '归档', '指定用户', 'cons_no')
    ),

    # ---- JOIN 条件规则 ----
    DomainRule(
        rule_id="R010",
        name="ac_org 关联条件检查",
        severity="WARN",
        description="标准关联模式为 a.org_no = o.id（不是 o.code），这个项目中 org_no 存储的是 ac_org 的 id",
        fix_suggestion="确认 JOIN 条件为 a.org_no = o.id（不是 o.code 或 o.org_no）",
        check_fn=lambda sql, q, tables:
            _has_table(tables, 'ac_org')
            and re.search(r'org_no\s*=\s*o\.(code|org_no)', sql, re.IGNORECASE) is not None
    ),

    # ---- 数据隔离规则 ----
    DomainRule(
        rule_id="R011",
        name="SQL 整体缺少 org_no 数据隔离",
        severity="ERROR",
        description="电力营销系统必须按组织隔离数据，SQL 必须包含 org_no LIKE 'xxx%' 或 org_no = 'xxx'。除纯字典查询外，所有查询都需要 org_no 过滤",
        fix_suggestion="在主查询 WHERE 中添加 org_no LIKE 'xxx%' 条件",
        check_fn=lambda sql, q, tables:
            'org_no' not in sql.lower()
            # 排除纯字典查询（只查 m_p_code 等字典表，无 org_no 概念）
            and len([t for t in tables if t.lower() not in ('m_p_code',)]) > 0
            # 排除 EXPLAIN 语句
            and not sql.strip().upper().startswith('EXPLAIN')
    ),

    # ---- 采集点关联规则 ----
    DomainRule(
        rule_id="R012",
        name="m_r_coll_obj 禁止直接 JOIN m_c_cons（没有 cons_id 列）",
        severity="ERROR",
        description="m_r_coll_obj 没有 cons_id 字段！正确关联路径: m_r_coll_obj.meter_id → m_c_meter.id → m_c_meter_mp_rela.meter_id → m_c_meter_mp_rela.mp_id → m_c_mp.id → m_c_sp.id → m_c_sp.cons_id → m_c_cons.id。禁止写 co.cons_id = c.id",
        fix_suggestion="删除对 m_r_coll_obj 的 cons_id 引用。改为完整的 JOIN 链: m_c_cons → m_c_sp(cons_id) → m_c_mp(sp_id+cons_id) → m_c_meter_mp_rela(mp_id) → m_c_meter(id) → m_r_coll_obj(meter_id) → m_r_cp(cp_no)",
        check_fn=lambda sql, q, tables:
            _has_table(tables, 'm_r_coll_obj')
            and re.search(r'(coll_obj|co2?|obj|f)\s*\.\s*cons_id', sql, re.IGNORECASE) is not None
    ),
    DomainRule(
        rule_id="R013",
        name="采集对象查询缺少关键中间表",
        severity="WARN",
        description="查询涉及 m_r_coll_obj/m_r_cp 等采集表时，需要 m_c_sp、m_c_meter_mp_rela、m_c_meter 等中间表才能正确关联到用户",
        fix_suggestion="确保检索/表结构上下文中包含完整的采集关联链: m_c_sp, m_c_meter_mp_rela, m_c_meter",
        check_fn=lambda sql, q, tables:
            (_has_table(tables, 'm_r_coll_obj') or _has_table(tables, 'm_r_cp'))
            and (not _has_table(tables, 'm_c_sp')
                 or not _has_table(tables, 'm_c_meter_mp_rela')
                 or not _has_table(tables, 'm_c_meter'))
    ),

    # ---- 总电量来源规则 ----
    DomainRule(
        rule_id="R014",
        name="总电量禁止从 m_r_data_arc 取",
        severity="ERROR",
        description="总电量（总有功）必须从 m_a_rcvbl_flow.t_pq 取，不能从 m_r_data_arc（抄表数据）取。m_r_data_arc 按计量点存储，SUM 会导致总电量重复累加（多表用户多倍）",
        fix_suggestion="删除 m_r_data_arc 子查询中的 read_type_code='11' 分支，SELECT 中改用 m_a_rcvbl_flow.t_pq 的 SUM 结果作为总电量",
        check_fn=lambda sql, q, tables:
            _has_table(tables, 'm_r_data_arc')
            and _has_table(tables, 'm_a_rcvbl_flow')
            and bool(re.search(r"read_type_code\s*=\s*'11'", sql, re.IGNORECASE))
            and bool(re.search(r'(当月有功总|总有功|total_pq|有功总电量)', sql, re.IGNORECASE))
    ),
]


# ============================================================
# 校验引擎
# ============================================================

def validate(sql: str, question: str, tables: Optional[List[str]] = None) -> dict:
    """
    对生成的 SQL 执行所有领域规则校验。

    参数:
        sql: 生成的 SQL 语句
        question: 用户原始需求
        tables: 涉及的表名列表（从 retrieve_and_plan 获取）

    返回:
        {
            "passed": bool,
            "errors": [{"rule_id": "R001", "name": "...", "fix_suggestion": "..."}],
            "warnings": [{"rule_id": "R003", "name": "...", "fix_suggestion": "..."}]
        }
    """
    if tables is None:
        tables = []

    errors = []
    warnings = []

    for rule in DOMAIN_RULES:
        if rule.check(sql, question, tables):
            issue = {
                "rule_id": rule.rule_id,
                "name": rule.name,
                "severity": rule.severity,
                "description": rule.description,
                "fix_suggestion": rule.fix_suggestion,
            }
            if rule.severity == "ERROR":
                errors.append(issue)
                _log.info("领域规则拦截 [%s]: %s", rule.rule_id, rule.name)
            else:
                warnings.append(issue)
                _log.info("领域规则提醒 [%s]: %s", rule.rule_id, rule.name)

    passed = len(errors) == 0

    if not passed:
        _log.warning("领域校验未通过: %d 个错误, %d 个警告", len(errors), len(warnings))

    return {
        "passed": passed,
        "errors": errors,
        "warnings": warnings,
    }


def format_validation_message(result: dict) -> str:
    """将校验结果格式化为 Fixer 可读的错误消息"""
    parts = []

    if result["errors"]:
        parts.append("【领域规则错误 — 必须修复】")
        for e in result["errors"]:
            parts.append(f"- [{e['rule_id']}] {e['name']}")
            parts.append(f"  原因: {e['description']}")
            parts.append(f"  修复: {e['fix_suggestion']}")

    if result["warnings"]:
        parts.append("\n【领域规则提醒 — 建议检查】")
        for w in result["warnings"]:
            parts.append(f"- [{w['rule_id']}] {w['name']}")
            parts.append(f"  说明: {w['description']}")

    return "\n".join(parts)
