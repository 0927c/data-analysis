# ITSM 工单智能分析平台

基于 **FastAPI + Vue 3 + ECharts + Flue Agent (DeepSeek)** 的 IT 服务台工单数据智能分析平台。支持从 Excel 导入 ITSM 工单数据，通过自然语言对话自动生成多维度可视化报表和深度洞察。

## 核心特性

### 智能分析

- **自然语言交互** — 支持中文提问，如"五月份各系统有多少工单？""哪些故障反复出现？"
- **日期智能识别** — 自动提取"五月份""上个月""最近一周""2026年3月"等时间范围
- **Flue Agent 意图识别** — HTTP Agent Harness，调用 DeepSeek API 进行意图解析
- **安全网机制** — Flue 误判为闲聊时，自动 fallback 到规则引擎
- **四阶段深度分析法** — 数据分析大师角色：现状扫描 → 根因推导 → 趋势预测 → 行动建议
- **Markdown 富文本渲染** — AI 响应支持标题/加粗/列表/代码等格式化展示
- **深度洞察面板** — 独立的深色专业风格卡片，标签化分类（暴增预警/隐性根因/黄金建议）
- **自动洞察** — 规则驱动的数据洞察卡片（SLA 预警 / 重复告警 / 偏差检测）

### 维度自学习

- **动态维度发现** — 用户查询预设映射表外的维度时，自动在数据列中模糊匹配并出图
- **Markdown 待办清单** — 新发现的维度记录到 `docs/dimension-todo.md`，用户编辑决策
- **一键审批** — 运行 `scripts/process_dimension_todo.py` 永久加入维度映射表
- **维度覆盖层** — 批准的维度热更新到 `dimension_overrides.json`，无需重启

### 长记忆机制

- **用户偏好记忆** — 记住常用分析维度、筛选条件，自动推荐
- **分析历史记忆** — 保存每次分析结论，支持跨会话检索引用（"刚才那个分析"）
- **数据源元数据记忆** — 上传时自动提取字段结构、数据质量报告
- **对话上下文增强** — 跨轮引用检测，支持"上次的结果""之前的分析"等自然语言

### 数据源管理

- **两阶段上传** — 先预览字段映射（自动识别 + 置信度评分），确认后再导入
- **多数据源切换** — 对话中自然语言切换（"切换到 XX 数据源"）或 UI 点击切换
- **自定义字段映射** — 支持非标 Excel 列名映射到系统字段
- **报表数据源绑定** — 报表和下钻使用创建时的数据源，切换数据源后旧报表仍可正确查看
- **元数据自动提取** — 自动统计字段类型、空值率、关键分布、数据质量指标

### 报表与可视化

- **五章节结构化报告** — 摘要概览 → 产品线分析 → 原因分析 → 大客户分析 → 洞察建议
- **HTML 格式** — 交互式网页报告（内嵌 ECharts 图表）
- **Excel 格式** — 多 Sheet 电子表格（封面 + KPI + 数据明细 + 洞察 + 图表数据）
- **图表下钻** — 点击图表柱子/扇区查看原始工单明细（精确匹配，分页展示）
- **亮色主题** — 统一亮色设计系统，图表文字清晰可读

### 多轮对话

- **筛选条件累积** — 多轮对话中筛选条件自动叠加（"五月工单" → "其中PPM的" → "按状态分布"）
- **日期筛选智能保留** — 有其他筛选时保留日期范围，避免二次筛选丢失时间上下文
- **活跃筛选展示** — AI 回复下方显示当前生效的筛选条件标签

## 分析维度

| 类别 | 维度 | 图表 |
|------|------|------|
| 基础分布 | 状态 / 服务组 / 部门 / 来源渠道 / 业务系统 | 饼图 / 柱状图 |
| 机构分析 | 请求人机构分布 | 柱状图 |
| 人员效能 | 责任人 TOP / 解决人处理量 | 横向柱状图 |
| 趋势分析 | 每周 / 每月工单量、SLA 达标率周趋势 | 折线图 |
| 故障根因 | 原因类别 → 故障分组 → 症状三层钻取、故障趋势 | 横向柱状图 + 折线图 |
| 重复挖掘 | 按故障原因 + 标题关键词双向去重 | 横向柱状图 |
| 症状聚类 | 常见症状 → 最佳解决方案推荐、平均解决耗时 | 横向柱状图 |
| 运维质量 | 退回率 / 挂起率 / 撤单率 / SLA + 周趋势 | 横向柱状图 |
| 请求人分析 | 高频请求人 / 部门 / 机构 / 职务分布 × 性质交叉 | 横向柱状图 + 柱状图 |
| 性质趋势 | 各类性质占比饼图 + 周趋势堆叠面积图 | 饼图 + 折线图 |
| 满意度 | 服务态度 / 技术水平 / 响应时效评分 | 柱状图 |
| **动态维度** | 预设表外的维度自动发现 + 待办审批 | 横向柱状图 |

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | FastAPI + Uvicorn |
| 数据库 | SQLite + SQLAlchemy (async) |
| 数据处理 | Pandas + OpenPyXL |
| 意图引擎 | Flue Agent (Node.js) → DeepSeek API（**唯一 LLM 入口**） |
| 前端 | Vue 3 + Vite + Pinia + Vue Router |
| 图表 | ECharts 5 |
| 认证 | JWT |
| 代码智能 | CodeGraph（语义代码索引 + MCP 工具） |

