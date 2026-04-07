# LLM Wiki Tool 实现任务计划

- [x] Task 1: 项目骨架搭建（pyproject.toml + 包结构 + CLI 入口）
    - 1.1: 创建 `pyproject.toml`，声明依赖（click, openai, pyyaml, fastapi, uvicorn）、CLI 入口点 `llm-wiki`
    - 1.2: 创建 `llm_wiki/__init__.py`
    - 1.3: 创建 `llm_wiki/cli.py`，定义 click group 和 5 个子命令骨架（init/ingest/query/lint/serve）
    - 1.4: 运行 `pip install -e .` 验证 `llm-wiki --help` 可用

- [x] Task 2: 配置管理（config.py）
    - 2.1: 创建 `llm_wiki/config.py`，实现 `get_config(root_dir)` 从 `config.yaml` 加载配置
    - 2.2: 支持环境变量 `LLM_WIKI_API_KEY` 覆盖 yaml 中的 api_key
    - 2.3: 配置缺失时抛出明确错误信息

- [x] Task 3: Wiki 文件管理（wiki.py）
    - 3.1: 创建 `llm_wiki/wiki.py`，实现 `WikiManager` 类，接收 root_dir 参数
    - 3.2: 实现 `init_wiki()`：创建目录结构、index.md 模板、log.md 模板、schema.md 默认模板、config.yaml 模板
    - 3.3: 实现文件读写：`read_wiki_page`, `write_wiki_page`, `list_wiki_pages`
    - 3.4: 实现 `read_index()`, `write_index(content)` 索引管理
    - 3.5: 实现 `append_log(action, title, details)` 日志追加
    - 3.6: 实现 `read_raw_source(path)`, `list_raw_sources()` 原始材料读取

- [x] Task 4: LLM 调用封装（llm.py）
    - 4.1: 创建 `llm_wiki/llm.py`，实现 `LLMClient` 类，封装 openai SDK 调用
    - 4.2: 实现 `chat(messages, json_mode=False)` 方法，支持普通文本和 JSON 模式
    - 4.3: 错误处理：API 异常捕获、超时处理、友好错误提示

- [x] Task 5: Init 命令实现
    - 5.1: 在 `cli.py` 中实现 `init` 命令，调用 `WikiManager.init_wiki()`
    - 5.2: 检查目录是否已初始化，避免覆盖
    - 5.3: 输出创建结果信息

- [x] Task 6: Ingest 命令实现（ingest.py）
    - 6.1: 创建 `llm_wiki/ingest.py`，实现 `run_ingest(source_file, wiki_manager, llm_client)` 函数
    - 6.2: 读取源文件内容、当前 index.md、schema.md，构建 ingest prompt
    - 6.3: 设计 LLM 返回的 JSON 结构：summary_page, entity_pages, concept_pages, procedure_pages, index_updates, key_points
    - 6.4: 解析 LLM JSON 响应，处理需要更新已有页面的场景（读取旧内容传给 LLM 合并）
    - 6.5: 写入所有新建/更新的 wiki 页面
    - 6.6: 更新 index.md、追加 log.md
    - 6.7: 输出 Key Points 和操作摘要
    - 6.8: 在 `cli.py` 中连接 ingest 命令

- [x] Task 7: Query 命令实现（query.py）
    - 7.1: 创建 `llm_wiki/query.py`，实现 `run_query(question, save, wiki_manager, llm_client)` 函数
    - 7.2: 第一轮 LLM 调用：传入 index.md，让 LLM 选择相关页面列表
    - 7.3: 读取选定的 wiki 页面内容
    - 7.4: 第二轮 LLM 调用：传入页面内容和问题，生成带引用的 Markdown 回答
    - 7.5: 输出回答到终端
    - 7.6: `--save` 模式：将回答归档为 wiki 页面，更新 index.md、追加 log.md
    - 7.7: 在 `cli.py` 中连接 query 命令

- [x] Task 8: Lint 命令实现（lint.py）
    - 8.1: 创建 `llm_wiki/lint.py`，实现 `run_lint(fix, wiki_manager, llm_client)` 函数
    - 8.2: 结构检查（本地，不需要 LLM）：孤立页面、断链、空/过短页面
    - 8.3: LLM 深层检查：传入所有页面摘要，检测矛盾、缺失交叉引用、应独立成页的概念
    - 8.4: 输出检查报告
    - 8.5: `--fix` 模式：让 LLM 生成修复内容，写入 wiki 页面
    - 8.6: 追加 log.md
    - 8.7: 在 `cli.py` 中连接 lint 命令

