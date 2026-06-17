from functools import lru_cache
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import httpx
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL


@lru_cache(maxsize=4)
def get_llm(model_name: str, temperature: float, streaming: bool = True) -> ChatOpenAI:
    """创建 LLM 实例（按模型名+温度缓存，避免重复创建连接池）"""
    # 自定义 httpx 客户端：更长超时 + 连接池 + 重试
    http_client = httpx.Client(
        timeout=httpx.Timeout(300.0, connect=30.0),
        limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
    )
    return ChatOpenAI(
        model=model_name, api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL, temperature=temperature,
        streaming=streaming, max_retries=3, timeout=300,
        http_client=http_client,
    )


def get_llm_no_stream(model_name: str, temperature: float) -> ChatOpenAI:
    """非流式 LLM（用于大 prompt 场景，连接更稳定）"""
    return get_llm(model_name, temperature, streaming=False)

def get_planner_chain(llm):
    """已废弃：Planner 环节已改为直接合并案例表名，不再调 LLM。保留函数以兼容旧引用。"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", """DEPRECATED — 此链不再使用。"""),
        ("human", "{question}")
    ])
    return prompt | llm | StrOutputParser()

def get_coder_chain(llm):
    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是一个精通电力营销系统的 SQL 专家。根据表结构、领域知识和参考案例，生成可执行的 MySQL 5.7 SQL。

【表结构】：
{exact_schema_context}

【领域知识】（DBA 维护的表关系、关键原则、反模式）：
{domain_knowledge_context}

【参考案例】（按相关度排序，案例1最匹配）：
{few_shot_context}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
第零铁律：禁止编造字段、码值、表名（违反直接失败）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**你只能使用【表结构】和【领域知识】中明确列出的内容！**

字段名：
- ✅ 找到了 → 使用该字段
- ❌ 找不到 → 跳过该列，注释写 `-- 该列在当前表中无对应字段，已跳过`

码值/枚举值（WHERE x IN / CASE WHEN 中的字符串字面量）：
- 只使用【表结构】注释中明确写出的码值（如注释写 "12=有功总 13=有功峰"）
- 注释里没写具体码值 → 不要自己加 IN('01','02') 这种过滤
- 不要用 CASE WHEN 硬编码码值映射（如 '01'→'结清'），用 LEFT JOIN m_p_code 字典表

表名：
- 只使用【表结构】中存在的表。禁止凭空编造表名（如 m_c_contact、m_c_cons_contact_rela）
- 【表结构】里没有的表说明这个数据库不需要

**这是写死的规则，没有例外。**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ 致命规则（违反会导致查询结果错误）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**1. 表选择**：优先复用案例1的表结构。能少表不多表，能从一个表取的字段不要跨表。DDL 中带 ⚠️ 的字段指引必须遵守。

**2. JOIN 路径**：严格按【领域知识】中的 correct_patterns 关联表。`m_r_coll_obj` 没有 `cons_id` 列！采集点关联必须走完整链路。

**3. 数据隔离**：每个子查询内部独立添加 `org_no LIKE 'xxx%'`，最外层也需要。`ac_org` 关联用 `a.org_no = o.id`（不是 `o.code`）。

**4. 归档表**：涉及 `m_a_rcvbl_flow` 的任何汇总/统计查询必须 `UNION ALL m_a_rcvbl_flow_arc`。

**5. 分时电量**：走 `m_e_cons_snap_arc → m_r_data_arc(ON snap.id = r.calc_id AND r.amt_ym = snap.ym AND r.org_no LIKE 'xxx%' AND r.read_type_code IN (...))`。JOIN 四条件缺一不可。DDL 注释中 ⚠️ 警告的字段规则必须遵守。总有功从 `m_a_rcvbl_flow.t_pq` 取。

**6. MySQL 5.7**：禁止 WITH (CTE)，用嵌套子查询。关键字列名用反引号包裹。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 质量要求
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**7. 覆盖所有列**：逐一核对用户需求的每一列，SELECT 中都有对应表达式。找不到字段的列用注释说明跳过原因。

**8. 字典翻译**：码值用 `LEFT JOIN m_p_code px ON px.code_type = '码类' AND px.value = 源表.字段 AND px.take_effect_flag = 1`，取 `px.name AS 中文名`。

**9. NULL 处理**：数值 `IFNULL(expr, 0)`，字符串 `IFNULL(expr, '')`。

**10. 性能**：大表先用小表按 ym + org_no 过滤出 ID，再 INNER JOIN。禁止 EXISTS 关联子查询。

**11. 注释（必须详细，方便 DBA 微调）**：
   每条 SQL 必须包含以下注释：
   - **头部注释**：查询目的、数据范围（组织、月份）、关键过滤条件
   - **子查询注释**：每个派生表前面用 `-- [用途]` 说明它做了什么、为什么这样写
   - **JOIN 注释**：每个 JOIN 前面用 `-- 关联xxx表获取xxx`
   - **字段注释**：关键字段用 `-- 注释` 说明业务含义（尤其 CASE WHEN、复杂计算）
   - **跳过说明**：找不到字段的列写 `-- xxx字段不存在，已跳过`
   注释示例：
   ```
   -- ============================================
   -- 查询: 组织5100113下后付费用户202605月电费明细
   -- 过滤: org_no LIKE '5100113%', rcvbl_ym='202605', ctl_mode='03'（后付费）
   -- 数据来源: m_a_rcvbl_flow + m_a_rcvbl_flow_arc（归档表UNION ALL）
   -- ============================================
   -- 电费汇总（应收+实收+结清状态，现用库+归档库合并）
   LEFT JOIN (
       SELECT cons_no,
              SUM(rcvbl_amt) AS rcvbl_amt_sum,   -- 应收电费
              SUM(rcved_amt) AS rcved_amt_sum,   -- 实收电费
              SUM(t_pq) AS t_pq_sum               -- 总有功电量（注意：从rcvbl_flow取，不从r_data_arc取避免多表重复）
       FROM (
           SELECT cons_no, rcvbl_amt, rcved_amt, t_pq
           FROM m_a_rcvbl_flow
           WHERE org_no LIKE '5100113%' AND rcvbl_ym = '202605'
           UNION ALL
           SELECT cons_no, rcvbl_amt, rcved_amt, t_pq
           FROM m_a_rcvbl_flow_arc
           WHERE org_no LIKE '5100113%' AND rcvbl_ym = '202605'
       ) t
       GROUP BY cons_no
   ) f ON a.cons_no = f.cons_no  -- 关联应收流水获取电费数据
   ```

**12. 安全**：只生成 SELECT，输出纯净 ```sql 代码块。"""),
        ("human", "{question}")
    ])
    return prompt | llm | StrOutputParser()

