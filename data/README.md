# SQL 知识库数据清洗文档

## 一、背景与动机

### 1.1 旧流程的问题

项目原有的数据清洗流程（位于 `data/` 目录）存在根本性缺陷：

```
旧流程:
  schema_docs.json (手工维护) + auto_field_map.json (人工猜测的字段→字典映射)
        ↓ 暴力拼接（无论对错，有映射就强行塞入）
  intermediate_schema.json (包含大量错误映射)
        ↓ AI "纠错"（在错误的基础上修正，效果不稳定）
  final_super_schema_by_ai.json
```

**核心问题：**

1. **`auto_field_map.json` 是无上下文的盲目映射**——例如 `status_code` 字段在不同表中含义完全不同：
   - `m_c_cons.status_code` = 用户状态（正常/暂停/销户）
   - `m_c_mp.status_code` = 计量点状态（设立/在用/停用/撤销）
   - `m_a_rcvbl_flow.status_code` = 收费状态（非锁定/锁定）
   
   但 `auto_field_map.json` 把它们全部映射到同一个字典 `statusCode`，造成大量错误。

2. **`schema_docs.json` 手工维护**——表结构变更时需要手动更新，容易过时。

3. **`buildVector/` 目录的两个关键脚本丢失**（`build_few_shot_db.py`、`build_vector_db.py`），无法从清洗后的数据构建向量库。

### 1.2 新流程的设计思路

**核心原则：从真实 SQL 出发，而非从猜测出发。**

生产环境中积累的常用 SQL 是业务知识的金矿——它们包含了：
- 真实的表关联关系（FROM / JOIN）
- 正确的字段→字典映射（`m_p_code` 的 `code_type` + `value` 关联）
- 硬编码的枚举值翻译（`CASE WHEN '01' THEN '设立' ...`）
- 业务关键词（列别名中的中文描述）

新流程直接从这些 SQL 中提取知识，让 AI 做"融合"而非"纠错"。

---

## 二、新流程总览

```
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 解析 SQL 文件                                       │
│  step1_parse_sqls.py                                         │
│  输入: data/合并.sql                                          │
│  输出: parsed_sqls.json (92 条结构化 SQL)                     │
│  职责: 拆解多语句 SQL、提取表名、识别 m_p_code 关联、          │
│        识别 CASE WHEN 硬编码、提取中文关键词                   │
└──────────────┬──────────────────────────────────────────────┘
               ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 2: 提取字段→值映射                                      │
│  step2_extract_mappings.py                                   │
│  输入: parsed_sqls.json                                      │
│  输出: field_value_mappings.json (39 表/149 字段的映射)       │
│  职责: 从 CASE WHEN 提取硬编码枚举值、从 m_p_code 提取        │
│        字典类型关联、按表+字段去重聚合、归一化 code_type 大小写 │
└──────────────┬──────────────────────────────────────────────┘
               ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 3: 下载数据库 DDL                                       │
│  step3_download_ddl.py                                       │
│  输入: parsed_sqls.json (表名列表) + MySQL 连接               │
│  输出: raw_ddl.json (99 张表的完整 CREATE TABLE)              │
│  职责: 连接 MySQL 执行 SHOW CREATE TABLE、解析列信息           │
└──────────────┬──────────────────────────────────────────────┘
               ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 4: AI 增强 Schema（核心步骤）                            │
│  step4_ai_enhance_schema.py                                  │
│  输入: raw_ddl.json + field_value_mappings.json + DeepSeek   │
│  输出: final_super_schema_by_ai.json (80 张表 AI 增强)        │
│  职责: 将 DDL 原始注释与 SQL 提取的映射进行智能融合            │
└──────────────┬──────────────────────────────────────────────┘
               ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 5: AI 增强 Few-Shot 样本                                │
│  step5_ai_enhance_fewshot.py                                 │
│  输入: parsed_sqls.json + final_super_schema_by_ai.json      │
│        + DeepSeek API                                        │
│  输出: few_shot_examples.json (89 条高质量样本)               │
│  职责: 以增强 Schema 为上下文，反向工程每条 SQL 的业务含义      │
└──────────────┬──────────────────────────────────────────────┘
               ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 6: 构建向量数据库                                       │
│  step6_build_vectors.py                                      │
│  输入: final_super_schema_by_ai.json + few_shot_examples.json│
│        + Ollama (qwen3-embedding)                            │
│  输出: schema_chroma_db/ + few_shot_chroma_db/               │
│  职责: 构建 ChromaDB 向量库 + BM25 关键词索引，部署到 app/     │
└─────────────────────────────────────────────────────────────┘
```