> **LLM 使用现状**：系统通过 Flue Agent 调用 DeepSeek API，是唯一实际使用的 LLM。`backend/llm/` 中的 `openai_provider.py` 和 `claude_provider.py` 为死代码（配置了但未使用）。

## 快速开始

### 1. 环境准备

```bash
# Python 3.8+
pip install -r requirements.txt

# Node.js 18+（Flue Agent + 前端）
cd flue-agent && npm install
cd ../frontend && npm install
```

### 2. 配置

```bash
cp .env.example .env
```

编辑 `.env`，最少配置：

```env
# LLM（通过 Flue Agent 调用 DeepSeek）
LLM_PROVIDER=flue
FLUE_AGENT_URL=http://localhost:3002

# Flue Agent 配置（flue-agent/.env）
LLM_API_KEY=sk-你的DeepSeek API密钥
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
AGENT_PORT=3002

# 数据源
TICKET_EXCEL_PATH=./data.xlsx

# JWT 密钥
JWT_SECRET=改成随机字符串

# 长记忆（默认开启）
MEMORY_ENABLED=True
MEMORY_AUTO_SAVE_HISTORY=True
```

### 3. 数据库迁移

```bash
python scripts/init_db.py
python scripts/migrate_add_memory_tables.py
python scripts/create_admin.py
python scripts/create_test_users.py    # 可选：创建测试账号
```

### 4. 启动服务

Flue Agent 需**单独启动**，不随后端自动启动：

```bash
# 终端 1：启动 Flue Agent（端口 3002）
cd flue-agent && node agent-server.js

# 终端 2：启动后端（端口 8000）
python run_backend.py

# 终端 3：启动前端（端口 3000）
cd frontend && npm run dev
```

> Flue Agent 是独立的 Node.js 进程，后端通过 HTTP 调用其 `/agent/intent` 和 `/agent/chat` 端点。

### 5. 局域网访问

后端和前端均绑定 `0.0.0.0`，局域网内其他设备可通过 IP 访问：

```
前端: http://<服务器IP>:3000
后端: http://<服务器IP>:8000
```

> 需要在 `.env` 的 `CORS_ORIGINS` 中添加访问地址，并开放防火墙端口 3000、8000。

### 6. 登录

打开 `http://localhost:3000`，默认账号：

| 用户名 | 密码 | 角色 | 说明 |
|--------|------|------|------|
| `admin` | `admin123` | 管理员 | 系统管理员 |
| `zhangwei` | `test1234` | 用户 | 张伟（运维主管） |
| `lina` | `test1234` | 用户 | 李娜（服务台） |
| `wangfang` | `test1234` | 用户 | 王芳（开发工程师） |
| `liuqiang` | `test1234` | 用户 | 刘强（安全审计） |

> 各账号数据通过 `user_id` 外键隔离：会话、消息、报表、偏好、分析历史互不可见。

## 项目结构

