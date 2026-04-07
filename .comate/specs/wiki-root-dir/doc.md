# Wiki 数据目录独立化

## 需求场景

当前 `llm-wiki init` 直接在当前目录（项目源码根目录）下创建 `raw/`、`wiki/`、`schema/`、`config.yaml`，导致 Wiki 数据文件与项目源码混在一起。需要将生成的 Wiki 数据放到独立目录中。

## 技术方案

### 方案设计

在 CLI 顶层 group 增加 `--root` 全局选项，指定 Wiki 数据目录。所有子命令通过 Click context 读取该值。

- `init` 命令增加可选的 `DIRECTORY` 参数，支持 `llm-wiki init my-wiki` 的用法
- 其他命令（ingest/query/lint/serve）统一通过 `--root` 选项指定数据目录
- **默认值为 `"wiki-data"`**，不指定时所有数据自动存放在 `./wiki-data/` 子目录

### 改造后的使用方式

```bash
# 默认初始化到 wiki-data/ 目录
llm-wiki init
# 生成: wiki-data/raw/, wiki-data/wiki/, wiki-data/schema/, wiki-data/config.yaml

# 初始化到自定义目录
llm-wiki init my-k8s-wiki

# 后续操作（默认读取 wiki-data/）
llm-wiki ingest wiki-data/raw/ops-manual.md
llm-wiki query "如何升级集群？"
llm-wiki serve

# 指定其他数据目录
llm-wiki --root my-k8s-wiki ingest my-k8s-wiki/raw/ops-manual.md
llm-wiki --root my-k8s-wiki query "如何升级集群？"
llm-wiki --root my-k8s-wiki serve
```

## 受影响文件

### 1. `llm_wiki/cli.py` — 核心改动

**修改 `main` group**：增加 `--root` 选项，存入 click.Context

```python
@click.group()
@click.option("--root", "-r", default=".", help="Wiki data directory")
@click.pass_context
def main(ctx, root):
    """LLM Wiki - AI-powered personal knowledge base"""
    ctx.ensure_object(dict)
    ctx.obj["root"] = root
```

**修改 `init` 命令**：增加可选 DIRECTORY 参数，优先使用该参数，其次用 `--root`

```python
@main.command()
@click.argument("directory", default=None, required=False)
@click.pass_context
def init(ctx, directory):
    """Initialize a new LLM Wiki in DIRECTORY (default: current dir)"""
    root = directory or ctx.obj["root"]
    wm = _wiki(root)
    ...
```

**修改其他命令**（ingest/query/lint/serve）：从 context 读取 root

```python
@main.command()
@click.argument("source_file")
@click.pass_context
def ingest(ctx, source_file):
    root = ctx.obj["root"]
    wm = _wiki(root)
    ...
```

### 2. `llm_wiki/server.py:67` — `create_app` 函数

无需改动，`create_app(root_dir)` 已接受 root_dir 参数，只需 CLI 侧正确传入即可。

### 3. `hack/docs/usage.md` — 更新使用文档

更新初始化和命令示例，体现 `--root` 选项和 `init DIRECTORY` 用法。

## 边界条件

- `init` 的 DIRECTORY 参数和 `--root` 同时指定时，DIRECTORY 参数优先
- 指定的目录不存在时，`init` 命令负责创建（`WikiManager.init_wiki` 已有 `mkdir(parents=True)` 逻辑）
- `--root` 默认值 `"."` 保持向后兼容