def get_sql_fix_chain(llm):
    prompt = ChatPromptTemplate.from_messages([
        ("system", """上一轮生成的 SQL 被拒绝了，你需要修复它。

【数据库表结构】：
{exact_schema_context}

【表关系领域知识】（关键原则与反模式，修复时务必遵守）：
{domain_knowledge_context}

【历史参考案例】（可参考的正确 SQL 写法）：
{few_shot_context}

【错误 SQL】：
{wrong_sql}

【报错/拦截原因】：
{error_msg}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🛑 第一原则：不存在的字段直接删除
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**修复 SQL 时，如果报错是字段不存在（Unknown column）：删除该字段引用，在注释中说明「该字段在当前表中不存在，已跳过」。不要换一个名字重试，不要猜测别名字段——直接删除。**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【修复原则】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. **局部修复优先**：只修改导致报错的部分，保留原有正确的查询结构和业务逻辑不变。不要推倒重写。

2. **错误类型判断**：
   - 如果是「SQL_ERROR」字段不存在 → **直接删除该字段引用**，在注释中标注 `-- 字段 xxx 不存在，已跳过`。严禁换名重试！
   - 如果是「SQL_ERROR」语法/表名错误 → 检查表名拼写、JOIN 条件是否正确、反引号是否正确包裹关键字。参照【表关系领域知识】中的正确 JOIN 路径。
   - 如果是「领域规则拦截」→ 严格按拦截信息中的 fix_suggestion 修改，并参照【表关系领域知识】中的关键原则和反模式。
   - 如果是「性能审查失败」→ 按 Reviewer 的 suggestion 修改，通常是 EXISTS → INNER JOIN、添加索引友好的过滤条件。

3. **安全红线**：只输出 SELECT 查询。禁止生成 CREATE、DELETE、DROP、INSERT、UPDATE 等 DDL/DML 语句。

4. 输出修正后的纯净 ```sql ... ``` 代码块。"""),
        ("human", "原始需求：{question}。请立刻修复！")
    ])
    return prompt | llm | StrOutputParser()

def get_reviewer_chain(llm):
    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是一个经验丰富的数据库性能审查官（Reviewer Agent）。
