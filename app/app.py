import streamlit as st
import io
import pandas as pd
from retriever import init_ensemble_retriever, init_few_shot_retriever
from agent import get_llm
from agent_graph import sql_agent_graph
from database import execute_export_sql

# ================= 1. 页面与全局配置 =================
st.set_page_config(page_title="DeepSeek SQL Copilot", page_icon="⚡", layout="wide")


@st.cache_resource
def load_retriever():
    return init_ensemble_retriever()


@st.cache_resource
def load_few_shot_retriever():
    return init_few_shot_retriever()


@st.cache_resource
def load_llm(model_name, temp):
    return get_llm(model_name, temp)


# ================= 2. 侧边栏 =================
with st.sidebar:
    st.header("⚙️ 核心大脑配置")
    selected_model = st.selectbox("选择 AI 模型", ("deepseek-v4-flash", "deepseek-v4-pro"), index=1)
    selected_temp = st.slider("温度调节", 0.0, 1.0, 0.1, 0.1)

    st.divider()  # 添加一条华丽的分割线

    st.header("🛠️ 会话控制")

    # 【新增功能 1】：清空对话缓存
    if st.button("🧹 清空对话历史", use_container_width=True):
        # 将历史记录重置为初始状态
        st.session_state.messages = [
            {"role": "assistant", "content": "你好！请描述你的查询需求，我将为你生成并验证高阶 SQL。"}
        ]
        # 清空上一次的导出 SQL 记忆
        st.session_state.last_successful_sql = None
        # 强制刷新页面
        st.rerun()

    # 【新增功能 2】：强制停止按钮
    # 点击此按钮会触发 Streamlit 重新运行，从而直接掐断后台正在 running 的 Agent 循环
    if st.button("⏹️ 强制停止当前推演", type="primary", use_container_width=True):
        # Streamlit 点击任意按钮都会自动打断当前正在执行的长耗时任务，并触发全局重绘。
        # 这里绝对不能写 st.stop()，否则会阻止下方聊天界面的渲染，导致白屏。
        st.toast("🛑 已强行中断当前任务！您可以继续提问。")  # 弹出一条友好的小提示
        pass  # 直接放行，让代码继续往下跑，把聊天记录和输入框正常渲染出来

# ================= 3. 主界面初始化 =================
st.title("⚡ 智能 SQL 生成AI ")
st.markdown(
    "💡 *输入自然语言需求，AI 将自动进行库表规划、语法验证与性能审查（请帮我查询组织代码为5100113公司下面的所有费控类型为无的用户202604月电费明细，包含供电单位、用户编号、费控类型......。要求所有字典都展现字典名，不要展示码值）。*")

# 初始化历史消息记录
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "你好！请描述你的查询需求，我将为你生成并验证高阶 SQL。"}]

# 初始化上一次成功生成的 SQL
if "last_successful_sql" not in st.session_state:
    st.session_state.last_successful_sql = None

# 渲染历史对话
for idx, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

        # 🛡️ 【修复点 1】：如果历史消息中包含推演日志，使用 expander 完美还原历史细节下拉框
        if "logs" in msg and msg["logs"]:
            with st.expander("✨ 展开查看本轮 Agent 协同推演过程", expanded=False):
                for log in msg["logs"]:
                    if log["type"] == "text":
                        st.write(log["content"])
                    elif log["type"] == "code":
                        st.code(log["content"], language=log.get("lang", "sql"))
                    elif log["type"] == "error":
                        st.error(log["content"])
                    elif log["type"] == "success":
                        st.success(log["content"])

        # 如果历史消息中存了最终 SQL，单独展示一个代码块
        if "final_sql" in msg:
            st.code(msg["final_sql"], language="sql")

        # 如果历史消息里存了 Excel 数据流，渲染下载按钮
        if msg.get("is_export_ready"):
            st.download_button(
                label="📥 数据已就绪，点击下载 Excel 文件",
                data=msg["excel_bytes"],
                file_name="数据库探查结果导出.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"dl_btn_{idx}"
            )

