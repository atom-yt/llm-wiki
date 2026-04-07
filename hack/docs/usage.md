# LLM Wiki 使用文档

LLM Wiki 是一个基于大语言模型的个人知识库工具。它将原始文档（运维手册、FAQ、事故报告等）自动分析、结构化后生成 Markdown Wiki 页面，并支持自然语言查询和健康检查。

## 安装

```bash
# 克隆项目后，以可编辑模式安装
pip install -e .
```

安装完成后即可使用 `llm-wiki` 命令。

## 快速开始

### 1. 初始化 Wiki

在项目目录下执行：

```bash
llm-wiki init
```

默认在 `wiki-data/` 子目录下创建 Wiki 结构。也可以指定目录名：

```bash
llm-wiki init my-k8s-wiki
```

初始化后的目录结构：

```
wiki-data/                 # 或自定义目录名
├── config.yaml            # LLM 配置文件
├── raw/                   # 原始源文件（不可变，LLM 只读）
│   └── assets/            # 附件目录
├── wiki/                  # LLM 生成的 Wiki 页面
│   ├── index.md           # 全局索引
│   └── log.md             # 操作日志
└── schema/                # Wiki 结构定义
    └── schema.md          # 页面类型与格式规范
```

### 2. 配置 LLM

编辑 `wiki-data/config.yaml`，填入你的 LLM API 密钥：

```yaml
llm:
  api_key: "sk-your-api-key-here"
  base_url: "https://api.openai.com/v1"
  model: "gpt-4o"
```

也可以通过环境变量设置（优先级高于配置文件）：

```bash
export LLM_WIKI_API_KEY="sk-your-api-key-here"
```

**兼容接口说明**：`base_url` 支持任何兼容 OpenAI API 格式的服务，例如：
- OpenAI: `https://api.openai.com/v1`
- Azure OpenAI: 对应的 endpoint
- 本地模型（vLLM/Ollama 等）: `http://localhost:8080/v1`

### 3. 添加源文件

将原始文档放入 `wiki-data/raw/` 目录：

```bash
cp k8s-ops-manual.md wiki-data/raw/
cp k8s-faq.md wiki-data/raw/
```

### 4. 摄入知识

```bash
llm-wiki ingest wiki-data/raw/k8s-ops-manual.md
```

LLM 会分析源文件内容，自动：
- 提取关键知识点
- 创建/更新对应的 Wiki 页面（实体、概念、操作步骤等）
- 更新 `wiki/index.md` 索引
- 记录操作到 `wiki/log.md`

可以逐个摄入多个源文件：

```bash
llm-wiki ingest wiki-data/raw/k8s-faq.md
llm-wiki ingest wiki-data/raw/incident-20240301.md
```

### 5. 查询知识

```bash
llm-wiki query "如何将 K8s 集群从 1.27 升级到 1.28？"
```

查询流程：
1. LLM 根据问题从索引中选择相关页面
2. 读取选中页面的完整内容
3. 基于页面内容生成综合答案

使用 `--save` 将答案归档为 Wiki 页面：

```bash
llm-wiki query --save "节点 NotReady 怎么排查？"
```

### 6. 健康检查

```bash
llm-wiki lint
```

检查内容包括：
- **结构检查**：孤立页面（无入链）、断裂链接、内容过少的页面
- **LLM 深度分析**：知识矛盾、过时内容、缺失概念、缺失交叉引用

使用 `--fix` 让 LLM 自动修复发现的问题：

```bash
llm-wiki lint --fix
```

## 指定数据目录

所有命令默认操作 `wiki-data/` 目录。使用 `--root`（`-r`）指定其他数据目录：

```bash
# 初始化到自定义目录
llm-wiki init my-k8s-wiki

# 后续操作指向该目录
llm-wiki --root my-k8s-wiki ingest my-k8s-wiki/raw/ops-manual.md
llm-wiki --root my-k8s-wiki query "如何升级集群？"
llm-wiki --root my-k8s-wiki lint
llm-wiki --root my-k8s-wiki serve
```

## Web UI

### 启动服务

```bash
llm-wiki serve
```

默认在 `http://127.0.0.1:8000` 启动。可自定义端口和地址：

```bash
llm-wiki serve --host 0.0.0.0 --port 3000
```

### 页面功能

