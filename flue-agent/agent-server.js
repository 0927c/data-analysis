/**
 * Flue Agent Server — HTTP Agent Harness
 * 
 * 遵循 Flue 架构：Markdown Agent 定义 + 模型管理 + HTTP 端点
 * Python 后端通过 HTTP 调用此服务进行意图识别和闲聊。
 */

import OpenAI from "openai";
import { readFileSync, existsSync, readdirSync, statSync } from "fs";
import { createServer } from "http";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";
import "dotenv/config";

// 全局错误捕获，防止进程崩溃
process.on("uncaughtException", (err) => {
  console.error("UNCAUGHT EXCEPTION:", err.message, err.stack?.slice(0, 200));
});
process.on("unhandledRejection", (err) => {
  console.error("UNHANDLED REJECTION:", err?.message || err);
});

const __dirname = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = resolve(__dirname, "..");
const AGENTS_DIR = resolve(__dirname, "agents");
const SKILLS_DIR = resolve(PROJECT_ROOT, "harness", "skills");

// ── 初始化 OpenAI 客户端 ─────────────────────────────────
const client = new OpenAI({
  apiKey: process.env.LLM_API_KEY || process.env.DEEPSEEK_API_KEY,
  baseURL: process.env.LLM_BASE_URL || "https://api.deepseek.com",
});

const MODEL = process.env.LLM_MODEL || "deepseek-chat";
const PORT = parseInt(process.env.AGENT_PORT || "3002");

// ── Agent 定义（从 AGENTS.md 加载） ──────────────────────
function loadAgentDefinition() {
  const agentPath = resolve(AGENTS_DIR, "intent-router.md");
  if (!existsSync(agentPath)) return null;
  const content = readFileSync(agentPath, "utf-8");
  const m = content.match(/^---\s*\n([\s\S]*?)\n---/);
  if (!m) return null;
  const meta = {};
  for (const line of m[1].split("\n")) {
    const idx = line.indexOf(":");
    if (idx > 0) meta[line.slice(0, idx).trim()] = line.slice(idx + 1).trim();
  }
  return meta;
}

// ── Skill 加载（从 Markdown 文件） ────────────────────────
function loadSkills() {
  const skills = {};
  if (!existsSync(SKILLS_DIR)) return skills;
  for (const entry of readdirSync(SKILLS_DIR)) {
    const skillDir = resolve(SKILLS_DIR, entry);
    if (!statSync(skillDir).isDirectory()) continue;
    const mdPath = resolve(skillDir, "SKILL.md");
    if (!existsSync(mdPath)) continue;
    const content = readFileSync(mdPath, "utf-8");
    const m = content.match(/^---\s*\n([\s\S]*?)\n---/);
    if (!m) continue;
    const meta = {};
    for (const line of m[1].split("\n")) {
      const idx = line.indexOf(":");
      if (idx > 0) meta[line.slice(0, idx).trim()] = line.slice(idx + 1).trim();
    }
    if (meta.id) skills[meta.id] = { ...meta, content };
  }
  return skills;
}

// ── Tool 定义（内置） ─────────────────────────────────────
const TOOLS = [
  {
    type: "function",
    function: {
      name: "intent_parse",
      description: "解析用户意图，分类为数据分析请求或普通对话",
      parameters: {
        type: "object",
        properties: {
          skill_id: {
            type: "string",
            enum: ["ticket_analysis", "chitchat"],
            description: "匹配到的技能ID",
          },
          group_by: {
            type: "string",
            description: "如果ticket_analysis，分组的维度",
          },
          chart_type: {
            type: "string",
            enum: ["pie", "bar", "line", "horizontal_bar", "stacked_bar"],
            description: "推荐的图表类型",
          },
          filters: {
            type: "object",
            description: "提取的过滤条件",
            additionalProperties: true,
          },
          reasoning: {
            type: "string",
            description: "简短的原因说明",
          },
        },
        required: ["skill_id"],
      },
    },
  },
];

