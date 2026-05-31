# ITSM 工单智能分析系统

基于 **FastAPI + Vue 3 + ECharts + MiMo LLM** 的 IT 服务台工单数据智能分析平台。支持从 Excel 导入 ITSM 工单数据，通过自然语言对话自动生成多维度可视化报表和深度洞察。

## 功能特性

### 分析维度

| 类别 | 维度 | 图表 |
|------|------|------|
| 基础分布 | 状态 / 服务组 / 部门 / 来源渠道 / 业务系统 | 饼图 |
| 人员效能 | 责任人 TOP / 解决人处理量 | 横向柱状图 |
| 趋势分析 | 每周/每月工单量、SLA 达标率周趋势 | 折线图 |
| 故障根因 | 原因类别→故障分组→症状三层钻取、故障趋势 | 横向柱状图 + 折线图 |
| 重复挖掘 | 按故障原因 + 标题关键词双向去重 | 横向柱状图 |
| 症状聚类 | 常见症状→最佳解决方案推荐、平均解决耗时 | 横向柱状图 |
| 运维质量 | 退回率/挂起率/撤单率/SLA + 周趋势 | 横向柱状图 |
| 请求人分析 | 高频请求人/部门/机构/职务分布×性质交叉 | 横向柱状图 + 柱状图 |
| 性质趋势 | 各类性质占比饼图 + 周趋势堆叠面积图 | 饼图 + 折线图 |
| 满意度 | 服务态度/技术水平/响应时效评分 | 柱状图 |

### 智能分析
- **自然语言交互** — 支持中文提问，如"哪些故障反复出现？""运维质量如何？"
- **LLM 深度分析** — MiMo 模型结合数据上下文进行根因诊断和优化建议
- **自动洞察** — 11 条规则驱动的数据洞察卡片（SLA预警/重复告警/偏差检测）
- **对话上下文** — 支持多轮对话，筛选条件可累积

### 报表导出
- HTML 格式可视化报告
- Excel 数据明细导出

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | FastAPI + Uvicorn |
| 数据库 | SQLite + SQLAlchemy (async) |
| 数据处理 | Pandas + OpenPyXL |
| 前端 | Vue 3 + Vite + Pinia + Vue Router |
| 图表 | ECharts 5 |
| AI 模型 | MiMo v2.5-pro (OpenAI 兼容协议) |
| 认证 | JWT |

## 快速开始

### 1. 环境准备

```bash
# Python 3.10+
pip install -r requirements.txt

# Node.js 18+
cd frontend && npm install
```

### 2. 配置

复制环境变量模板并填写：

```bash
cp .env.example .env
```

`.env` 配置项：

```env
# LLM
LLM_PROVIDER=openai
LLM_BASE_URL=https://api.xiaomimimo.com/v1
LLM_MODEL=mimo-v2.5-pro
LLM_API_KEY=你的API密钥

# 数据源（ITSM 导出的 Excel 文件路径）
TICKET_EXCEL_PATH=./data/tickets.xlsx

# 认证
JWT_SECRET=改成随机字符串
```

### 3. 启动

```bash
# 后端 (端口 8000)
python backend/main.py

# 前端 (端口 5173)
cd frontend && npm run dev
```

打开 `http://localhost:5173`，默认管理员账号 `admin` / `admin123`。

### 4. 上传数据

登录后进入 **数据源管理** → 上传 ITSM 导出的 Excel 文件（支持 48 字段标准 ITSM 格式）。

## 项目结构

```
├── backend/
│   ├── main.py                  # FastAPI 入口
│   ├── config.py                # 配置管理
│   ├── models.py                # SQLAlchemy 数据模型
│   ├── schemas.py               # Pydantic 请求/响应模型
│   ├── auth.py                  # JWT 认证
│   ├── routers/                 # API 路由
│   │   ├── chat.py              # Agent 对话
│   │   ├── analytics.py         # 数据分析 API
│   │   ├── reports.py           # 报表管理
│   │   └── datasources.py       # 数据源上传
│   ├── services/
│   │   ├── ticket_processor.py  # 工单数据处理引擎
│   │   ├── skill_engine.py      # Skill 执行引擎
│   │   ├── intent_parser.py     # 意图解析 (LLM + 规则)
│   │   ├── chart_renderer.py    # ECharts option 渲染
│   │   ├── export_service.py    # HTML/Excel 导出
│   │   └── conversation_manager.py
│   └── llm/
│       ├── openai_provider.py   # OpenAI 兼容协议适配
│       └── claude_provider.py   # Anthropic 协议适配
├── frontend/
│   └── src/
│       ├── views/               # Chat / ReportList / Login 等页面
│       ├── components/          # KPICard / ChartRenderer / ChatMessage
│       └── store/               # Pinia 状态管理
├── internal/                    # Harness 层 (Agent/Skill/Tool 调度)
│   ├── tools/                   # MCP 工具 (ticket_query / chart_render)
│   └── router/                  # 关键词路由 + Agent 注册
├── harness/skills/              # Skill 定义 (SKILL.md)
└── .claude/agents/              # Claude Agent 角色定义
```

## 支持的 ITSM 工单字段

系统自动映射以下 48 个标准 ITSM 字段（中文列名 → 英文变量）：

`编号` `标题` `详细` `创建时间` `请求人部门` `请求人` `创建人` `来源` `状态` `责任角色` `责任人` `请求人联系方式` `解决角色` `解决人` `解决时间` `更新人` `更新时间` `所属服务组` `所属服务` `所属业务系统` `所属业务系统模块` `是否评价` `服务态度` `技术水平` `响应时效` `评价内容` `SLA百分比` `是否挂起过` `挂起时长` `挂起原因` `症状` `是否退回过服务台` `故障原因` `性质` `解决办法` `来源渠道` `故障原因分组` `流程链信息` `请求人机构` `请求人职务` `原因类别` `处理方式` `是否撤单` `备注1`

## License

MIT
