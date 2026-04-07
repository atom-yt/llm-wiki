# Wiki 数据目录独立化 - 任务计划

- [x] Task 1: 改造 CLI 全局选项与命令参数
    - 1.1: `main` group 增加 `--root/-r` 选项，默认值 `"wiki-data"`，存入 click.Context
    - 1.2: `init` 命令增加可选 `DIRECTORY` 参数，优先使用该参数，其次用 context 中的 root
    - 1.3: `ingest`、`query`、`lint`、`serve` 命令改为从 context 读取 root，传入 `_wiki()` 和 `_llm_client()`
    - 1.4: `serve` 命令将 root 传给 `create_app(root)`

- [x] Task 2: 清理已生成的根目录数据文件
    - 2.1: 删除项目根目录下误生成的 `raw/`、`wiki/`、`schema/`、`config.yaml`（如果存在）

- [x] Task 3: 更新使用文档
    - 3.1: 更新 `hack/docs/usage.md` 中的初始化和命令示例，体现 `--root` 选项和默认 `wiki-data` 目录

- [x] Task 4: 验证
    - 4.1: `llm-wiki --help` 显示 `--root` 选项
    - 4.2: `llm-wiki init --help` 显示 `DIRECTORY` 参数
    - 4.3: `llm-wiki init` 默认在 `wiki-data/` 下创建结构