- [x] Task 9: FastAPI 后端服务（server.py）
    - 9.1: 创建 `llm_wiki/server.py`，初始化 FastAPI app，配置 CORS
    - 9.2: 实现 Wiki 浏览 API：`GET /api/pages`（页面列表）、`GET /api/pages/{name}`（页面内容）、`GET /api/index`（索引）、`GET /api/log`（日志）
    - 9.3: 实现 Ingest API：`POST /api/ingest`（上传文件 或 指定 raw/ 下的文件路径）
    - 9.4: 实现 Query API：`POST /api/query`（提交问题，返回回答；支持 save 参数）
    - 9.5: 实现 Lint API：`POST /api/lint`（执行检查，返回报告；支持 fix 参数）
    - 9.6: 实现 Raw Sources API：`GET /api/raw`（列出原始材料）、`GET /api/raw/{name}`（查看内容）
    - 9.7: 配置静态文件服务，部署前端构建产物
    - 9.8: 在 `cli.py` 中实现 `serve` 命令：`llm-wiki serve --port 8000`

- [x] Task 10: 前端项目初始化（Vite + React + TypeScript + Ant Design）
    - 10.1: 在 `web/` 目录使用 Vite 创建 React + TypeScript 项目
    - 10.2: 安装依赖：antd, @ant-design/icons, react-router-dom, react-markdown, axios
    - 10.3: 配置 Vite：dev 模式 API 代理到 FastAPI 后端（`/api` → `http://localhost:8000`）
    - 10.4: 创建 `web/src/services/api.ts`，封装后端 API 调用

- [x] Task 11: 前端页面 - 布局与 Dashboard
    - 11.1: 创建 `App.tsx`，使用 Ant Design Layout（Sider + Content），配置 react-router-dom 路由
    - 11.2: 侧边栏导航：Dashboard、Wiki 浏览、摄入、查询、健康检查
    - 11.3: 创建 `Dashboard.tsx`：显示 Wiki 统计概览（页面总数、各类别数量）、最近操作日志、快捷操作入口

- [ ] Task 12: 前端页面 - Wiki 浏览（WikiBrowser）
    - 12.1: 左侧面板：按类别（Sources/Entities/Concepts/Procedures/Incidents）展示页面列表，使用 Ant Design Tree 或 Menu 组件
    - 12.2: 右侧面板：使用 react-markdown 渲染选中页面的 Markdown 内容
    - 12.3: 页面内链接可点击跳转到对应 Wiki 页面
    - 12.4: 顶部搜索框：输入关键词过滤页面列表

- [ ] Task 13: 前端页面 - 摄入（IngestPage）
    - 13.1: 展示 raw/ 目录下的源材料文件列表
    - 13.2: 支持选择文件执行 ingest，调用 `POST /api/ingest`
    - 13.3: 支持直接上传新文件到 raw/ 目录
    - 13.4: 显示 ingest 结果：Key Points、创建/更新的页面列表

- [ ] Task 14: 前端页面 - 查询（QueryPage）
    - 14.1: 输入框 + 发送按钮，提交问题调用 `POST /api/query`
    - 14.2: 回答区域：使用 react-markdown 渲染 LLM 返回的 Markdown 回答
    - 14.3: "归档到 Wiki" 按钮：将当前回答保存为 Wiki 页面
    - 14.4: 历史查询列表（从 log.md 中提取 query 记录）

- [ ] Task 15: 前端页面 - 健康检查（LintPage）
    - 15.1: "运行检查" 按钮，调用 `POST /api/lint`
    - 15.2: 检查结果展示：使用 Ant Design Alert/Tag 区分 OK/WARN/INFO 级别
    - 15.3: "自动修复" 按钮，调用 `POST /api/lint` 带 fix=true
    - 15.4: 修复结果展示：列出创建/更新的页面

- [ ] Task 16: 前端构建与后端集成
    - 16.1: 配置 Vite 构建输出到 `web/dist/`
    - 16.2: FastAPI 配置 StaticFiles 挂载 `web/dist/`，前端路由 fallback 到 `index.html`
    - 16.3: `llm-wiki serve` 同时提供 API 和前端页面

- [ ] Task 17: 端到端验证
    - 17.1: 运行 `llm-wiki init` 验证目录和文件创建
    - 17.2: 准备测试源材料放入 raw/，运行 `llm-wiki ingest` 验证 CLI 摄入流程
    - 17.3: 运行 `llm-wiki query` 验证 CLI 查询流程
    - 17.4: 运行 `llm-wiki lint` 验证 CLI 检查流程
    - 17.5: 运行 `llm-wiki serve`，打开浏览器验证 Web UI 各页面功能
    - 17.6: 修复验证中发现的问题