---

## 三、各步骤详细说明

### Step 1: 解析 SQL 文件

**脚本**: `step1_parse_sqls.py`

**输入**: `data/合并.sql`（924 行，包含约 60 个 SQL 查询的集合文件）

**处理逻辑**:

1. **切分 SQL 块**: 按 `-- 文件名：` 标记将文件切分为独立的 SQL 块，提取标题
2. **拆分多语句**: 将包含多条 SQL（用 `;` 分隔）的块拆分为独立语句，只保留 SELECT 语句
3. **提取表名**: 用正则从 FROM / JOIN 子句中提取所有涉及的表名（支持 `db.table` 格式、反引号包裹等）
4. **提取 m_p_code 映射**: 识别 `code_type='xxx' AND value=table.field` 模式，记录字典类型与字段的关联
5. **提取 CASE WHEN 硬编码**: 识别 `CASE field WHEN '01' THEN '标签1' WHEN '02' THEN '标签2' END` 模式
6. **提取中文关键词**: 从列别名（`AS '列名'`）中提取业务关键词
7. **清洗 SQL**: 去除注释、压缩空白、标准化格式

**输出示例** (`parsed_sqls.json`):
```json
{
  "title": "关口表信息查询",
  "sql": "select ... from m_c_mp mp left join m_c_meter me ...",
  "tables": ["ac_org", "m_c_meter", "m_c_mp", "m_g_line", "m_g_tg", "m_p_code"],
  "m_p_code_mappings": [
    {"code_type": "mpSortCode", "field_ref": "mp.type_code"},
    {"code_type": "chkunitSort", "field_ref": "ch.chkunit_type_code"}
  ],
  "case_when_mappings": [
    {
      "field": "status_code",
      "full_field_ref": "mp.status_code",
      "values": {"01": "设立", "02": "在用", "03": "停用", "04": "撤销"}
    }
  ],
  "keywords": ["单位名称", "计量点编号", "计量名称", "计量点分类", "线路", "台区"]
}
```

**统计结果**:
- 识别 61 个 SQL 块 → 解析出 92 条独立 SELECT 语句
- 涉及 102 张数据库表
- 提取 129 种 m_p_code 字典类型
- 提取 9 个 CASE WHEN 硬编码映射

---

### Step 2: 提取字段→值映射

**脚本**: `step2_extract_mappings.py`

**处理逻辑**:

1. **解析 SQL 别名**: 从 FROM/JOIN 子句建立 `alias → table_name` 的映射表，将 `mp.type_code` 解析为 `m_c_mp.type_code`
2. **提取 m_p_code 关联**: 扫描所有 SQL 中的 `pX.code_type='xxx' AND pX.value=alias.field` 模式，按表+字段去重
3. **提取 CASE WHEN 硬编码**: 聚合所有 CASE WHEN 枚举值，按表+字段去重合并
4. **归一化 code_type**: SQL 中 code_type 大小写不一致（如 `statusCode` vs `StatusCode` vs `statuscode`），统一归一化
5. **合并输出**: 将两种来源（m_p_code 和 CASE WHEN）的映射合并为统一的 `field_value_mappings.json`

**输出格式** (`field_value_mappings.json`):
```json
{
  "table_name": "m_c_cons",
  "fields": [
    {
      "field_name": "status_code",
      "code_types": ["statusCode"],
      "hardcoded_values": {},
      "source": "m_p_code"
    },
    {
      "field_name": "ctl_mode",
      "code_types": ["ctlMode"],
      "hardcoded_values": {"01": "本地费控", "02": "本地量控", "03": "无", "04": "中心费控"},
      "source": "both"
    }
  ]
}
```

**字段来源说明**:

| source 值 | 含义 | 可信度 |
|-----------|------|--------|
| `case_when` | 仅从 CASE WHEN 硬编码中提取 | 高（来自生产 SQL） |
| `m_p_code` | 仅从 m_p_code 字典关联中提取 | 中（知道字典类型，不知道具体枚举值） |
| `both` | 两种来源都有 | 最高 |

**统计结果**:
- 39 张表有映射数据，共 149 个字段
- 5 个字段有 CASE WHEN 硬编码值
- 149 个字段有 m_p_code 字典类型关联

---

### Step 3: 下载数据库 DDL

