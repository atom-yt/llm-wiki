# Wiki 数据目录独立化 - 完成总结

## 改动内容

### `llm_wiki/cli.py` — 核心改造
- `main` group 增加 `--root/-r` 全局选项，默认值 `"wiki-data"`
- `init` 命令增加可选 `DIRECTORY` 参数（优先级高于 `--root`）
- `ingest`/`query`/`lint`/`serve` 全部从 click.Context 读取 root 值
- `serve` 命令正确将 root 传给 `create_app(root)`

### `.gitignore` — 新建
- 添加 `wiki-data/` 忽略规则，避免数据文件被误提交

### `hack/docs/usage.md` — 文档更新
- 所有示例路径从根目录改为 `wiki-data/` 子目录
- 新增「指定数据目录」章节说明 `--root` 用法

### 清理
- 删除项目根目录下误生成的 `raw/`、`wiki/`、`schema/`、`config.yaml`

## 验证结果
- `llm-wiki --help` 正确显示 `-r, --root TEXT` 选项
- `llm-wiki init --help` 正确显示 `[DIRECTORY]` 参数
- `llm-wiki init` 默认在 `wiki-data/` 下创建完整结构
- 项目根目录保持干净