| 页面 | 功能 |
|------|------|
| **Dashboard** | 总览统计（页面数量按类型分组）+ 最近操作日志 |
| **Wiki Browser** | 按类型浏览所有 Wiki 页面，支持搜索过滤和页面内链跳转 |
| **Ingest** | 上传源文件（拖拽或选择）、查看已有源文件、触发摄入操作 |
| **Query** | 自然语言查询知识库，可选择将答案保存为 Wiki 页面 |
| **Health Check** | 运行健康检查，查看结构问题和 LLM 分析结果，可选自动修复 |

### 开发模式

前后端分离开发时，前端 dev server 会自动代理 API 请求到后端：

```bash
# 终端 1：启动后端
llm-wiki serve

# 终端 2：启动前端 dev server
cd web && npm run dev
```

前端开发服务运行在 `http://localhost:5173`，API 请求自动代理到 `http://127.0.0.1:8000`。

### 构建前端

```bash
cd web && npm run build
```

构建产物输出到 `web/dist/`，`llm-wiki serve` 会自动提供静态文件服务。

## Wiki 页面类型

| 类型前缀 | 说明 | 示例 |
|-----------|------|------|
| `source-*` | 原始文档摘要 | `source-k8s-ops-manual.md` |
| `entity-*` | 工具、服务、系统组件 | `entity-etcd.md`, `entity-kubelet.md` |
| `concept-*` | 概念、模式、原则 | `concept-pod-scheduling.md` |
| `procedure-*` | 操作步骤、排障流程 | `procedure-cluster-upgrade.md` |
| `incident-*` | 事故记录、事后复盘 | `incident-etcd-oom-20240301.md` |
| `query-*` | 归档的查询答案 | `query-how-to-upgrade-cluster.md` |

每个页面包含 YAML front-matter：

```yaml
---
type: entity
related: [entity-kubelet, concept-pod-scheduling]
sources: [source-k8s-ops-manual]
---
```

## 页面命名规范

- 使用 kebab-case（小写字母 + 连字符），例如 `entity-nginx-ingress.md`
- 以类型前缀开头
- 页面间通过 Markdown 链接交叉引用：`[etcd](entity-etcd.md)`
- `index.md` 维护全局目录，按类型分组

## REST API

启动 `llm-wiki serve` 后，以下 API 可用：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/pages` | 列出所有 Wiki 页面 |
| GET | `/api/pages/{name}` | 获取单个页面内容 |
| GET | `/api/index` | 获取 index.md 内容 |
| GET | `/api/log` | 获取 log.md 内容 |
| GET | `/api/raw` | 列出所有源文件 |
| GET | `/api/raw/{name}` | 获取源文件内容 |
| POST | `/api/raw/upload` | 上传源文件（multipart/form-data） |
| POST | `/api/ingest` | 摄入源文件 `{"source_file": "raw/xxx.md"}` |
| POST | `/api/query` | 查询 `{"question": "...", "save": false}` |
| POST | `/api/lint` | 健康检查 `{"fix": false}` |

## 典型使用场景：K8s 运维知识库

```bash
# 初始化（默认创建 wiki-data/ 目录）
llm-wiki init

# 配置 LLM（编辑 config.yaml 或设置环境变量）
export LLM_WIKI_API_KEY="sk-xxx"

# 准备源文件
cp ~/docs/k8s-cluster-upgrade-guide.md wiki-data/raw/
cp ~/docs/k8s-common-issues-faq.md wiki-data/raw/
cp ~/docs/incident-etcd-oom-20240301.md wiki-data/raw/

# 逐个摄入
llm-wiki ingest wiki-data/raw/k8s-cluster-upgrade-guide.md
llm-wiki ingest wiki-data/raw/k8s-common-issues-faq.md
llm-wiki ingest wiki-data/raw/incident-etcd-oom-20240301.md

# 查询
llm-wiki query "etcd 集群出现 OOM 如何处理？"
llm-wiki query --save "如何安全地进行 K8s 版本升级？"

# 健康检查
llm-wiki lint
llm-wiki lint --fix

# 启动 Web UI 浏览和管理
llm-wiki serve
```

## 配置参考

完整的 `config.yaml` 选项：

```yaml
llm:
  api_key: ""                              # LLM API 密钥（必填，或用环境变量 LLM_WIKI_API_KEY）
  base_url: "https://api.openai.com/v1"   # API 基础 URL
  model: "gpt-4o"                          # 模型名称

wiki:
  root: "."              # Wiki 根目录
  raw_dir: "raw"         # 原始文件目录
  wiki_dir: "wiki"       # Wiki 页面目录
  schema_dir: "schema"   # Schema 定义目录
```