审查 SQL 及其 MySQL EXPLAIN 执行计划，给出 PASS 或 FAIL 判定。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【审查判定标准】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**可以放行（PASS）的场景（只要满足任一条就放行）：**
1. SQL 包含 SUM/COUNT/GROUP BY 等聚合统计 — 报表查询天然需要扫描大量数据，全表扫描(type=ALL/index)是正常的，不因行数多而拦截
2. SQL 有 org_no LIKE 'xxx%' 过滤 + UNION ALL 归档表 — 说明数据隔离和完整性已正确处理，即使行数大也放行
3. Using temporary / Using filesort 出现在复杂报表中 — 可接受
4. LEFT JOIN m_p_code 字典翻译 — 标准模式，不影响性能

**必须拦截（FAIL）的场景（只有出现以下情况才拦截）：**
1. **DEPENDENT SUBQUERY + 大表**：EXPLAIN 中出现 `DEPENDENT SUBQUERY` 且关联表为 m_r_data_arc、m_a_rcvbl_flow、m_a_rcvbl_flow_arc 等亿级大表 — 这会导致逐行扫描上亿行，必须改为 INNER JOIN
2. **笛卡尔积**：缺少 JOIN 条件，预估 rows 达到数千万或破亿
3. **单用户查询全表扫描**：业务要求只查单个用户（cons_no = 'xxx'），但 EXPLAIN 显示 type=ALL 且没有 org_no 或 cons_no 过滤
4. **子查询缺少 org_no 过滤**：派生表/子查询内部没有 `org_no LIKE 'xxx%'`

【重要原则】：
- 不要因为"扫描行数多"就拦截 —— 只要过滤条件正确（org_no LIKE）、JOIN 路径正确、没有 DEPENDENT SUBQUERY，报表 SQL 扫描几百万甚至上千万行都是正常的
- 你的任务是拦截"写法错误导致的不必要扫描"，而不是拦截"数据量大导致的必然扫描"

【输出格式】：
必须严格输出 JSON（不要 ```json 标签）：
{{
    "status": "PASS" 或 "FAIL",
    "reason": "如果 FAIL，指出致命性能问题（提及具体表名和行数）",
    "suggestion": "如果 FAIL，给出具体的 SQL 修改示例"
}}"""),
        ("human", "【待审查 SQL】:\n{sql}\n\n【EXPLAIN 计划】:\n{explain_plan}")
    ])
    return prompt | llm | StrOutputParser()


def get_schema_linker_chain(llm):
    """Schema Linking：给定用户需求 + 表及全部字段，返回每张表的相关字段列表（JSON）。
    用于裁剪 DDL，只发送相关列给 Coder，减少 50-70% token。"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是一个数据库 Schema 分析专家。根据用户需求，从每张表的可用字段中选出本次查询真正需要的字段。

【输出规则】：
1. 输出纯 JSON，不要 ```json 标签
2. 格式：{{"表名": ["字段1", "字段2", ...]}}
3. 选择原则：
   - 用户明确提到的指标、维度、过滤条件对应的字段 → 必选
   - 关联字段（JOIN 的 ON 条件涉及的字段）→ 必选
   - org_no（数据隔离）→ 必选
   - 字典翻译需要的码值字段 → 必选
   - 用户没有提到的字段 → 不选
   - 每张表至少保留 1 个字段（如果该表完全无关，可以整表不选）
4. 只输出 JSON，不要任何解释文字"""),
        ("human", """【用户需求】：
{question}

【可用表及字段】：
{schema_summary}

请输出相关字段的 JSON 映射。""")
    ])
    return prompt | llm | StrOutputParser()


def get_table_discovery_chain(llm):
    """表发现：根据用户问题，从全部可用表中选出本次查询需要的表（JSON 列表）。
    用于补充 few-shot 检索可能遗漏的关键表。"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是一个电力营销数据库专家。根据用户需求，从可用表清单中选出本次查询肯定需要的表。

【规则】：
1. 输出纯 JSON 数组，如 ["m_c_cons", "ac_org", "m_a_rcvbl_flow"]
2. 只选和用户需求直接相关的表（主数据表、关联表、字典表）
3. 字典翻译相关的 m_p_code 在需要翻译码值时必选
4. org_no 数据隔离需要的 ac_org 在有用户/组织查询时必选
5. 用户明确提到的实体对应表 → 必选
6. 宁可多选 1-2 张，不要漏选关键表
7. 只输出 JSON 数组，不要任何解释"""),
        ("human", """【用户需求】：
{question}

【可用表清单】：
{table_list}

输出 JSON 数组。""")
    ])
    return prompt | llm | StrOutputParser()