# LLM Wiki 文档总结

## 核心概念

这是一个关于使用大语言模型（LLM）构建**个人知识库**的模式。

### 传统 RAG 的局限
大多数人与 LLM 的交互基于 RAG（检索增强生成）：上传文件，查询时检索相关片段，生成答案。这种方式每次都需要重新发现知识，没有积累，没有持久化的知识结构。

### LLM Wiki 的创新
不同于传统 RAG，LLM Wiki 让 LLM **增量构建和维护一个持久的 Wiki** —— 一个结构化、相互链接的 Markdown 文件集合，位于你和原始源材料之间。

**关键区别：Wiki 是一个持久的、复合的产物。** 交叉引用已经存在，矛盾已被标记，综合已经反映你读过的所有内容。

## 三层架构

| 层级 | 说明 |
|------|------|
| **Raw Sources** | 你精心整理的原始文档（文章、论文、图片、数据）。不可变，LLM 只读取不修改。这是你的真理之源。 |
| **The Wiki** | LLM 生成的 Markdown 文件目录。摘要、实体页面、概念页面、对比、概览、综合。LLM 完全拥有这一层。你读，LLM 写。 |
| **The Schema** | 告诉 LLM Wiki 结构、约定、工作流的配置文档（如 CLAUDE.md）。这是让 LLM 成为纪律性 Wiki 维护者的关键。 |

## 三大操作

### 1. Ingest（摄入）
将新源材料放入原始集合，让 LLM 处理：
1. 读取源材料
2. 与你讨论关键要点
3. 在 Wiki 中写摘要页
4. 更新索引
5. 更新相关的实体和概念页
6. 在日志中追加条目

单个源可能触及 10-15 个 Wiki 页面。

### 2. Query（查询）
向 Wiki 提问，LLM 搜索相关页面并生成带引用的答案。答案可以有多种形式：
- Markdown 页面
- 对比表格
- 幻灯片
- 图表
- Canvas

**重要：好的答案可以归档回 Wiki 作为新页面。**

### 3. Lint（健康检查）
定期让 LLM 检查 Wiki：
- 页面间的矛盾
- 被新源材料取代的过时声明
- 没有入链的孤立页面
- 缺少独立页面的重要概念
- 缺失的交叉引用
- 可通过网络搜索填补的数据空白

## 索引和日志

### index.md
- 面向内容的目录
- 列出每个页面，包含链接、一句话摘要、元数据
- 按类别组织（实体、概念、源等）
- 每次摄入时更新
- 问答时 LLM 先读取索引，再深入相关页面

### log.md
- 按时间顺序记录
- 仅追加，记录发生的事件和时间
- 建议使用一致前缀（如 `## [2026-04-02] ingest | Article Title`）
- 可用 unix 工具解析，如 `grep "^## \[" log.md \| tail -5`

## 适用场景

- **个人**：追踪目标、健康、心理学、自我提升
- **研究**：深入某个话题数月，读论文、文章、报告，构建 evolving thesis
- **读书**：为角色、主题、情节线索建立页面及其关联
- **商业/团队**：由 LLM 维护的内部 Wiki，源材料来自 Slack、会议记录、项目文档、客户通话
- **竞品分析、尽职调查、旅行规划、课程笔记、爱好深度钻研**

## 如何上手实践

### 1. 准备工具
- **Obsidian** 作为 Wiki 的 IDE
- **Obsidian Web Clipper** 浏览器扩展（将网页文章转为 Markdown）
- LLM Agent（Claude Code、OpenAI Codex 等）

### 2. 设置目录结构
```
your-wiki/
├── raw/           # 原始源材料
│   └── assets/    # 图片附件
├── wiki/          # LLM 生成的 Markdown 文件
│   ├── index.md   # 索引
│   ├── log.md     # 日志
│   └── ...        # 其他页面
└── schema/        # 配置文档
    └── CLAUDE.md  # 或 AGENTS.md
```

### 3. 配置 Obsidian
1. 设置固定附件文件夹路径：Settings → Files and links → Attachment folder path → `raw/assets/`
2. 绑定快捷键下载附件：Settings → Hotkeys → 搜索 "Download" → 绑定快捷键（如 Ctrl+Shift+D）

### 4. 编写 Schema（关键）
在 `CLAUDE.md` 中定义：
- Wiki 的目录结构
- 页面格式约定
- 摄入源材料的工作流程
- 回答问题的流程
- 维护 Wiki 的规则

### 5. 开始实践
1. **摄入第一个源材料**：用 Web Clipper 保存一篇文章
2. 让 LLM 处理：讨论要点、写摘要、更新索引和日志
3. **在 Obsidian 中查看结果**：浏览页面、检查图形视图
4. **持续迭代**：加入更多源材料，提问，让答案归档回 Wiki
5. **定期 Lint**：检查 Wiki 健康状况

### 6. 可选增强
- **qmd**：本地 Markdown 搜索引擎，混合 BM25/向量搜索和 LLM 重排序
- **Marp**：基于 Markdown 的幻灯片格式
- **Dataview**：Obsidian 插件，可查询页面 frontmatter
- Git：Wiki 就是 Markdown 文件的 git 仓库，自带版本历史和协作能力

## 为什么有效

维护知识库最繁琐的部分是**记录工作**——更新交叉引用、保持摘要最新、标记新旧数据矛盾、维护数十页的一致性。人类放弃 Wiki 是因为维护负担增长快于价值。

LLM 不会厌倦，不会忘记更新交叉引用，可以一次修改 15 个文件。Wiki 保持被维护，因为维护成本接近于零。

---

> 人类的工作是策划源材料、指导分析、提出好问题、思考这一切意味着什么。LLM 的工作是其他一切。

## 相关资源

- 原文：https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
- qmd（搜索工具）：https://github.com/tobi/qmd
- Obsidian：https://obsidian.md/
- Tolkien Gateway 示例：https://tolkiengateway.net/wiki/Main_Page