# ================= 4. 核心工作流 =================
if user_query := st.chat_input("输入查询需求，或在查出结果后输入'导出'获取数据文件..."):

    # ---------------- 拦截器：判断是否为导出数据的指令 ----------------
    export_intents = ["是", "是的", "要", "导出", "导出数据", "导出excel", "需要", "yes", "y"]
    if user_query.strip().lower() in export_intents and st.session_state.last_successful_sql:
        st.session_state.messages.append({"role": "user", "content": user_query})
        with st.chat_message("user"):
            st.markdown(user_query)

        with st.chat_message("assistant"):
            with st.spinner("⏳ 正在深入数据库执行超长查询，请耐心等待..."):
                export_sql = st.session_state.last_successful_sql
                df, sys_error = execute_export_sql(export_sql)

                if sys_error:
                    st.error(f"❌ 导出失败：\n{sys_error}")
                elif df is None or df.empty:
                    st.warning("⚠️ 数据库中当前条件下无匹配记录可供导出。")
                else:
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                        df.to_excel(writer, index=False, sheet_name='数据导出')
                    excel_bytes = buffer.getvalue()

                    msg_content = f"✅ 成功提取并生成 Excel 文件！(本次共提取了 {len(df)} 条数据)"
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": msg_content,
                        "is_export_ready": True,
                        "excel_bytes": excel_bytes
                    })
                    st.rerun()
        # ⚠️ 必须包裹在导出逻辑的分支内，防止阻断正常提问
        st.stop()

    # ---------------- 常规提问：走大模型 Agent 推演流程 ----------------
    st.session_state.messages.append({"role": "user", "content": user_query})
    with st.chat_message("user"):
        st.markdown(user_query)

    with st.chat_message("assistant"):
        # A. 初始化图状态
        initial_state = {
            "question": user_query,
            "model_name": selected_model,
            "temperature": selected_temp,
            "few_shot_context": "", "required_tables": [], "exact_schema_context": "",
            "found_tables": [], "sql": None, "error_msg": None, "loop_count": 0
        }
        final_output_state = initial_state.copy()

        # 🛡️ 【修复点 2】：创建一个临时容器，用来打包这一轮次产生的所有日志颗粒
        current_logs = []

        # B. 开启日志追踪面板
        with st.status("⚡ 唤醒多 Agent 协作网络，实况推演中...", expanded=True) as status_container:

            # C. 监听图状态机的每一个节点产出
            for output in sql_agent_graph.stream(initial_state):
                for node_name, node_state in output.items():
                    final_output_state.update(node_state)
                    current_loop = final_output_state.get('loop_count', 1)

                    # 根据不同节点，打印日志的同时，塞入 current_logs 结构化列表
                    if node_name == "retrieve_and_plan":
                        log_txt = f"🧠 **[Planner 节点]** 检索完成，锁定底层表：`{', '.join(node_state.get('found_tables', []))}`"
                        st.write(log_txt)
                        current_logs.append({"type": "text", "content": log_txt})

                    elif node_name == "coder":
                        log_txt = f"🧑‍💻 **[Coder 节点]** 编写出 **初版 SQL (V1)**："
                        st.write(log_txt)
                        current_logs.append({"type": "text", "content": log_txt})
                        if node_state.get("sql"):
                            st.code(node_state["sql"], language="sql")
                            current_logs.append({"type": "code", "content": node_state["sql"], "lang": "sql"})

                    elif node_name == "dba_reviewer":
                        if node_state.get("error_msg"):
                            log_txt = f"🚨 **[DBA 拦截]** 发现性能/语法问题，打回重写：\n{node_state['error_msg']}"
                            st.error(log_txt)
                            current_logs.append({"type": "error", "content": log_txt})
                        else:
                            log_txt = "✅ **[DBA 放行]** EXPLAIN 校验通过，无全表扫描风险！"
                            st.success(log_txt)
                            current_logs.append({"type": "success", "content": log_txt})

                    elif node_name == "fixer":
                        log_txt = f"🔄 **[Fixer 节点]** 针对报错重新推演，生成 **第 {current_loop} 版修正 SQL**："
                        st.write(log_txt)
                        current_logs.append({"type": "text", "content": log_txt})
                        if node_state.get("sql"):
                            st.code(node_state["sql"], language="sql")
                            current_logs.append({"type": "code", "content": node_state["sql"], "lang": "sql"})

            status_container.update(label="✨ Agent 架构演进与验证完毕！点击可展开查看推演过程", state="complete",
                                    expanded=False)

        # D. 最终结果判定与渲染
        if final_output_state.get("error_msg") and final_output_state.get("loop_count") >= 3:
            err_msg = f"❌ 经历了 {final_output_state['loop_count']} 次震荡修复后仍未完全成功，最终错误：{final_output_state['error_msg']}"
            st.error(err_msg)
            # 🛡️ 【修复点 3】：失败时也将日志细节打包绑定存入历史
            st.session_state.messages.append({"role": "assistant", "content": err_msg, "logs": current_logs})
        else:
            final_sql = final_output_state.get("sql")
            loop_count = final_output_state.get('loop_count', 1)

            st.session_state.last_successful_sql = final_sql

            success_msg = f"✅ **高可用 SQL 生成完毕！(共经历 {loop_count} 轮打磨)**\n\n您可以直接复制执行，或者回复 **“导出”** 让后台帮您下载为 Excel 文件："
            st.markdown(success_msg)
            st.code(final_sql, language="sql")

            # 🛡️ 【修复点 4】：成功时将日志细节打包绑定存入历史
            st.session_state.messages.append({
                "role": "assistant",
                "content": success_msg,
                "final_sql": final_sql,
                "logs": current_logs
            })