```
├── backend/                          # FastAPI 后端
│   ├── main.py                       # 应用入口 + 生命周期管理
│   ├── config.py                     # 环境配置 (Pydantic Settings)
│   ├── database.py                   # 数据库连接
│   ├── models.py                     # SQLAlchemy 数据模型（含记忆表 + 待确认维度表）
│   ├── schemas.py                    # Pydantic 请求/响应模型
│   ├── auth.py                       # JWT 认证
│   ├── dependencies.py               # FastAPI 依赖注入
│   ├── utils.py                      # 工具函数
│   ├── routers/                      # API 路由
│   │   ├── chat.py                   # Agent 对话（含记忆 Hook + 维度待办记录）
│   │   ├── auth.py                   # 认证
│   │   ├── analytics.py              # 数据分析（支持多数据源）
│   │   ├── reports.py                # 报表管理（下钻 + 导出，数据源绑定）
│   │   ├── datasources.py            # 数据源管理（预览+确认上传）
│   │   ├── skills.py                 # Skill 管理
│   │   ── dimensions.py             # 维度管理 API
│   ├── services/                     # 业务服务
│   │   ├── ticket_processor.py       # 工单数据处理 + ProcessorManager + 动态维度发现
│   │   ├── memory_service.py         # 长记忆服务（4 种记忆）
│   │   ├── skill_engine.py           # Skill 执行（含 _dynamic 维度 + 覆盖层查询）
│   │   ├── intent_parser.py          # 意图解析（Flue + 安全网 + 规则引擎 + 覆盖层）
│   │   ├── dimension_overrides.py    # 维度覆盖层（热更新映射表）
│   │   ├── dimension_todo.py         # 维度待办清单管理器（Markdown 文件）
│   │   ├── datasource_detector.py    # 数据源切换检测
│   │   ├── chart_renderer.py         # ECharts option 生成（亮色主题）
│   │   ├── export_service.py         # HTML/Excel 导出
│   │   ├── conversation_manager.py   # 对话上下文管理（筛选累积）
│   │   └── report_generator.py       # 报表生成
│   └── llm/                          # LLM Provider
│       ├── base.py                   # 抽象基类 + 工厂函数
│       └── flue_provider.py          # Flue Agent HTTP 调用（唯一在用）
│
├── frontend/                         # Vue 3 前端
│   └── src/
│       ├── views/                    # 页面
│       │   ├── Chat.vue              # 对话主界面（含筛选标签展示）
│       │   ├── Login.vue             # 登录页
│       │   ├── ReportList.vue        # 报表列表
│       │   ├── ReportDetail.vue      # 报表详情（含下钻弹窗）
│       │   ├── DataSourceManage.vue  # 数据源管理（两阶段上传）
│       │   └── SkillManage.vue       # Skill 管理
│       ├── components/               # 组件
│       │   ├── ChartRenderer.vue     # ECharts 渲染（全屏 + PNG 下载）
│       │   ├── ChatMessage.vue       # 消息气泡
│       │   ├── ChatInput.vue         # 输入框
│       │   ├── KPICard.vue           # KPI 卡片
│       │   ├── LoadingIndicator.vue  # 加载指示器
│       │   ├── DataSourceMappingPreview.vue  # 字段映射预览
│       │   ├── DeepInsightPanel.vue  # 深度洞察面板
│       │   └── PageNavBar.vue        # 全局导航栏
│       ├── store/                    # Pinia 状态
│       │   ├── index.js              # auth / chat / analytics / report
│       │   └── datasource.js         # 多数据源状态
│       └── router/                   # 路由
│
├── flue-agent/                       # Flue Agent (Node.js)
│   ├── agent-server.js               # HTTP Agent Server（意图识别 + 闲聊）
│   ├── agents/                       # Markdown Agent 定义
│   │   └── intent-router.md          # 意图路由 Agent
│   ├── .env                          # DeepSeek API 配置
│   └── package.json
│
── internal/                         # Harness 调度层
│   ├── router/                       # 路由
│   │   ├── agent_registry.py         # Agent 注册中心
│   │   ├── skill_router.py           # Skill 调度
│   │   └── harness_router.py         # HTTP 端点
│   ├── tools/                        # MCP 工具
│   │   ├── base.py                   # 工具基类
│   │   ├── ticket_query.py           # 工单查询
│   │   ├── chart_render.py           # 图表渲染
│   │   └── report_export.py          # 报表导出
│   ├── context/                      # 上下文管理
│   │   ├── manager.py                # Token 感知窗口管理
│   │   └── compressor.py             # 对话压缩
│   ├── session/                      # 会话管理
│   │   ├── manager.py
│   │   └── models.py
│   ── memory/                       # 文件 KV 记忆存储
│       └── store.py
│
── skills/                           # Skill 定义 (SKILL.md)
│   ├── user/                         # 用户自定义技能
│   │   ├── ticket_analysis/
│   │   ├── deep_analysis/
│   │   ├── report_export/
│   │   └── data_query/
│   └── system/                       # 系统内置技能
│       └── chitchat/
│
├── docs/                             # 文档
│   └── dimension-todo.md             # 维度待办清单（用户编辑决策）
│
├── scripts/                          # 工具脚本
│   ├── init_db.py                    # 初始化数据库
│   ├── create_admin.py               # 创建管理员
│   ├── create_test_users.py          # 创建测试账号
│   ├── migrate_add_memory_tables.py  # 长记忆表迁移
│   └── process_dimension_todo.py     # 处理维度待办（审批 + 更新映射表）
│
├── .claude/                          # Claude Code 配置
│   ├── agents/                       # Agent 角色定义
│   ├── skills/                       # Skill 规范（Claude Code 代码生成参考）
│   └── codegraph/                    # CodeGraph 源码
│
├── .codegraph/                       # CodeGraph 索引数据库
├── .mcp.json                         # CodeGraph MCP 配置
├── .env.example                      # 环境变量模板
├── run_backend.py                    # 后端启动脚本
└── data.xlsx                         # 示例工单数据
```

