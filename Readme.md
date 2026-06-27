# Jeffrey_AI_step_1st

> 三合一智能办公平台 — AI 驱动的 PPT / DOCX / XLSX 生成与编辑

<p align="center">
  <a href="https://gitee.com/Ldi876/step_1st"><img src="https://img.shields.io/badge/Gitee-step__1st-red?style=for-the-badge" alt="Gitee"></a>
  <a href="https://github.com/AIg-Lid/step_1st"><img src="https://img.shields.io/badge/GitHub-step__1st-black?style=for-the-badge" alt="GitHub"></a>
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue?style=for-the-badge" alt="License"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.9+-green?style=for-the-badge" alt="Python"></a>
  <a href="https://fastapi.tiangolo.com/"><img src="https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge" alt="FastAPI"></a>
</p>

---

## 项目简介

Jeffrey_AI_step_1st 是一个基于 FastAPI + DeepSeek（兼容 OpenAI 接口）的三合一智能办公平台，支持通过自然语言生成和修改 PPT、Word 文档、Excel 表格。内置 AI 文档助手（AgentScope 2.0 驱动），用户可通过对话直接操作文档内容并实时渲染。

### 核心能力

| 模块 | 功能 | 说明 |
|------|------|------|
| **PPT 生成** | 两步生成（大纲→内容） | 输入主题，AI 生成结构化大纲，再逐页填充内容 |
| **DOCX 写作** | 结构化文档导出 | 支持 heading1/2/3、paragraph、bullet 等块级格式 |
| **XLSX 表格** | 数据表格导出 | 自定义表头 + 数据行，带品牌配色样式 |
| **AI 助手** | 自然语言修改文档 | 对话式交互，Agent 返回结构化 JSON 动作直接操作文档 |

---

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| **后端框架** | FastAPI 0.115+ | 异步 API，自动生成 OpenAPI 文档 |
| **AI 引擎** | AgentScope 2.0 | 阿里巴巴 Agent 框架，支持 DeepSeek 模型 |
| **大模型** | DeepSeek Chat | 通过 OpenAI 兼容接口调用 |
| **向量数据库** | Milvus Lite 3.0 | 轻量级嵌入式向量库（无 Docker 依赖） |
| **前端** | 原生 HTML + JS | 单页应用，含 Agent 聊天面板与动作执行器 |
| **部署** | Nginx + Uvicorn | Nginx 反向代理，Uvicorn 运行 FastAPI |

---

## 项目结构

```
step_1st/
├── server_sync/                 # 服务器最新代码
│   ├── app/
│   │   ├── main.py              # FastAPI 应用入口
│   │   ├── config.py            # 配置管理（pydantic-settings）
│   │   ├── models.py            # 数据模型定义
│   │   ├── prompts.py           # AI 提示词模板
│   │   ├── themes.py            # PPT 主题配色
│   │   ├── routers/
│   │   │   ├── generate.py      # PPT 生成接口
│   │   │   ├── export_routes.py # DOCX/XLSX 导出接口
│   │   │   └── agent_routes.py  # AI 文档助手接口
│   │   └── services/
│   │       └── ppt_generator.py # PPT 生成服务
│   ├── index.html               # 前端页面（含 Agent 聊天面板）
│   ├── requirements.txt         # Python 依赖
│   ├── run.py                   # 启动脚本
│   └── .env.example             # 环境变量模板
├── chain/                       # LangChain 链式调用（旧版）
├── generation/                  # PPT 大纲生成（旧版）
├── mdtree/                      # Markdown 解析与树结构
├── pptx_static/                 # PPT 背景图与图标资源
├── templates/                   # 前端构建产物
└── Readme.md
```

---

## API 接口

### PPT 生成

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/generate_outline` | 生成 PPT 大纲（章节 + 要点） |
| `POST` | `/api/generate_content` | 根据大纲生成完整内容 |
| `POST` | `/api/export_html` | 导出 HTML 格式预览 |
| `GET` | `/api/health` | 健康检查 |

### 文档导出

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/export_docx` | 生成并下载 DOCX 文件 |
| `POST` | `/api/export_xlsx` | 生成并下载 XLSX 文件 |

### AI 文档助手

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/chat_agent` | Agent 对话，返回自然语言 + 结构化动作 |

**Agent 动作类型**：

| 文档类型 | 支持动作 |
|----------|----------|
| PPT | 修改标题、章节、要点、子要点；增删章节/要点/子要点 |
| DOCX | 追加文本（段落/标题/列表）、全文替换 |
| XLSX | 设置单元格值、添加数据行 |

---

## 快速开始

### 1. 环境准备

- Python 3.9+
- DeepSeek API Key（或任何 OpenAI 兼容接口）

### 2. 安装依赖

```bash
cd server_sync
python -m venv venv
source venv/bin/activate    # Linux/Mac
# venv\Scripts\activate     # Windows
pip install -r requirements.txt
```

### 3. 配置环境变量

创建 `.env` 文件：

```env
OPENAI_API_KEY=sk-your-deepseek-api-key
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-chat
APP_PORT=8000
DEBUG=True
```

### 4. 启动服务

```bash
python run.py
# 或
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. 访问

- 前端页面：http://127.0.0.1:8000
- API 文档：http://127.0.0.1:8000/docs（DEBUG 模式下可用）

---

## 部署

### Nginx 反向代理配置

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 前端静态页面
    location / {
        root /var/www/slideforge-ai;
        index index.html;
        try_files $uri $uri/ /index.html;
        add_header Cache-Control "no-store, no-cache, must-revalidate";
    }

    # API 反向代理
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 生产模式运行

```bash
gunicorn -b 0.0.0.0:8000 --threads 4 app.main:app > gunicorn.log 2>&1 &
```

---

## 版本历程

| 版本 | 日期 | 内容 |
|------|------|------|
| v0.5 | 2023.07 | Auto_PPT 初版，gpt-3.5 生成 PPT |
| v1.0 | 2023.07 | LangChain 重构，链式调用生成 |
| v1.5 | 2023.07 | 前端重构，多 MD 格式支持 |
| v2.0 | 2026.06 | 升级为 Jeffrey_AI 三合一平台，FastAPI 后端 |
| v2.1 | 2026.06 | 集成 AgentScope 2.0，AI 助手直接修改文档 |
| v2.2 | 2026.06 | 接入 Milvus Lite 向量数据库，支持 RAG 检索 |

---

## 仓库地址

- **Gitee**：https://gitee.com/Ldi876/step_1st
- **GitHub**：https://github.com/AIg-Lid/step_1st

---

## License

[MIT License](./LICENSE)
