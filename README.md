# LLM Wiki

[English](#english) | [中文](#chinese)

---

<a id="chinese"></a>
## 中文

一个基于大语言模型（LLM）的个人知识库工具，受 [Andrej Karpathy 的 LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) 启发。

LLM Wiki 让你将原始文档（运维手册、FAQ、事故报告、技术文档等）自动分析、结构化后生成 Markdown Wiki 页面，并支持自然语言查询和健康检查。

## 核心特性

- **三层架构设计**：原始源材料（Raw Sources）→ LLM 生成的 Wiki → Schema 配置
- **智能摄入**：自动提取关键知识点，创建/更新 Wiki 页面
- **自然语言查询**：基于 Wiki 内容生成带引用的答案
- **健康检查**：检测孤立页面、内容矛盾、过时声明等问题
- **Web UI 界面**：可视化浏览和管理知识库
- **CLI 工具**：命令行操作，支持脚本化
- **支持多种 LLM**：兼容 OpenAI API 格式的服务

## 安装

```bash
# 克隆项目
git clone https://github.com/yourusername/llm-wiki.git
cd llm-wiki

# 安装后端
pip install -e .

# 安装前端（可选，用于 Web UI）
cd web
npm install
```

## 快速开始

### 1. 初始化 Wiki

```bash
llm-wiki init
```

这将创建 `wiki-data/` 目录结构：

```
wiki-data/
├── config.yaml    # LLM 配置文件
├── raw/           # 原始源文件
│   └── assets/    # 附件目录
├── wiki/          # LLM 生成的 Wiki 页面
│   ├── index.md   # 全局索引
│   └── log.md     # 操作日志
└── schema/        # Wiki 结构定义
    └── schema.md  # 页面类型与格式规范
```

### 2. 配置 LLM

编辑 `wiki-data/config.yaml` 或设置环境变量：

```bash
export LLM_WIKI_API_KEY="sk-your-api-key-here"
```

### 3. 摄入知识

```bash
# 添加源文件到 raw/ 目录
cp your-doc.md wiki-data/raw/

# 摄入
llm-wiki ingest wiki-data/raw/your-doc.md
```

### 4. 查询知识

```bash
llm-wiki query "如何处理这个问题？"
```

### 5. 启动 Web UI

```bash
llm-wiki serve
```

访问 `http://127.0.0.1:8000` 使用 Web 界面。

## CLI 命令

| 命令 | 说明 |
|------|------|
| `llm-wiki init [name]` | 初始化 Wiki 目录 |
| `llm-wiki ingest <file>` | 摄入源文件 |
| `llm-wiki query <question>` | 查询知识库 |
| `llm-wiki lint [--fix]` | 健康检查 |
| `llm-wiki serve` | 启动 Web UI |

使用 `--root` 或 `-r` 指定自定义数据目录：

```bash
llm-wiki --root my-wiki ingest my-wiki/raw/doc.md
```

## Web UI 功能

- **Dashboard**：总览统计和最近操作日志
- **Wiki Browser**：按类型浏览所有 Wiki 页面
- **Ingest**：上传源文件并触发摄入操作
- **Query**：自然语言查询知识库
- **Health Check**：运行健康检查并修复问题

## Wiki 页面类型

| 类型前缀 | 说明 |
|-----------|------|
| `source-*` | 原始文档摘要 |
| `entity-*` | 工具、服务、系统组件 |
| `concept-*` | 概念、模式、原则 |
| `procedure-*` | 操作步骤、排障流程 |
| `incident-*` | 事故记录、事后复盘 |
| `query-*` | 归档的查询答案 |

## 适用场景

- **技术文档管理**：运维手册、API 文档、开发指南
- **事故分析**：故障复盘、根因分析
- **竞品分析**：产品对比、市场分析
- **研究笔记**：论文阅读、文献综述
- **个人知识库**：读书笔记、学习记录

## REST API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/pages` | 列出所有 Wiki 页面 |
| GET | `/api/pages/{name}` | 获取单个页面内容 |
| POST | `/api/ingest` | 摄入源文件 |
| POST | `/api/query` | 查询知识库 |
| POST | `/api/lint` | 健康检查 |

完整 API 文档请参考 [hack/docs/usage.md](hack/docs/usage.md)。

## 开发

```bash
# 后端开发
pip install -e .

# 前端开发
cd web
npm install
npm run dev

# 构建前端
npm run build
```

## 配置参考

完整的 `config.yaml` 选项：

```yaml
llm:
  api_key: ""                              # LLM API 密钥
  base_url: "https://api.openai.com/v1"   # API 基础 URL
  model: "gpt-4o"                          # 模型名称

wiki:
  root: "."              # Wiki 根目录
  raw_dir: "raw"         # 原始文件目录
  wiki_dir: "wiki"       # Wiki 页面目录
  schema_dir: "schema"   # Schema 定义目录
```

## 许可证

MIT

---

<a id="english"></a>
## English

A personal knowledge base tool powered by Large Language Models (LLM), inspired by [Andrej Karpathy's LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).

LLM Wiki automatically analyzes and structures your raw documents (operation manuals, FAQs, incident reports, technical docs, etc.) into Markdown Wiki pages, supporting natural language queries and health checks.

## Features

- **Three-layer architecture**: Raw Sources → LLM-generated Wiki → Schema configuration
- **Smart ingestion**: Automatically extract key insights and create/update Wiki pages
- **Natural language queries**: Generate answers with citations from Wiki content
- **Health checks**: Detect orphaned pages, content contradictions, outdated statements, etc.
- **Web UI interface**: Visually browse and manage your knowledge base
- **CLI tools**: Command-line operations with script support
- **Multi-LLM support**: Compatible with OpenAI API format services

## Installation

```bash
git clone https://github.com/yourusername/llm-wiki.git
cd llm-wiki

# Install backend
pip install -e .

# Install frontend (optional, for Web UI)
cd web
npm install
```

## Quick Start

### 1. Initialize Wiki

```bash
llm-wiki init
```

This creates the `wiki-data/` directory structure:

```
wiki-data/
├── config.yaml    # LLM configuration file
├── raw/           # Raw source files
│   └── assets/    # Attachments directory
├── wiki/          # LLM-generated Wiki pages
│   ├── index.md   # Global index
│   └── log.md     # Operation log
└── schema/        # Wiki structure definitions
    └── schema.md  # Page types and format specifications
```

### 2. Configure LLM

Edit `wiki-data/config.yaml` or set environment variable:

```bash
export LLM_WIKI_API_KEY="sk-your-api-key-here"
```

### 3. Ingest Knowledge

```bash
# Add source file to raw/ directory
cp your-doc.md wiki-data/raw/

# Ingest
llm-wiki ingest wiki-data/raw/your-doc.md
```

### 4. Query Knowledge

```bash
llm-wiki query "How to handle this issue?"
```

### 5. Start Web UI

```bash
llm-wiki serve
```

Visit `http://127.0.0.1:8000` for the Web interface.

## CLI Commands

| Command | Description |
|---------|-------------|
| `llm-wiki init [name]` | Initialize Wiki directory |
| `llm-wiki ingest <file>` | Ingest source file |
| `llm-wiki query <question>` | Query knowledge base |
| `llm-wiki lint [--fix]` | Health check |
| `llm-wiki serve` | Start Web UI |

Use `--root` or `-r` to specify custom data directory:

```bash
llm-wiki --root my-wiki ingest my-wiki/raw/doc.md
```

## Web UI Features

- **Dashboard**: Overview statistics and recent operation logs
- **Wiki Browser**: Browse all Wiki pages by type
- **Ingest**: Upload source files and trigger ingestion
- **Query**: Natural language queries to knowledge base
- **Health Check**: Run health checks and fix issues

## Wiki Page Types

| Type Prefix | Description |
|-------------|-------------|
| `source-*` | Raw document summaries |
| `entity-*` | Tools, services, system components |
| `concept-*` | Concepts, patterns, principles |
| `procedure-*` | Operation steps, troubleshooting flows |
| `incident-*` | Incident records, post-mortems |
| `query-*` | Archived query answers |

## Use Cases

- **Technical documentation**: Operation manuals, API docs, development guides
- **Incident analysis**: Post-mortems, root cause analysis
- **Competitive analysis**: Product comparisons, market analysis
- **Research notes**: Paper reading, literature reviews
- **Personal knowledge base**: Reading notes, learning records

## REST API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/pages` | List all Wiki pages |
| GET | `/api/pages/{name}` | Get single page content |
| POST | `/api/ingest` | Ingest source file |
| POST | `/api/query` | Query knowledge base |
| POST | `/api/lint` | Health check |

For complete API documentation, see [hack/docs/usage.md](hack/docs/usage.md).

## Development

```bash
# Backend development
pip install -e .

# Frontend development
cd web
npm install
npm run dev

# Build frontend
npm run build
```

## Configuration Reference

Full `config.yaml` options:

```yaml
llm:
  api_key: ""                              # LLM API key
  base_url: "https://api.openai.com/v1"   # API base URL
  model: "gpt-4o"                          # Model name

wiki:
  root: "."              # Wiki root directory
  raw_dir: "raw"         # Raw files directory
  wiki_dir: "wiki"       # Wiki pages directory
  schema_dir: "schema"   # Schema definitions directory
```

## License

MIT