**脚本**: `step3_download_ddl.py`

**处理逻辑**:

1. 从 `parsed_sqls.json` 提取所有唯一表名（过滤 SQL 关键字、临时表前缀等）
2. 连接 MySQL 数据库（`10.11.0.95:10050/epmp`，只读账户）
3. 逐表执行 `SHOW CREATE TABLE` 获取完整 DDL
4. 解析 DDL 中的列定义（字段名、类型、COMMENT、是否可空、默认值）

**数据库连接配置**:
```
Host: 10.11.0.95
Port: 10050
User: readonlyuser
Database: epmp
```

**统计结果**:
- 102 张表发出请求 → 99 张成功下载
- 3 张临时表（`xls_add_sect`、`xls_cons_cap315`、`xls_org`）不存在（正常，这些是 SQL 中引用的临时表）

---

### Step 4: AI 增强 Schema（核心步骤）

**脚本**: `step4_ai_enhance_schema.py`

**这是新旧流程的本质区别所在。**

**处理逻辑**:

每张表调用 DeepSeek API，输入：
1. 数据库原始 DDL（列名 + 类型 + COMMENT）
2. 从 SQL 提取的字段映射（code_type + 硬编码枚举值）

AI 的融合规则（在 Prompt 中明确约束）：

| 场景 | 处理方式 |
|------|---------|
| DDL COMMENT 已包含枚举值，且与 SQL 提取的一致 | 保持原样 |
| DDL COMMENT 无枚举值，SQL 提取到了 | 追加到 comment："枚举值: 01=设立, 02=在用..." |
| DDL COMMENT 提到"引用国家电网代码类集:XXXX" | 保留原文，追加 SQL 中实际使用的值作为参考 |
| DDL COMMENT 与 SQL 提取的冲突 | 以 DDL 为准（DDL 是官方定义） |
| SQL 中有 m_p_code 关联但无具体枚举值 | 标注："字典类型: code_type_name" |

**与旧流程的本质对比**:

| 维度 | 旧流程 (data/genSuperSchema.py) | 新流程 (dataNew/step4) |
|------|-------------------------------|----------------------|
| 映射来源 | `auto_field_map.json` 手工猜测 | 92 条真实 SQL 自动提取 |
| DDL 来源 | `schema_docs.json` 手工维护 | `SHOW CREATE TABLE` 直接下载 |
| AI 角色 | "纠错"（暴力拼接后修正错误） | "融合"（两个可信来源的合并） |
| 容错机制 | 解析失败时丢失字段 | API 失败时降级使用原始 DDL |

**统计结果**:
- 99 张表送入 AI → 80 张成功增强，19 张降级（API 临时不可用）
- 降级的表直接使用原始 DDL COMMENT，不影响后续流程

---

### Step 5: AI 增强 Few-Shot 样本

**脚本**: `step5_ai_enhance_fewshot.py`

**处理逻辑**:

1. **去重**: 按 SQL 签名（前 100 字符 + 长度）去重，避免冗余样本
2. **排序**: 按 SQL 长度降序排列，优先处理信息量大的 SQL
3. **构建上下文**: 为每条 SQL 涉及的每张表，从增强 Schema 中提取字段注释摘要
4. **AI 反向工程**: 调用 DeepSeek API，输入 SQL + Schema 上下文，生成结构化样本

**输出格式** (`few_shot_examples.json`):
```json
{
  "question": "查询供电单位5100102下所有关口计量点的详细信息...",
  "business_rules": "1. 关联ac_org表查询单位名称。2. 使用m_p_code字典表，code_type='mpSortCode'查询计量点分类...",
  "search_keywords": ["关口计量点", "计量点分类", "抄表段", "考核单元", "综合倍率"],
  "complexity": "complex",
  "sql": "select ... from m_c_mp mp left join ...",
  "title": "关口表信息查询",
  "tables_used": ["ac_org", "m_c_meter", "m_c_mp", "m_g_line", "m_g_tg", "m_p_code"]
}
```

**新增字段说明**（旧流程没有的）:

| 字段 | 用途 |
|------|------|
| `search_keywords` | 5-10 个业务关键词，用于向量检索时提升匹配精度 |
| `tables_used` | 涉及的表名列表，方便 Agent 快速判断是否需要此案例 |
| `complexity` | 复杂度分级（simple/medium/complex），可用于检索时按场景过滤 |
| `title` | 原始 SQL 标题，保留溯源信息 |

