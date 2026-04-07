# LLM Wiki - 剩余任务

- [x] Task 1-11: 后端核心模块 + 前端基础设施 + Dashboard (已完成)

- [x] Task 12: 前端页面 - Wiki 浏览（WikiBrowser）
    - 12.1: 左侧展示 wiki 页面列表，按类型分组（Sources/Entities/Concepts/Procedures/Incidents/Queries）
    - 12.2: 右侧展示选中页面的 Markdown 内容（MarkdownViewer）
    - 12.3: 搜索过滤功能
    - 12.4: 页面间导航（点击 wiki 内链跳转）

- [x] Task 13: 前端页面 - 摄入（IngestPage）
    - 13.1: 文件上传功能（拖拽/选择）
    - 13.2: 已有源文件列表展示
    - 13.3: 触发 ingest 操作，展示结果（key_points / created / updated）

- [x] Task 14: 前端页面 - 查询（QueryPage）
    - 14.1: 问题输入框 + 提交按钮
    - 14.2: 查询结果展示（answer + selected_pages）
    - 14.3: 可选的保存查询功能（save checkbox）

- [x] Task 15: 前端页面 - 健康检查（LintPage）
    - 15.1: 触发 lint 操作按钮
    - 15.2: 结构问题列表展示
    - 15.3: LLM 深度分析问题列表
    - 15.4: 可选 fix 模式

- [x] Task 16: 前端构建与后端集成
    - 16.1: npm run build 构建前端
    - 16.2: 确认 server.py 静态文件服务配置正确

- [x] Task 17: 端到端验证
    - 17.1: 启动后端验证 API 可用
    - 17.2: 验证前端页面可访问