// ── HTTP Server ──────────────────────────────────────────
const server = createServer(async (req, res) => {
  // CORS
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "POST, GET, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  
  let responded = false;
  function send(status, data) {
    if (responded) return;
    responded = true;
    res.writeHead(status, { "Content-Type": "application/json" });
    res.end(JSON.stringify(data));
  }

  if (req.method === "OPTIONS") {
    send(204, {});
    return;
  }

  const url = new URL(req.url, `http://localhost:${PORT}`);

  try {
    // ── 健康检查 ──────────────────────────────────────
    if (url.pathname === "/health" && req.method === "GET") {
      send(200, { status: "ok", model: MODEL, agent: "intent-router" });
      return;
    }

    // ── 意图识别 ──────────────────────────────────────
    if (url.pathname === "/agent/intent" && req.method === "POST") {
      const body = await readBody(req);
      const { message, context } = body;

      const systemPrompt = `你是一个ITSM工单系统的意图识别Agent。
请判断用户的意图属于以下哪类：
1. **ticket_analysis** — 用户想查询、分析工单数据（如：查看状态分布、各系统工单数、故障原因等）
2. **chitchat** — 用户闲聊、问好、提问与数据无关的问题（如：你是谁、今天天气等）

如果是ticket_analysis，请进一步提取：
- group_by: 按什么维度分组（status/service_group/assignee/department/source/fault_group/business_system/weekly/monthly/sla/resolver/recurring）
- chart_type: 推荐图表类型（pie/bar/line/horizontal_bar/stacked_bar）
- filters: 任何过滤条件

用户消息: "${message}"`;

      const response = await client.chat.completions.create({
        model: MODEL,
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: message },
        ],
        tools: TOOLS,
        tool_choice: "required",
        temperature: 0.1,
        max_tokens: 500,
      });

      const choice = response.choices[0];
      let result;

      if (choice.finish_reason === "tool_calls" && choice.message.tool_calls) {
        const call = choice.message.tool_calls[0];
        result = JSON.parse(call.function.arguments);
      } else {
        // Fallback
        const content = choice.message.content || "";
        result = {
          skill_id: content.includes("ticket_analysis") ? "ticket_analysis" : "chitchat",
          reasoning: content.slice(0, 200),
        };
      }

      send(200, result);
      return;
    }

    // ── 闲聊/问答 ────────────────────────────────────
    if (url.pathname === "/agent/chat" && req.method === "POST") {
      const body = await readBody(req);
      const { message, chat_history, data_context } = body;

      const messages = [];

      // 如果客户端传了 system 级别的 data_context，用它作为系统提示
      const systemContent = data_context || `你是ITSM工单数据分析助手。回答原则：
- 先理解用户提问的真实意图，精准分类
- 根据数据上下文进行详细分析，给出有深度的洞察
- 识别数据中的异常模式（突发增长、集中故障、重复问题）
- 回答时引用具体数据支撑观点
- 对于分析类问题，给出可操作的改进建议
- 使用列表或分层结构让分析清晰易读`;

      messages.push({ role: "system", content: systemContent });

      if (chat_history) {
        for (const m of chat_history.slice(-6)) {
          messages.push({ role: m.role, content: m.content });
        }
      }

      messages.push({ role: "user", content: message });

      const response = await client.chat.completions.create({
        model: MODEL,
        messages,
        temperature: 0.7,
        max_tokens: 2048,
      });

      const content = response.choices[0].message.content || "";

      send(200, { message: content });
      return;
    }

    // ── 未知路由 ─────────────────────────────────────
    send(404, { error: "not found" });

  } catch (err) {
    console.error("Agent error:", err.message);
    send(500, { error: err.message });
  }
});

// ── 启动 ────────────────────────────────────────────────
server.listen(PORT, "0.0.0.0", () => {
  const agent = loadAgentDefinition();
  const skills = loadSkills();
  console.log(`\n  ✓ Flue Agent 已启动`);
  console.log(`  • 端点: http://localhost:${PORT}`);
  console.log(`  • 模型: ${MODEL}`);
  console.log(`  • Agent: ${agent?.name || "intent-router"}`);
  console.log(`  • Skills: ${Object.keys(skills).length} 个\n`);
});

// ── 工具函数 ────────────────────────────────────────────
function readBody(req) {
  return new Promise((resolve, reject) => {
    let data = "";
    req.on("data", (chunk) => (data += chunk));
    req.on("end", () => {
      try {
        resolve(JSON.parse(data || "{}"));
      } catch {
        resolve({});
      }
    });
    req.on("error", (err) => {
      console.error("readBody error:", err.message);
      reject(err);
    });
    // 超时保护
    const timeout = setTimeout(() => {
      console.error("readBody timeout");
      reject(new Error("Request body read timeout"));
    }, 30000);
    req.on("end", () => clearTimeout(timeout));
    req.on("error", () => clearTimeout(timeout));
  });
}