## 架构

### 意图识别流程

```
用户消息
  ↓
_is_chitchat() — 本地规则快速检测
  ↓ 非闲聊
FlueProvider.parse_intent()
  → POST http://localhost:3002/agent/intent
    → Flue Agent 调用 DeepSeek API
    → function calling 返回 {skill_id, group_by, chart_type, filters}
  ↓ 成功
返回结果（安全网：Flue 返回 chitchat 但含分析关键词 → 走规则引擎）
  ↓ Flue 失败
FlueProvider.chat_completion() — 同一 Flue Agent 的 /agent/chat 端点
  ↓ 失败
_parse_with_rules() — 本地关键词匹配（兜底）
  ↓ 全部未匹配
group_by='_dynamic' → 动态列发现 + 记录到维度待办清单
```

### 系统架构

```
┌─────────────┐     HTTP      ──────────────────┐     HTTP      ┌──────────────┐
│  前端        │ ───────────→ │  后端 FastAPI     │ ───────────→ │  Flue Agent  │
│  Vue 3       │ ←──────────── │  (端口 8000)      │ ←──────────── │  Node.js     │
│  (端口 3000)  │              │                    │              │  (端口 3002)  │
└─────────────┘               └──────────────────┘              └──────┬───────┘
                                                                       │
                                                                OpenAI SDK
                                                                       ↓
                                                               ┌──────────────┐
                                                               │  DeepSeek API │
                                                               │  (远程)       │
                                                               └──────────────┘
```

## 数据库模型

### 核心表

| 表名 | 说明 | 关键外键 |
|------|------|----------|
| `users` | 用户账号 | — |
| `sessions` | 对话会话（含 context_summary） | `user_id` |
| `messages` | 对话消息 | `session_id`, `report_id` |
| `reports` | 分析报表（含 datasource_id 绑定） | `user_id`, `session_id`, `datasource_id` |
| `datasources` | 数据源（含 file_path） | — |
| `skills` | 分析技能 | `datasource_id` |

### 长记忆表

| 表名 | 说明 | 隔离字段 |
|------|------|----------|
| `user_preferences` | 用户偏好（常用维度、筛选条件） | `user_id` |
| `analysis_history` | 分析历史（结论、关键发现、标签） | `user_id`, `session_id`, `datasource_id` |
| `datasource_metadata` | 数据源元数据（字段结构、质量指标） | `datasource_id` |
| `pending_dimensions` | 待确认维度（动态发现 + 用户审批） | `user_id` |

## 数据隔离机制

系统通过 `user_id` 外键实现多用户数据隔离：

- **会话隔离**：每个用户只能查看自己的 `sessions` 和 `messages`
- **报表隔离**：每个用户只能查看自己的 `reports`
- **记忆隔离**：`user_preferences`、`analysis_history` 按 `user_id` 隔离
- **数据源共享**：`datasources` 全局共享，上传后所有用户可分析
- **报表数据源绑定**：报表和下钻使用创建时的 `datasource_id`，切换数据源后旧报表仍正确
- **JWT 认证**：所有 API 通过 `get_current_user` 中间件强制鉴权

## 日期筛选支持

用户在对话中使用自然语言即可过滤时间范围：

| 说法 | 自动转换 |
|------|----------|
| "五月份" / "5月" | `2026-05-01` ~ `2026-05-31` |
| "2026年3月" | `2026-03-01` ~ `2026-03-31` |
| "上个月" | 上月 1 日 ~ 上月最后一天 |
| "上周" | 上周一 ~ 上周日 |
| "本周" | 本周一 ~ 今天 |
| "最近一周" / "近7天" | 7 天前 ~ 今天 |
| "最近一个月" / "近30天" | 30 天前 ~ 今天 |
| "今年" | 今年 1 月 1 日 ~ 今天 |
| "去年" | 去年 1 月 1 日 ~ 去年 12 月 31 日 |

> 日期提取由 LLM 提示词 + 规则引擎双通道保障。

## License

MIT