**统计结果**:
- 去重后 90 条 → 生成 89 条 Few-Shot 样本（1 条 SQL 太短被跳过）
- 复杂度分布: complex 50 条 / medium 29 条 / simple 10 条

---

### Step 6: 构建向量数据库

**脚本**: `step6_build_vectors.py`

**说明**: 此步骤暂时不运行，后续需要时执行。它替代丢失的 `buildVector/build_vector_db.py` 和 `buildVector/build_few_shot_db.py`。

**构建内容**:

1. **Schema 向量库** (`schema_chroma_db/`):
   - 嵌入模型: Ollama `qwen3-embedding:8b`
   - 检索策略: Ensemble（向量检索 + BM25 关键词检索，权重各 50%）
   - 每条 Document 的 page_content = 表名 + 所有字段及增强后的注释
   - metadata = 表名、字段数

2. **Few-Shot 向量库** (`few_shot_chroma_db/`):
   - 嵌入模型: 同上
   - 检索策略: MMR（Maximal Marginal Relevance，多样性召回）
   - fetch_k=10, k=5（从最相似的 10 个中挑选 5 个最有差异的）
   - 每条 Document 的 page_content = 问题 + 业务规则 + 关键词
   - metadata = title、question、business_rules、sql、tables_used、search_keywords、complexity

**部署目标**: 向量库和 JSON 数据文件复制到 `app/` 目录，供运行时使用。

---

## 四、运行指南

### 4.1 环境要求

| 步骤 | 依赖 |
|------|------|
| Step 1-2 | Python 3.10+，无外部网络依赖 |
| Step 3 | MySQL 数据库连接（内网 `10.11.0.95:10050`） |
| Step 4-5 | DeepSeek API（`api.deepseek.com`） |
| Step 6 | 本地 Ollama（`qwen3-embedding:8b` 模型） |

### 4.2 一键运行

```bash
cd dataNew

# 查看执行计划（不实际执行）
python run_all.py --dry-run

# 全部运行
python run_all.py

# 只运行特定步骤
python run_all.py --step 1,2,3

# 跳过 AI 步骤（适合网络不可用的情况）
python run_all.py --skip-step 4,5
```

### 4.3 单步运行

```bash
cd dataNew

# 设置 UTF-8 编码（Windows 必须）
export PYTHONIOENCODING=utf-8

python step1_parse_sqls.py        # 解析 SQL
python step2_extract_mappings.py   # 提取字段映射
python step3_download_ddl.py       # 下载 DDL
python step4_ai_enhance_schema.py  # AI 增强 Schema
python step5_ai_enhance_fewshot.py # AI 增强 Few-Shot
python step6_build_vectors.py      # 构建向量库
```

### 4.4 步骤间依赖

```
step1 → parsed_sqls.json
           ↓
step2 → field_value_mappings.json    step3 → raw_ddl.json
                                        ↘     ↙
                                    step4 → final_super_schema_by_ai.json
                                               ↓
step1 → parsed_sqls.json ─────────┐
                                  step5 → few_shot_examples.json
                                               ↓
                                          step6 → 向量库
```

---

## 五、文件清单

### 5.1 脚本文件

| 文件 | 行数 | 说明 |
|------|------|------|
| `step1_parse_sqls.py` | ~300 | SQL 解析器 |
| `step2_extract_mappings.py` | ~270 | 字段映射提取器 |
| `step3_download_ddl.py` | ~200 | DDL 下载器 |
| `step4_ai_enhance_schema.py` | ~230 | AI Schema 增强器 |
| `step5_ai_enhance_fewshot.py` | ~220 | AI Few-Shot 增强器 |
| `step6_build_vectors.py` | ~220 | 向量库构建器 |
| `run_all.py` | ~180 | 一键运行总控 |

### 5.2 数据文件

| 文件 | 大小 | 说明 |
|------|------|------|
| `parsed_sqls.json` | 189 KB | 92 条结构化 SQL |
| `field_value_mappings.json` | 30 KB | 39 表 149 字段的映射 |
| `raw_ddl.json` | ~500 KB | 99 张表的完整 DDL |
| `final_super_schema_by_ai.json` | ~200 KB | AI 增强后的知识库 Schema |
| `few_shot_examples.json` | ~150 KB | 89 条 AI 增强的 Few-Shot 样本 |

### 5.3 配置文件

| 文件 | 说明 |
|------|------|
| `.env` | DeepSeek API Key（从 data/.env 复制） |

---