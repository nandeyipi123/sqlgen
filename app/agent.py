from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL

def get_llm(model_name, temperature):
    return ChatOpenAI(
        model=model_name, api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL, temperature=temperature, streaming=True,max_retries=3,timeout=120
    )

def get_planner_chain(llm):
    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是一个顶级的电网数据库架构师 (Planner Agent)。
        你的任务是根据用户的【查询需求】和【历史参考案例】，推断出完成该查询需要用到哪些底层数据库表。
        【历史参考案例】：\n{few_shot_context}\n
        【你的输出要求 (极为严格)】：
        请严格只输出一个 Python 列表格式的表名集合，例如：['m_c_cons', 'ac_org']。绝对不要输出任何文字。"""),
        ("human", "用户需求：{question}")
    ])
    return prompt | llm | StrOutputParser()

def get_coder_chain(llm):
    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是一个精通 SQL 的高级 DBA (Coder Agent)。
        请根据以下【精准数据库表结构】和【历史参考案例】，将用户的需求转换为高质量的纯净 SQL。

        【精准数据库表结构】：\n{exact_schema_context}\n
        【历史参考案例】：\n{few_shot_context}\n

        【编写策略】：
        1. 优先模仿案例中的计算逻辑和表关联方式。
        2. 数据隔离：必须使用 `org_no LIKE 'xxx%'` 进行模糊匹配。
        3. ⚡ 性能调优：严禁在庞大的流水表上无条件进行外层 LEFT JOIN 和全局聚合！请通过高效的关联条件限制扫描行数。
        4. 🚫 版本限制 (极其重要)：当前数据库为 MySQL 5.7，绝对禁止使用 `WITH` (CTE) 语法！如需复用中间结果或提前过滤大表，请务必使用传统的嵌套子查询（派生表）。
        5. 请使用 `<think>` 标签梳理逻辑，最后输出 ```sql ... ``` 代码块。"""),
        ("human", "{question}")
    ])
    return prompt | llm | StrOutputParser()

def get_sql_fix_chain(llm):
    prompt = ChatPromptTemplate.from_messages([
        ("system", """你生成的 SQL 报错了！请结合【表结构】和真实的【数据库报错信息】修复 SQL。
        【数据库表结构】：\n{exact_schema_context}\n
        【错误 SQL】：\n{wrong_sql}\n
        【报错信息】：\n{error_msg}\n
        输出修正后的纯净 ```sql ... ``` 代码块。"""),
        ("human", "原始需求：{question}。请立刻修复！")
    ])
    return prompt | llm | StrOutputParser()

def get_reviewer_chain(llm):
    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是一个经验丰富的数据库性能审查官 (Reviewer Agent)。
        你的任务是审查 SQL 及其在 MySQL 中的【EXPLAIN 执行计划】。

        【审查宽容度原则 (极其重要)】：
        1. 区分场景：如果 SQL 包含 SUM, COUNT, GROUP BY 等统计逻辑，扫描上百万行 (rows < 5000000) 且 type 为 ALL 或 index 是**可以接受的**，不要轻易 FAIL。
        2. 致命拦截 (必须 FAIL)：
           - 缺少 JOIN 条件导致笛卡尔积（预估扫描 rows 达到数千万或破亿）。
           - 业务明确要求只查单个用户 (有 cons_no = 'xxx')，但却发生了全表扫描。
        3. Using temporary 和 Using filesort 在复杂报表统计中是正常的，只做建议，不强制 FAIL。

        【你的输出要求 (极为严格)】：
        必须严格输出 JSON 格式（直接输出花括号，不要包含 ```json 标签）：
        {{
            "status": "PASS" 或者 "FAIL",
            "reason": "如果FAIL，指出致命的性能崩坏点",
            "suggestion": "如果FAIL，给出具体的 SQL 修改建议"
        }}"""),
        ("human", "【待审查 SQL】:\n{sql}\n\n【EXPLAIN 计划】:\n{explain_plan}")
    ])
    return prompt | llm | StrOutputParser()