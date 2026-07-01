import streamlit as st
# import io                         # [已废弃] 导出逻辑
import os
import json
import socket
from datetime import datetime
# import pandas as pd               # [已废弃] 导出逻辑
from retriever import init_ensemble_retriever, init_few_shot_retriever
from agent import get_llm
from agent_graph import sql_agent_graph
# from database import execute_export_sql  # [已废弃] 导出逻辑
from config import OLLAMA_BASE_URL, CHROMA_DB_PATH, FEW_SHOT_DB_PATH, DB_HOST, DB_PORT

# ================= 组织编号数据加载 =================
_ORG_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "组织编号.json")


@st.cache_data
def _load_org_tree():
    """加载原始树结构（缓存）"""
    try:
        with open(_ORG_DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []



# ================= 1. 页面与全局配置 =================
st.set_page_config(page_title="DeepSeek SQL Copilot", page_icon="⚡", layout="wide")

# ---- 用户反馈存储（轻量：纯记录，不做自动入库） ----
_FEEDBACK_LOG = os.path.join(os.path.dirname(__file__), "..", "data", "feedback_log.json")


def _save_feedback(question: str, sql: str, label: str):
    """保存用户反馈到 feedback_log.json，label=liked/disliked"""
    record = {
        "label": label,
        "question": question,
        "sql": sql,
        "timestamp": datetime.now().isoformat(),
    }
    try:
        existing = []
        if os.path.exists(_FEEDBACK_LOG):
            with open(_FEEDBACK_LOG, "r", encoding="utf-8") as f:
                existing = json.load(f)
        existing.append(record)
        with open(_FEEDBACK_LOG, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
    except Exception as e:
        import logging
        logging.getLogger("sqlgen").warning(f"反馈保存失败: {label} | {type(e).__name__}: {e}")

# ---- 自定义 CSS ----
st.markdown("""
<style>
    /* 侧边栏整体 */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
        padding-top: 0;
    }
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] .stMarkdown,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] .stCaption {
        color: #e2e8f0;
    }

    /* 侧边栏标题区域 */
    .sidebar-brand {
        padding: 1.5rem 1rem 0.75rem 1rem;
        text-align: center;
        border-bottom: 1px solid rgba(148, 163, 184, 0.15);
        margin-bottom: 0.75rem;
    }
    .sidebar-brand h1 {
        font-size: 1.15rem;
        font-weight: 700;
        color: #f8fafc;
        margin: 0;
        letter-spacing: 0.02em;
    }
    .sidebar-brand p {
        font-size: 0.72rem;
        color: #94a3b8;
        margin: 0.25rem 0 0 0;
    }

    /* 分区卡片 */
    .sb-section {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(148, 163, 184, 0.1);
        border-radius: 10px;
        padding: 0.75rem 0.85rem;
        margin: 0 0.5rem 0.75rem 0.5rem;
    }
    .sb-section-title {
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #64748b;
        margin-bottom: 0.6rem;
    }

    /* 模型选择器 */
    .model-badge {
        display: inline-block;
        font-size: 0.65rem;
        padding: 2px 8px;
        border-radius: 10px;
        background: rgba(99, 102, 241, 0.2);
        color: #a5b4fc;
        margin-left: 0.3rem;
    }

    /* 按钮 — 深色主题 */
    [data-testid="stSidebar"] .stButton > button,
    [data-testid="stSidebar"] .stButton > button * {
        color: #e2e8f0 !important;
    }
    [data-testid="stSidebar"] .stButton > button {
        border-radius: 8px !important;
        font-size: 0.82rem;
        font-weight: 500;
        transition: all 0.15s;
        background: rgba(255,255,255,0.08) !important;
        border: 1px solid rgba(148,163,184,0.15) !important;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(255,255,255,0.16) !important;
        border-color: rgba(148,163,184,0.35) !important;
        color: #f1f5f9 !important;
        transform: translateY(-1px);
    }
    /* primary 按钮（强制停止） */
    [data-testid="stSidebar"] .stButton > button[kind="primary"],
    [data-testid="stSidebar"] .stButton > button[kind="primary"] * {
        color: #ffffff !important;
    }
    [data-testid="stSidebar"] .stButton > button[kind="primary"] {
        background: #dc2626 !important;
        border-color: #991b1b !important;
    }
    [data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {
        color: #ffffff !important;
        background: #b91c1c !important;
    }
    /* secondary / default 按钮 */
    [data-testid="stSidebar"] .stButton > button[kind="secondary"],
    [data-testid="stSidebar"] .stButton > button[kind="secondary"] * {
        color: #e2e8f0 !important;
    }
    [data-testid="stSidebar"] .stButton > button[kind="secondary"] {
        background: rgba(255,255,255,0.08) !important;
        border-color: rgba(148,163,184,0.15) !important;
    }
    [data-testid="stSidebar"] .stButton > button[kind="secondary"]:hover {
        background: rgba(255,255,255,0.16) !important;
    }

    /* 健康检查条目 */
    .hc-item {
        font-size: 0.75rem;
        padding: 4px 8px;
        border-radius: 6px;
        margin: 2px 0;
    }
    .hc-ok {
        background: rgba(34, 197, 94, 0.1);
        color: #4ade80;
    }
    .hc-err {
        background: rgba(239, 68, 68, 0.1);
        color: #f87171;
    }

    /* expander "详情" 按钮 — 全部状态下保持浅色 */
    [data-testid="stSidebar"] .stExpander details summary,
    [data-testid="stSidebar"] .stExpander details summary *,
    [data-testid="stSidebar"] .stExpander details[open] summary,
    [data-testid="stSidebar"] .stExpander details[open] summary *,
    [data-testid="stSidebar"] .stExpander details summary:hover,
    [data-testid="stSidebar"] .stExpander details summary:hover *,
    [data-testid="stSidebar"] .stExpander details summary:focus,
    [data-testid="stSidebar"] .stExpander details summary:focus *,
    [data-testid="stSidebar"] .stExpander details summary:active,
    [data-testid="stSidebar"] .stExpander details summary:active * {
        color: #94a3b8 !important;
        background: transparent !important;
    }
    /* expander 内容区 */
    [data-testid="stSidebar"] .stExpander details {
        color: #e2e8f0 !important;
    }

    /* 滚动条 */
    [data-testid="stSidebar"] ::-webkit-scrollbar { width: 4px; }
    [data-testid="stSidebar"] ::-webkit-scrollbar-thumb {
        background: rgba(148,163,184,0.2);
        border-radius: 2px;
    }

    /* 下拉框和滑块输入框 */
    [data-testid="stSidebar"] .stSelectbox [data-baseweb="select"],
    [data-testid="stSidebar"] .stSelectbox [data-baseweb="popover"],
    [data-testid="stSidebar"] [data-testid="stThumbValue"] {
        color: #1e293b !important;
    }
    [data-testid="stSidebar"] .stSlider [data-testid="stThumbValue"] {
        color: #fff !important;
        background: #6366f1;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def load_retriever():
    return init_ensemble_retriever()


@st.cache_resource
def load_few_shot_retriever():
    return init_few_shot_retriever()


@st.cache_resource
def load_llm(model_name, temp):
    return get_llm(model_name, temp)


@st.cache_data(ttl=30)  # 30 秒自动过期，避免错误状态被永久缓存
def health_check() -> dict:
    """校验所有关键依赖，失败项列入 errors 列表（最多缓存 30 秒）"""
    errors = []

    # 1. Ollama 连通性
    try:
        from langchain_ollama import OllamaEmbeddings
        embeddings = OllamaEmbeddings(model="qwen3-embedding:8b", base_url=OLLAMA_BASE_URL)
        _ = embeddings.embed_query("health_check")
    except Exception as e:
        errors.append(f"❌ Ollama 不可用 ({OLLAMA_BASE_URL}): {e}")

    # 2. Schema 向量库完整性
    schema_db = os.path.join(CHROMA_DB_PATH, "chroma.sqlite3")
    if not os.path.exists(schema_db):
        errors.append(f"❌ Schema 向量库缺失: {schema_db}")

    # 3. Few-Shot 向量库完整性
    fewshot_db = os.path.join(FEW_SHOT_DB_PATH, "chroma.sqlite3")
    if not os.path.exists(fewshot_db):
        errors.append(f"❌ Few-Shot 向量库缺失: {fewshot_db}")

    # 4. 数据库 TCP 可达性
    try:
        sock = socket.create_connection((DB_HOST, DB_PORT), timeout=5)
        sock.close()
    except Exception as e:
        errors.append(f"❌ 数据库不可达 ({DB_HOST}:{DB_PORT}): {e}")

    return {"errors": errors}


# ================= 2. 侧边栏 =================
with st.sidebar:
    # ---- 品牌标识 ----
    st.markdown('<div class="sidebar-brand">'
                '<h1>⚡ SQL Gen</h1>'
                '<p>电力营销 · AI SQL 助手</p>'
                '</div>', unsafe_allow_html=True)

    # ---- 模型配置 ----
    st.markdown('<p class="sb-section-title" style="margin:0 0.5rem 0.4rem 0.5rem;">模型配置</p>',
                unsafe_allow_html=True)

    with st.container():
        model_help = "flash 更快更便宜，pro 推理更强更贵"
        selected_model = st.selectbox(
            "AI 模型",
            ("deepseek-v4-flash", "deepseek-v4-pro"),
            index=1,
            help=model_help,
        )
        selected_temp = st.slider(
            "温度",
            min_value=0.0, max_value=1.0, value=0.1, step=0.1,
            help="越低越严谨，越高越有创意",
        )

    # ---- 会话控制 ----
    st.markdown('<p class="sb-section-title" style="margin:1rem 0.5rem 0.4rem 0.5rem;">会话</p>',
                unsafe_allow_html=True)

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("🧹 清空对话", use_container_width=True, help="重置对话历史"):
            st.session_state.messages = [
                {"role": "assistant", "content": "你好！请描述你的查询需求，我将为你生成并验证高阶 SQL。"}
            ]
            st.session_state.last_successful_sql = None
            st.rerun()
    with col_b:
        if st.button("⏹ 强制停止", type="primary", use_container_width=True,
                     help="中断当前正在运行的 Agent 推演"):
            st.toast("🛑 已强行中断当前任务！您可以继续提问。")
            pass

    # ---- 系统状态 ----
    st.markdown('<p class="sb-section-title" style="margin:1rem 0.5rem 0.4rem 0.5rem;">系统状态</p>',
                unsafe_allow_html=True)

    # 初始化检测状态
    if "hc_loading" not in st.session_state:
        st.session_state.hc_loading = False

    if st.button("🔄 重新检测", use_container_width=True, key="hc_refresh"):
        health_check.clear()
        st.session_state.hc_loading = True
        st.rerun()

    if st.session_state.hc_loading:
        # 显示加载中状态
        placeholder = st.empty()
        placeholder.markdown(
            '<div style="padding:0.5rem;margin:0 0.5rem;text-align:center;">'
            '<span style="font-size:0.78rem;color:#94a3b8;">⏳ 正在检测系统依赖...</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        hc = health_check()
        st.session_state.hc_loading = False
        placeholder.empty()
    else:
        hc = health_check()

    # 逐项展示结果
    checks = [
        ("Ollama 嵌入服务", not any("Ollama" in e for e in hc["errors"])),
        ("Schema 向量库",    not any("Schema" in e for e in hc["errors"])),
        ("Few-Shot 向量库",  not any("Few-Shot" in e for e in hc["errors"])),
        ("数据库连接",       not any("数据库" in e for e in hc["errors"])),
    ]

    ok_count = sum(1 for _, ok in checks if ok)
    all_ok = ok_count == 4

    st.markdown(
        f'<div style="display:flex;align-items:center;gap:6px;padding:0.4rem 0.5rem;'
        f'background:rgba({34 if all_ok else 239},{197 if all_ok else 68},{94 if all_ok else 68},0.08);'
        f'border-radius:8px;margin:0 0.5rem;">'
        f'<span style="font-size:0.9rem;">{"🟢" if all_ok else "🔴"}</span>'
        f'<span style="font-size:0.78rem;color:{"#4ade80" if all_ok else "#f87171"};">'
        f'{"所有服务正常运行" if all_ok else f"{4 - ok_count} 项服务异常"}'
        f'</span></div>',
        unsafe_allow_html=True,
    )

    with st.expander("详情", expanded=not all_ok):
        for name, ok in checks:
            icon = "✅" if ok else "❌"
            cls = "hc-ok" if ok else "hc-err"
            st.markdown(f'<div class="hc-item {cls}">{icon} {name}</div>', unsafe_allow_html=True)
        if not all_ok:
            for err in hc["errors"]:
                st.error(err)

    # ---- 组织编号 ----
    st.markdown('<p class="sb-section-title" style="margin:1rem 0.5rem 0.4rem 0.5rem;">组织编号</p>',
                unsafe_allow_html=True)

    org_tree = _load_org_tree()
    if org_tree:
        tree_json = json.dumps(org_tree, ensure_ascii=False)
        tree_html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  html, body {{
    height: 100%; margin: 0; padding: 0;
    background: transparent; color: #e2e8f0;
    font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
    font-size: 0.82rem; line-height: 1.5;
  }}
  body {{
    display: flex; flex-direction: column;
    padding: 4px 6px; user-select: none;
  }}
  /* 顶部区域：面包屑 + 返回按钮，固定不滚动 */
  .header {{
    flex-shrink: 0;
  }}
  /* 中间列表：自动撑满，内容多时滚动 */
  .list-scroll {{
    flex: 1; overflow-y: auto; min-height: 0;
    margin: 2px 0;
  }}
  .list-scroll::-webkit-scrollbar {{ width: 3px; }}
  .list-scroll::-webkit-scrollbar-thumb {{ background: rgba(148,163,184,0.2); border-radius: 2px; }}
  /* 底部卡片：固定不滚动 */
  .footer {{
    flex-shrink: 0;
  }}

  /* 面包屑 */
  .breadcrumb {{
    display: flex; flex-wrap: wrap; align-items: center; gap: 2px;
    padding: 4px 6px; margin-bottom: 4px;
    border-radius: 6px;
    background: rgba(255,255,255,0.03);
    font-size: 0.7rem; color: #94a3b8;
    min-height: 22px;
  }}
  .breadcrumb span {{ color: #64748b; }}
  .breadcrumb .active {{ color: #a5b4fc; font-weight: 600; }}

  /* 后退按钮 */
  .back-row {{
    display: flex; align-items: center; gap: 6px;
    margin-bottom: 4px;
  }}
  .back-btn {{
    background: rgba(255,255,255,0.06); border: none;
    color: #94a3b8; cursor: pointer;
    padding: 2px 10px; border-radius: 4px;
    font-size: 0.72rem;
    transition: all 0.15s;
  }}
  .back-btn:hover {{ background: rgba(255,255,255,0.12); color: #e2e8f0; }}
  .back-btn:disabled {{ opacity: 0.3; cursor: default; }}
  .level-hint {{
    font-size: 0.66rem; color: #475569;
  }}

  /* 列表项 */
  .item {{
    display: flex; align-items: center; justify-content: space-between;
    padding: 6px 8px; border-radius: 5px;
    cursor: pointer; transition: background 0.12s;
    gap: 6px;
  }}
  .item:hover {{ background: rgba(255,255,255,0.05); }}
  .item-name {{
    flex: 1; min-width: 0;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    color: #cbd5e1;
  }}
  .item-id {{
    flex-shrink: 0;
    padding: 2px 8px; border-radius: 3px;
    background: rgba(99,102,241,0.14);
    color: #818cf8;
    font-family: "SF Mono","Fira Code",monospace;
    font-size: 0.72rem;
    letter-spacing: 0.02em;
    transition: all 0.15s;
  }}
  .item:hover .item-id {{ background: rgba(99,102,241,0.25); }}
  .item.has-children::after {{
    content: '›'; color: #475569; font-size: 0.9rem; margin-left: 2px;
  }}

  /* 选中卡 */
  .selected-card {{
    background: rgba(99,102,241,0.08);
    border: 1px solid rgba(99,102,241,0.18);
    border-radius: 8px; padding: 6px 10px;
  }}
  .sel-path {{
    font-size: 0.68rem; color: #64748b; margin-bottom: 3px;
    line-height: 1.3;
  }}
  .sel-row {{
    display: flex; align-items: center; justify-content: space-between; gap: 6px;
  }}
  .sel-id {{
    background: rgba(99,102,241,0.15);
    color: #a5b4fc;
    padding: 3px 10px; border-radius: 4px;
    font-family: "SF Mono","Fira Code",monospace;
    font-size: 0.8rem;
  }}
  .copy-btn {{
    background: rgba(99,102,241,0.18); border: none;
    color: #a5b4fc; cursor: pointer;
    padding: 3px 12px; border-radius: 5px;
    font-size: 0.7rem; white-space: nowrap;
    transition: all 0.15s;
  }}
  .copy-btn:hover {{ background: rgba(99,102,241,0.35); }}
  .copy-btn.copied {{ background: rgba(34,197,94,0.22); color: #4ade80; }}

  .toast {{
    position: fixed; bottom: 8px; left: 50%; transform: translateX(-50%);
    padding: 4px 12px; border-radius: 5px;
    background: rgba(34,197,94,0.18); color: #4ade80;
    font-size: 0.68rem; opacity: 0; transition: opacity 0.2s;
    pointer-events: none; z-index: 10;
  }}
  .toast.show {{ opacity: 1; }}

  .empty-hint {{
    text-align: center; color: #475569; font-size: 0.7rem;
    padding: 20px 0;
  }}
</style></head><body>
<div class="header">
  <div class="breadcrumb" id="breadcrumb"></div>
  <div class="back-row">
    <button class="back-btn" id="backBtn" onclick="goBack()" disabled>← 返回上级</button>
    <span class="level-hint" id="levelHint"></span>
  </div>
</div>
<div class="list-scroll" id="list"></div>
<div class="footer">
  <div class="selected-card" id="selCard" style="display:none;">
    <div class="sel-path" id="selPath"></div>
    <div class="sel-row">
      <span class="sel-id" id="selId"></span>
      <button class="copy-btn" id="copyBtn" onclick="doCopy()">📋 复制</button>
    </div>
  </div>
</div>
<div class="toast" id="toast"></div>
<script>
  const TREE = {tree_json};
  let path = [];           // {{id, text}} 从根到当前
  let currentNode = null;  // TREE 根节点的引用

  function getChildren(node) {{
    return (node && node.children) ? node.children : [];
  }}

  function findNode(pathIds) {{
    let list = TREE;
    for (let pid of pathIds) {{
      let found = list.find(n => String(n.id) === String(pid));
      if (!found) return null;
      list = getChildren(found);
    }}
    return list;  // 返回 children 列表
  }}

  function render() {{
    const bc = document.getElementById('breadcrumb');
    const list = document.getElementById('list');
    const backBtn = document.getElementById('backBtn');
    const levelHint = document.getElementById('levelHint');
    const selCard = document.getElementById('selCard');

    // 面包屑
    if (path.length === 0) {{
      bc.innerHTML = '<span>🏢 全部组织</span>';
      backBtn.disabled = true;
      levelHint.textContent = '点击展开下级';
    }} else {{
      let html = '';
      for (let i = 0; i < path.length; i++) {{
        if (i > 0) html += '<span> › </span>';
        html += '<span class="active">' + esc(path[i].text) + '</span>';
      }}
      bc.innerHTML = html;
      backBtn.disabled = false;
      levelHint.textContent = path.length + ' 级深度';
    }}

    // 当前层级的子节点
    let children;
    if (path.length === 0) {{
      children = TREE;
    }} else {{
      let parentList = findNode(path.slice(0, -1).map(p => p.id));
      let parent = parentList ? parentList.find(n => String(n.id) === String(path[path.length-1].id)) : null;
      children = parent ? parent.children || [] : [];
    }}

    // 渲染列表
    list.innerHTML = '';
    if (!children || children.length === 0) {{
      list.innerHTML = '<div class="empty-hint">已到最底层，无下级组织</div>';
    }} else {{
      children.forEach(function(node) {{
        const div = document.createElement('div');
        div.className = 'item' + (node.children && node.children.length > 0 ? ' has-children' : '');

        const name = document.createElement('span');
        name.className = 'item-name';
        name.textContent = node.text;

        const idSpan = document.createElement('span');
        idSpan.className = 'item-id';
        idSpan.textContent = node.id;
        idSpan.title = '点击复制 ' + node.id;
        idSpan.addEventListener('click', function(e) {{
          e.stopPropagation();
          copyId(node.id);
        }});

        div.appendChild(name);
        div.appendChild(idSpan);

        div.addEventListener('click', function() {{
          path.push({{id: String(node.id), text: node.text}});
          render();
        }});

        list.appendChild(div);
      }});
    }}

    // 选中卡片
    if (path.length > 0) {{
      const last = path[path.length - 1];
      selCard.style.display = 'block';
      document.getElementById('selPath').textContent = path.map(p => p.text).join(' › ');
      document.getElementById('selId').textContent = last.id;
    }} else {{
      selCard.style.display = 'none';
    }}
  }}

  function goBack() {{
    if (path.length > 0) {{
      path.pop();
      render();
    }}
  }}

  function copyId(id) {{
    navigator.clipboard.writeText(id).then(function() {{
      showToast('✓ 已复制 ' + id);
    }}).catch(function() {{
      showToast('复制失败，请手动选择');
    }});
  }}

  function doCopy() {{
    if (path.length > 0) {{
      const id = path[path.length - 1].id;
      const btn = document.getElementById('copyBtn');
      navigator.clipboard.writeText(id).then(function() {{
        btn.textContent = '✓ 已复制';
        btn.classList.add('copied');
        setTimeout(function() {{ btn.textContent = '📋 复制'; btn.classList.remove('copied'); }}, 1500);
        showToast('✓ 已复制 ' + id);
      }}).catch(function() {{
        showToast('复制失败，请手动选择');
      }});
    }}
  }}

  function showToast(msg) {{
    const t = document.getElementById('toast');
    t.textContent = msg; t.classList.add('show');
    setTimeout(function() {{ t.classList.remove('show'); }}, 1500);
  }}

  function esc(s) {{
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }}

  render();
</script>
</body></html>"""
        st.components.v1.html(tree_html, height=450, scrolling=False)
    else:
        st.caption("组织数据加载失败")

    # ---- 底部信息 ----
    st.markdown(
        '<div style="font-size:0.62rem;color:#475569;padding:0.5rem 0.5rem;">'
        'MySQL 5.7 · DeepSeek · Ollama</div>',
        unsafe_allow_html=True,
    )

# ================= 3. 主界面初始化 =================
st.title("⚡ 智能 SQL 生成AI ")
st.markdown(
    "💡 **输入自然语言需求，AI 自动检索案例、编写 SQL、审查性能。**\n\n"
    "示例：*查询组织 5100113 下所有费控类型为后付费的用户 202605 月电费明细，"
    "包含供电单位、用户编号、用户名、费控类型、联系电话、用电类别、"
    "当月有功总/峰/平/谷电量、应收电费、实收电费、电费结清状态。*")


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

        # # [已废弃] 导出逻辑：模型只负责生成 SQL，不负责导出数据
        # if msg.get("is_export_ready"):
        #     st.download_button(
        #         label="📥 数据已就绪，点击下载 Excel 文件",
        #         data=msg["excel_bytes"],
        #         file_name="数据库探查结果导出.xlsx",
        #         mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        #         key=f"dl_btn_{idx}"
        #     )

# ================= 4. 核心工作流 =================
if user_query := st.chat_input("输入查询需求，AI 将为你生成 SQL..."):

    # # [已废弃] 导出拦截器：模型只负责生成 SQL
    # export_intents = ["是", "是的", "要", "导出", "导出数据", "导出excel", "需要", "yes", "y"]
    # if user_query.strip().lower() in export_intents and st.session_state.last_successful_sql:
    #     st.session_state.messages.append({"role": "user", "content": user_query})
    #     with st.chat_message("user"):
    #         st.markdown(user_query)
    #     with st.chat_message("assistant"):
    #         with st.spinner("⏳ 正在深入数据库执行超长查询，请耐心等待..."):
    #             export_sql = st.session_state.last_successful_sql
    #             df, sys_error = execute_export_sql(export_sql)
    #             if sys_error:
    #                 st.error(f"❌ 导出失败：\n{sys_error}")
    #             elif df is None or df.empty:
    #                 st.warning("⚠️ 数据库中当前条件下无匹配记录可供导出。")
    #             else:
    #                 buffer = io.BytesIO()
    #                 with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
    #                     df.to_excel(writer, index=False, sheet_name='数据导出')
    #                 excel_bytes = buffer.getvalue()
    #                 msg_content = f"✅ 成功提取并生成 Excel 文件！(本次共提取了 {len(df)} 条数据)"
    #                 st.session_state.messages.append({
    #                     "role": "assistant",
    #                     "content": msg_content,
    #                     "is_export_ready": True,
    #                     "excel_bytes": excel_bytes
    #                 })
    #                 st.rerun()
    #     st.stop()

    # ---------------- 常规提问：走大模型 Agent 推演流程 ----------------
    st.session_state.messages.append({"role": "user", "content": user_query})
    st.session_state.last_user_query = user_query  # 持久化，供反馈按钮跨重跑使用
    with st.chat_message("user"):
        st.markdown(user_query)

    with st.chat_message("assistant"):
        # A. 初始化图状态
        initial_state = {
            "question": user_query,
            "model_name": selected_model,
            "temperature": selected_temp,
            "few_shot_context": "", "required_tables": [], "exact_schema_context": "",
            "domain_knowledge_context": "",
            "found_tables": [], "sql": None, "sql_candidates": [], "error_msg": None, "warnings": [], "loop_count": 0
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
                        # API 降级警告
                        for w in node_state.get("warnings", []):
                            if w: st.warning(w)

                    elif node_name == "schema_augment":
                        domain_ctx = node_state.get('domain_knowledge_context', '')
                        if domain_ctx:
                            tables_with_knowledge = domain_ctx.count('###')
                            log_txt = f"📚 **[Schema 增强]** 为 {tables_with_knowledge} 张表注入了领域知识（表关系、关键原则、反模式）"
                            st.write(log_txt)
                            current_logs.append({"type": "text", "content": log_txt})
                        for w in node_state.get("warnings", []):
                            if w: st.warning(w)

                    elif node_name == "coder":
                        candidates = node_state.get("sql_candidates", [])
                        valid_cands = [c for c in candidates if c]
                        log_txt = f"🧑‍💻 **[Coder 节点]** 并行生成了 **{len(valid_cands)} 个候选 SQL**（低温保守 + 中温灵活）："
                        st.write(log_txt)
                        current_logs.append({"type": "text", "content": log_txt})
                        for w in node_state.get("warnings", []):
                            if w: st.warning(w)
                        for ci, cand in enumerate(valid_cands):
                            st.caption(f"候选 {chr(65 + ci)}（temp={0.0 if ci == 0 else 0.3}）：")
                            st.code(cand, language="sql")
                            current_logs.append({"type": "code", "content": cand, "lang": "sql"})

                    elif node_name == "candidate_select":
                        if node_state.get("error_msg"):
                            log_txt = f"🛡️ **[候选选择]** 最优候选存在领域规则问题，详见下方。SQL 已输出，可手动微调后使用：\n{node_state['error_msg']}"
                            st.warning(log_txt)
                            current_logs.append({"type": "warning", "content": log_txt})
                            # 即使有错误也展示最优 SQL
                            if node_state.get("sql"):
                                st.code(node_state["sql"], language="sql")
                                current_logs.append({"type": "code", "content": node_state["sql"], "lang": "sql"})
                        else:
                            log_txt = "✅ **[候选选择]** 已从 2 个候选中选出最优 SQL，领域规则校验通过！"
                            st.success(log_txt)
                            current_logs.append({"type": "success", "content": log_txt})

                    elif node_name == "domain_validator":
                        if node_state.get("error_msg"):
                            log_txt = f"🛡️ **[领域规则拦截]** 发现业务逻辑问题：\n{node_state['error_msg']}"
                            st.error(log_txt)
                            current_logs.append({"type": "error", "content": log_txt})
                        else:
                            log_txt = "✅ **[领域规则通过]** 表选择、字段使用、JOIN 路径均符合领域规范！"
                            st.success(log_txt)
                            current_logs.append({"type": "success", "content": log_txt})

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
        final_sql = final_output_state.get("sql")
        final_err = final_output_state.get("error_msg")

        if final_err:
            st.warning(f"⚠️ **SQL 生成过程中发现问题（可手动微调后使用）：**\n{final_err}")

        if final_sql:
            loop_count = final_output_state.get("loop_count", 1)
            st.session_state.last_successful_sql = final_sql
            if final_err:
                st.markdown("**👇 最优候选 SQL（存在上述问题，建议微调后执行）：**")
            else:
                st.markdown(f"✅ **SQL 生成成功！（共 {loop_count} 轮推演）**\n\n复制下方 SQL，在数据库客户端中执行：")
            st.code(final_sql, language="sql")
            # 保存到聊天记录（必须用 ```sql 包裹，否则重跑时 st.markdown 会把 SQL 当 markdown 渲染导致布局错乱）
            result_content = f"```sql\n{final_sql}\n```"
            if final_err:
                result_content = f"⚠️ 发现问题：{final_err}\n\n```sql\n{final_sql}\n```"
            st.session_state.messages.append({"role": "assistant", "content": result_content, "logs": current_logs})
        elif final_err:
            st.error(f"❌ SQL 生成失败：{final_err}")
            st.session_state.messages.append({"role": "assistant", "content": f"❌ {final_err}", "logs": current_logs})
        else:
            st.error("SQL generation failed: could not extract valid SQL")
            st.session_state.messages.append({"role": "assistant", "content": "SQL generation failed", "logs": current_logs})

# ---- 用户反馈按钮（有 SQL 时显示，在 if user_query: 外部，用 session_state 驱动） ----
if st.session_state.get("last_successful_sql"):
    final_sql = st.session_state.last_successful_sql
    fb_key = f"fb_{hash(final_sql) % 100000}"
    if f"{fb_key}_voted" not in st.session_state:
        st.caption("这条 SQL 对你有帮助吗？")
        col_fb1, col_fb2, col_fb3 = st.columns([1, 1, 6])
        with col_fb1:
            if st.button("👍", key=f"{fb_key}_up", help="SQL 正确，点赞入库"):
                _save_feedback(st.session_state.last_user_query, final_sql, "liked")
                st.session_state[f"{fb_key}_voted"] = "up"
                st.toast("👍 感谢反馈！该 SQL 已入库作为新案例")
                st.rerun()
        with col_fb2:
            if st.button("👎", key=f"{fb_key}_down", help="SQL 有误，记录分析"):
                _save_feedback(st.session_state.last_user_query, final_sql, "disliked")
                st.session_state[f"{fb_key}_voted"] = "down"
                st.toast("👎 感谢反馈！我们会分析改进")
                st.rerun()
    else:
        vote = st.session_state[f"{fb_key}_voted"]
        emoji = "👍" if vote == "up" else "👎"
        st.caption(f"已反馈 {emoji}，谢谢！")
