# LLM Wiki Tool - 设计文档

## 概述

基于 llm-wiki-ref.md 描述的模式，构建一个 Python CLI 工具，实现 LLM 驱动的个人知识库管理系统。用户通过命令行执行三大核心操作：Ingest（摄入源材料）、Query（查询知识库）、Lint（健康检查），LLM 负责自动维护 Wiki 的结构、索引、交叉引用和一致性。

## 架构设计

### 三层目录结构

```
your-wiki/
├── raw/              # 原始源材料（LLM 只读）
│   └── assets/       # 图片等附件
├── wiki/             # LLM 生成的 Markdown 文件
│   ├── index.md      # 索引（按类别组织）
│   ├── log.md        # 操作日志（仅追加）
│   └── ...           # 实体/概念/摘要等页面
├── schema/           # 配置文档
│   └── schema.md     # Wiki 结构、约定、工作流定义
└── llm_wiki/         # Python 工具源码（本项目）
```

### 技术方案

- **语言**: Python 3.10+
- **CLI 框架**: `click`（轻量、成熟）
- **Web 后端**: `FastAPI`（异步、自带 OpenAPI 文档）
- **Web 前端**: React 18 + Ant Design 5 + TypeScript，Vite 构建
- **LLM 调用**: `openai` SDK（兼容 OpenAI API 格式，可对接多种 LLM 服务）
- **配置管理**: YAML 配置文件（`config.yaml`），存放 API key、model、base_url 等
- **Markdown 渲染**: 前端使用 `react-markdown` 渲染 Wiki 页面
- **包管理**: `pyproject.toml` + pip（后端），`package.json` + npm/pnpm（前端，Vite 项目）

### 模块划分

```
llm_wiki/
├── __init__.py
├── cli.py            # CLI 入口，click 命令定义（含 serve 命令启动 Web）
├── config.py         # 配置加载（config.yaml）
├── llm.py            # LLM 调用封装
├── ingest.py         # Ingest 操作逻辑
├── query.py          # Query 操作逻辑
├── lint.py           # Lint 操作逻辑
├── wiki.py           # Wiki 文件读写、索引/日志管理
└── server.py         # FastAPI Web 服务，REST API

web/                  # 前端项目（React + Ant Design）
├── package.json
├── src/
│   ├── App.tsx
│   ├── main.tsx
│   ├── pages/
│   │   ├── Dashboard.tsx      # 首页仪表盘：Wiki 概览、最近操作
│   │   ├── WikiBrowser.tsx    # Wiki 页面浏览和阅读
│   │   ├── IngestPage.tsx     # 摄入源材料界面
│   │   ├── QueryPage.tsx      # 查询知识库界面
│   │   └── LintPage.tsx       # 健康检查界面
│   ├── components/
│   │   ├── MarkdownViewer.tsx # Markdown 渲染组件
│   │   ├── PageList.tsx       # 页面列表组件
│   │   └── LogViewer.tsx      # 操作日志组件
│   └── services/
│       └── api.ts             # 后端 API 调用封装
└── index.html
```

## 详细设计

### 1. 配置管理 (`config.py` + `config.yaml`)

`config.yaml` 示例：

```yaml
llm:
  api_key: "sk-xxx"           # 或通过环境变量 LLM_WIKI_API_KEY
  base_url: "https://api.openai.com/v1"
  model: "gpt-4o"

wiki:
  root: "."                    # Wiki 根目录，默认当前目录
  raw_dir: "raw"
  wiki_dir: "wiki"
  schema_dir: "schema"
```

`config.py` 核心逻辑：
- 从 `config.yaml` 加载配置
- 环境变量 `LLM_WIKI_API_KEY` 可覆盖 yaml 中的 api_key
- 提供 `get_config()` 函数返回配置字典

### 2. LLM 调用封装 (`llm.py`)

```python
def chat(messages: list[dict], config: dict) -> str:
    """调用 LLM，返回回复文本"""
```

- 使用 `openai.OpenAI` 客户端
- 支持 `base_url` 配置，兼容 OpenAI/兼容 API
- 统一的错误处理和重试逻辑

### 3. Wiki 文件管理 (`wiki.py`)

核心功能：
- `read_wiki_page(name) -> str`: 读取 wiki 页面内容
- `write_wiki_page(name, content)`: 写入/更新 wiki 页面
- `list_wiki_pages() -> list[str]`: 列出所有 wiki 页面
- `read_index() -> str`: 读取 index.md
- `update_index(entry)`: 更新 index.md（追加或修改条目）
- `append_log(action, title, details)`: 向 log.md 追加日志条目
- `read_raw_source(path) -> str`: 读取原始源材料
- `list_raw_sources() -> list[str]`: 列出所有原始源材料
- `init_wiki()`: 初始化 wiki 目录结构，创建 index.md、log.md、schema.md

index.md 格式：

```markdown
# Wiki Index

## Sources
- [source-article-title](source-article-title.md) - 一句话摘要

## Entities
- [entity-name](entity-name.md) - 一句话摘要

## Concepts
- [concept-name](concept-name.md) - 一句话摘要
```

log.md 格式：

```markdown
# Wiki Log

## [2026-04-07] ingest | Article Title
- Created: source-article-title.md
- Updated: entity-a.md, concept-b.md
- Added to index

## [2026-04-07] query | Question about X
- Generated answer based on 3 wiki pages
- Archived as: query-question-about-x.md
```

### 4. Ingest 操作 (`ingest.py`)

命令：`llm-wiki ingest <source_file>`

处理流程：
1. 读取 `raw/` 目录下的源文件内容
2. 读取当前 `wiki/index.md` 获取已有页面上下文
3. 读取 `schema/schema.md` 获取 Wiki 约定
4. 构建 prompt，让 LLM：
   - 分析源材料的关键要点
   - 生成摘要页面内容
   - 识别涉及的实体和概念
   - 判断需要创建或更新哪些页面
   - 生成 index.md 更新内容
5. LLM 返回结构化 JSON 响应，包含：
   - `summary_page`: 摘要页面（文件名 + 内容）
   - `entity_pages`: 需要创建/更新的实体页面列表
   - `concept_pages`: 需要创建/更新的概念页面列表
   - `index_updates`: index.md 更新条目
   - `key_points`: 关键要点摘要（输出给用户）
6. 将所有页面写入 `wiki/` 目录
7. 更新 `wiki/index.md`
8. 追加 `wiki/log.md` 日志
9. 输出关键要点和操作摘要给用户

对于更新已有页面的场景：读取已有页面内容，作为上下文传给 LLM，让 LLM 合并新旧内容。

### 5. Query 操作 (`query.py`)

命令：`llm-wiki query "<question>"`

处理流程：
1. 读取 `wiki/index.md`
2. 构建 prompt，让 LLM 根据索引选择相关页面
3. 读取 LLM 选定的相关页面内容
4. 构建最终 prompt，让 LLM 生成带引用的回答
5. 输出回答到终端
6. 可选：通过 `--save` 参数将回答归档为 Wiki 页面
7. 追加 log.md 日志

回答格式要求：
- 使用 Markdown 格式
- 引用来源页面（`[[page-name]]` 或 `[page-name](page-name.md)`）
- 标注信息的置信度

### 6. Lint 操作 (`lint.py`)

命令：`llm-wiki lint`

处理流程：
1. 读取所有 wiki 页面和 index.md
2. 先做基础的结构检查（不需要 LLM）：
   - 检测孤立页面（不在 index.md 中）
   - 检测断链（引用了不存在的页面）
   - 检测空页面或过短页面
3. 构建 prompt，让 LLM 做深层检查：
   - 页面间的矛盾
   - 过时的声明
   - 缺失的交叉引用
   - 应独立成页的重要概念
4. 输出检查报告
5. 可选：通过 `--fix` 参数让 LLM 自动修复发现的问题
6. 追加 log.md 日志

### 7. Init 操作

命令：`llm-wiki init`

创建完整的目录结构和初始文件：
- `raw/` 和 `raw/assets/`
- `wiki/index.md`（空索引模板）
- `wiki/log.md`（空日志模板）
- `schema/schema.md`（默认 schema 模板）
- `config.yaml`（配置模板）

### 8. CLI 入口 (`cli.py`)

```python
@click.group()
def main():
    """LLM Wiki - AI-powered personal knowledge base"""
    pass

@main.command()
def init():
    """Initialize a new LLM Wiki"""

@main.command()
@click.argument('source_file')
def ingest(source_file):
    """Ingest a source file into the wiki"""

@main.command()
@click.argument('question')
@click.option('--save', is_flag=True, help='Archive answer as wiki page')
def query(question, save):
    """Query the wiki"""

@main.command()
@click.option('--fix', is_flag=True, help='Auto-fix issues')
def lint(fix):
    """Check wiki health"""
```

## 受影响的文件

所有文件均为新建：

| 文件 | 类型 | 说明 |
|------|------|------|
| `pyproject.toml` | 新建 | 项目配置、依赖声明、CLI 入口点 |
| `llm_wiki/__init__.py` | 新建 | 包初始化 |
| `llm_wiki/cli.py` | 新建 | CLI 命令定义 |
| `llm_wiki/config.py` | 新建 | 配置加载 |
| `llm_wiki/llm.py` | 新建 | LLM 调用封装 |
| `llm_wiki/wiki.py` | 新建 | Wiki 文件读写管理 |
| `llm_wiki/ingest.py` | 新建 | Ingest 操作 |
| `llm_wiki/query.py` | 新建 | Query 操作 |
| `llm_wiki/lint.py` | 新建 | Lint 操作 |

## 边界条件和异常处理

1. **配置缺失**: 未找到 `config.yaml` 时提示用户运行 `llm-wiki init`
2. **API Key 缺失**: 明确提示需要配置 API Key
3. **源文件不存在**: `ingest` 时检查文件是否存在于 `raw/` 目录
4. **LLM 返回格式异常**: 对 LLM 的 JSON 响应做校验，异常时重试或提示
5. **Wiki 未初始化**: 操作前检查 wiki 目录结构是否完整
6. **大文件处理**: 源材料过大时截断并提示
7. **并发写入**: 单用户 CLI 工具，暂不考虑并发

## 数据流

### Ingest 数据流
```
用户 -> CLI (ingest) -> 读取 raw/source.md
                      -> 读取 wiki/index.md + schema/schema.md
                      -> 构建 prompt -> LLM API
                      -> 解析 LLM JSON 响应
                      -> 写入 wiki/ 多个页面
                      -> 更新 wiki/index.md
                      -> 追加 wiki/log.md
                      -> 输出摘要给用户
```

### Query 数据流
```
用户 -> CLI (query) -> 读取 wiki/index.md
                     -> LLM 选择相关页面
                     -> 读取相关 wiki 页面
                     -> LLM 生成回答
                     -> 输出回答给用户
                     -> (可选) 写入 wiki/ 归档
                     -> 追加 wiki/log.md
```

### Lint 数据流
```
用户 -> CLI (lint) -> 读取所有 wiki 页面
                    -> 结构检查（本地）
                    -> LLM 深层检查
                    -> 输出报告
                    -> (可选) LLM 自动修复
                    -> 追加 wiki/log.md
```

## 具体使用示例

## 具体使用示例

### 场景：K8s 集群运维操作手册 + 常见问题知识库

#### Step 1: 初始化 Wiki

```bash
mkdir k8s-ops-wiki && cd k8s-ops-wiki
llm-wiki init
```

输出：
```
Initialized LLM Wiki in /Users/me/k8s-ops-wiki
Created directories: raw/, raw/assets/, wiki/, schema/
Created files: wiki/index.md, wiki/log.md, schema/schema.md, config.yaml
Please edit config.yaml to set your LLM API key.
```

配置 `config.yaml`：
```yaml
llm:
  api_key: "sk-your-key-here"
  base_url: "https://api.openai.com/v1"
  model: "gpt-4o"
```

#### Step 2: 准备源材料

把你现有的运维文档直接放入 `raw/` 目录。格式无严格要求，Markdown、纯文本、甚至复制粘贴的内容都行：

```
raw/
├── k8s-cluster-ops-manual.md       # K8s 集群运维操作手册
├── k8s-faq.md                      # K8s 常见问题汇总
├── k8s-network-troubleshooting.md  # K8s 网络故障排查
├── incident-2026-03-20-oom.md      # 一次 OOM 故障复盘
└── k8s-upgrade-v1.29-to-v1.30.md   # 集群升级记录
```

以下是几份源材料的真实示例内容：

**`raw/k8s-cluster-ops-manual.md`**（集群运维操作手册）：

```markdown
# K8s 集群运维操作手册

## 集群信息
- 版本：v1.29.3
- 节点：3 master + 12 worker
- CNI：Calico v3.27
- Ingress：Nginx Ingress Controller v1.10
- 存储：Ceph RBD + NFS

## 日常巡检

### 检查集群状态
kubectl get nodes
kubectl get cs                        # 检查组件状态
kubectl top nodes                     # 节点资源使用率
kubectl get pods -A | grep -v Running # 非 Running 的 Pod

### 检查 etcd 健康
ETCDCTL_API=3 etcdctl \
  --endpoints=https://10.0.1.1:2379,https://10.0.1.2:2379,https://10.0.1.3:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key \
  endpoint health

### 检查证书到期时间
kubeadm certs check-expiration

## 节点操作

### 节点维护（驱逐 Pod）
kubectl cordon <node-name>                          # 标记不可调度
kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data  # 驱逐 Pod
# 维护完成后
kubectl uncordon <node-name>                        # 恢复调度

### 添加新 Worker 节点
# 在 master 上生成 join 命令
kubeadm token create --print-join-command
# 在新节点上执行输出的 join 命令
# 验证
kubectl get nodes

### 删除节点
kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data
kubectl delete node <node-name>
# 在被删除节点上执行
kubeadm reset

## 应用部署

### 滚动更新
kubectl set image deployment/<name> <container>=<image>:<tag> -n <ns>
kubectl rollout status deployment/<name> -n <ns>

### 回滚
kubectl rollout undo deployment/<name> -n <ns>
kubectl rollout undo deployment/<name> --to-revision=<n> -n <ns>

### 扩缩容
kubectl scale deployment/<name> --replicas=<n> -n <ns>
# 或 HPA
kubectl autoscale deployment/<name> --min=2 --max=10 --cpu-percent=70 -n <ns>

## 存储管理

### 查看 PV/PVC 状态
kubectl get pv
kubectl get pvc -A
# 查看卡在 Terminating 的 PVC
kubectl get pvc -A | grep Terminating

### 强制删除卡住的 PVC
kubectl patch pvc <name> -n <ns> -p '{"metadata":{"finalizers":null}}'

## 证书管理

### 续期所有证书
kubeadm certs renew all
# 重启控制面组件使新证书生效
crictl pods --name kube-apiserver -q | xargs crictl stopp
crictl pods --name kube-controller-manager -q | xargs crictl stopp
crictl pods --name kube-scheduler -q | xargs crictl stopp
```

**`raw/k8s-faq.md`**（常见问题）：

```markdown
# K8s 常见问题

## Q: Pod 一直处于 Pending 状态怎么办？
1. kubectl describe pod <pod-name> -n <ns> 查看 Events
2. 常见原因：
   - 资源不足：没有节点满足 CPU/内存 requests → kubectl top nodes 检查
   - 调度约束：nodeSelector/affinity/taint 不匹配
   - PVC 未绑定：存储卷无法挂载 → kubectl get pvc -n <ns>
3. 排查命令：
   kubectl get events -n <ns> --sort-by='.lastTimestamp' | tail -20

## Q: Pod 频繁 CrashLoopBackOff 怎么排查？
1. 查看日志：kubectl logs <pod-name> -n <ns> --previous
2. 查看退出码：kubectl describe pod <pod-name> -n <ns> | grep "Exit Code"
   - Exit Code 1: 应用异常退出
   - Exit Code 137: OOM Killed（被系统杀掉，内存不足）
   - Exit Code 143: SIGTERM（正常终止信号）
3. 检查资源限制：是否 limits 设太小导致 OOM
   kubectl get pod <pod-name> -n <ns> -o jsonpath='{.spec.containers[*].resources}'
4. 检查健康检查：liveness probe 是否配置不当导致误杀
   kubectl get pod <pod-name> -n <ns> -o jsonpath='{.spec.containers[*].livenessProbe}'

## Q: Service 无法访问后端 Pod 怎么排查？
1. 检查 Endpoints 是否关联到 Pod：
   kubectl get endpoints <svc-name> -n <ns>
   如果 Endpoints 为空，说明 selector 不匹配或 Pod 不健康
2. 检查 Pod 标签是否匹配 Service selector：
   kubectl get pods -n <ns> --show-labels
   kubectl get svc <svc-name> -n <ns> -o jsonpath='{.spec.selector}'
3. Pod 内部测试连通性：
   kubectl exec -it <pod-name> -n <ns> -- curl http://<svc-name>:<port>
4. 检查 NetworkPolicy 是否拦截了流量

## Q: 节点 NotReady 怎么处理？
1. kubectl describe node <node-name> 查看 Conditions
2. 常见原因：
   - kubelet 停止：ssh 到节点检查 systemctl status kubelet
   - 磁盘压力：DiskPressure=True → df -h 检查磁盘
   - 内存压力：MemoryPressure=True → free -h 检查
   - 容器运行时故障：systemctl status containerd
3. 查看 kubelet 日志：journalctl -u kubelet --since "30 min ago" | tail -50

## Q: Ingress 不生效 / 503 怎么排查？
1. 检查 Ingress 资源是否正确：kubectl describe ingress <name> -n <ns>
2. 检查 Ingress Controller 日志：
   kubectl logs -l app.kubernetes.io/name=ingress-nginx -n ingress-nginx --tail=100
3. 检查后端 Service 和 Endpoints 是否正常
4. 检查证书是否正确（TLS Ingress）：
   kubectl get secret <tls-secret> -n <ns> -o jsonpath='{.data.tls\.crt}' | base64 -d | openssl x509 -noout -dates

## Q: etcd 集群异常怎么处理？
1. 检查 etcd 成员状态：
   ETCDCTL_API=3 etcdctl member list
2. 检查 etcd 性能：
   ETCDCTL_API=3 etcdctl endpoint status --write-out=table
3. 如果磁盘 IOPS 不足会导致 etcd 慢，关注 WAL fsync 延迟
4. 紧急备份：
   ETCDCTL_API=3 etcdctl snapshot save /tmp/etcd-backup-$(date +%Y%m%d).db
```

**`raw/incident-2026-03-20-oom.md`**（故障复盘）：

```markdown
# 故障复盘：2026-03-20 生产环境 OOM 事件

## 时间线
- 14:30 监控告警：order-service Pod 重启
- 14:32 确认：Pod 被 OOM Killed，Exit Code 137
- 14:35 临时处理：kubectl scale deployment order-service --replicas=5 -n prod
- 14:40 排查：kubectl top pod -n prod 发现单 Pod 内存持续增长
- 15:00 根因：新版本引入的内存泄漏，缓存对象未设置过期时间
- 15:20 回滚：kubectl rollout undo deployment/order-service -n prod
- 15:25 服务恢复正常

## 根因
order-service v2.3.1 版本中，本地缓存（HashMap）未设置容量上限和 TTL，
每个请求都会往缓存写入数据，导致堆内存持续增长直到触发 OOM。

## 修复方案
1. 缓存改用 LRU + TTL 策略（Caffeine）
2. 设置 JVM 参数 -XX:+HeapDumpOnOutOfMemoryError
3. 增加内存使用率告警：Pod memory > 80% 持续 5 分钟

## 教训
1. 上线前必须做内存压测
2. 所有使用本地缓存的服务必须设置容量上限和过期时间
3. Pod resources.limits.memory 应设合理值，过大会延迟发现问题
```

#### Step 3: 摄入源材料

```bash
llm-wiki ingest raw/k8s-cluster-ops-manual.md
```

输出：
```
Ingesting: raw/k8s-cluster-ops-manual.md

Key Points:
  1. 集群 v1.29.3，3 master + 12 worker，Calico CNI
  2. 日常巡检覆盖节点状态、etcd 健康、证书到期
  3. 节点维护需 cordon → drain → 操作 → uncordon 标准流程
  4. 滚动更新/回滚/扩缩容的标准操作命令

Wiki Updates:
  [+] Created: wiki/source-k8s-cluster-ops-manual.md (源材料摘要)
  [+] Created: wiki/entity-k8s-cluster.md (实体：我们的 K8s 集群信息)
  [+] Created: wiki/entity-etcd.md (实体：etcd 集群)
  [+] Created: wiki/entity-calico.md (实体：Calico CNI)
  [+] Created: wiki/concept-rolling-update.md (概念：滚动更新与回滚)
  [+] Created: wiki/concept-node-maintenance.md (概念：节点维护流程)
  [+] Created: wiki/concept-k8s-certificate.md (概念：K8s 证书管理)
  [+] Created: wiki/procedure-daily-inspection.md (流程：日常巡检)
  [+] Created: wiki/procedure-add-worker-node.md (流程：添加 Worker)
  [+] Created: wiki/procedure-remove-node.md (流程：删除节点)
  [~] Updated: wiki/index.md (added 10 entries)
  [~] Updated: wiki/log.md

Done. 10 pages created, 2 pages updated.
```

继续摄入 FAQ：

```bash
llm-wiki ingest raw/k8s-faq.md
```

```
Ingesting: raw/k8s-faq.md

Key Points:
  1. Pod Pending 排查优先看 describe events
  2. CrashLoopBackOff 重点关注 Exit Code 判断原因类别
  3. Service 不通先检查 Endpoints 是否为空
  4. 节点 NotReady 从 kubelet → 磁盘 → 内存 → 容器运行时排查

Wiki Updates:
  [+] Created: wiki/source-k8s-faq.md
  [+] Created: wiki/procedure-pod-pending.md
  [+] Created: wiki/procedure-crashloopbackoff.md
  [+] Created: wiki/procedure-service-unreachable.md
  [+] Created: wiki/procedure-node-notready.md
  [+] Created: wiki/procedure-ingress-503.md
  [+] Created: wiki/procedure-etcd-recovery.md
  [+] Created: wiki/concept-k8s-health-probe.md (liveness/readiness)
  [+] Created: wiki/concept-k8s-network-policy.md
  [~] Updated: wiki/entity-k8s-cluster.md (添加了常见故障场景交叉引用)
  [~] Updated: wiki/entity-etcd.md (添加异常处理和备份流程)
  [~] Updated: wiki/index.md (added 9 entries)
  [~] Updated: wiki/log.md

Done. 9 pages created, 4 pages updated.
```

摄入故障复盘：

```bash
llm-wiki ingest raw/incident-2026-03-20-oom.md
```

```
Ingesting: raw/incident-2026-03-20-oom.md

Key Points:
  1. OOM Killed (Exit Code 137) 由内存泄漏引起
  2. 临时方案：扩副本；最终方案：回滚版本
  3. 教训：本地缓存必须设置容量上限和 TTL

Wiki Updates:
  [+] Created: wiki/source-incident-2026-03-20-oom.md
  [+] Created: wiki/incident-2026-03-20-oom.md (故障记录页)
  [+] Created: wiki/concept-oom-killer.md
  [~] Updated: wiki/procedure-crashloopbackoff.md (添加了 OOM 实际案例引用)
  [~] Updated: wiki/concept-rolling-update.md (添加了紧急回滚场景)
  [~] Updated: wiki/index.md
  [~] Updated: wiki/log.md

Done. 3 pages created, 4 pages updated.
```

注意：LLM 自动发现故障复盘中的 OOM 与 FAQ 中 CrashLoopBackOff (Exit Code 137) 的关联，将真实案例补充到了排障流程中。

此时 `wiki/index.md` 按类别组织所有知识：

```markdown
# Wiki Index

## Sources
- [source-k8s-cluster-ops-manual](source-k8s-cluster-ops-manual.md) - K8s 集群运维手册摘要
- [source-k8s-faq](source-k8s-faq.md) - K8s 常见问题摘要
- [source-incident-2026-03-20-oom](source-incident-2026-03-20-oom.md) - OOM 故障复盘摘要

## Entities (实体)
- [entity-k8s-cluster](entity-k8s-cluster.md) - 我们的 K8s 集群：v1.29, 3m+12w, Calico, Ceph
- [entity-etcd](entity-etcd.md) - etcd 集群：3 节点，健康检查与备份
- [entity-calico](entity-calico.md) - Calico CNI v3.27

## Concepts (概念)
- [concept-rolling-update](concept-rolling-update.md) - 滚动更新、回滚、金丝雀发布
- [concept-node-maintenance](concept-node-maintenance.md) - 节点维护：cordon/drain/uncordon
- [concept-k8s-certificate](concept-k8s-certificate.md) - K8s 证书生命周期管理
- [concept-k8s-health-probe](concept-k8s-health-probe.md) - liveness/readiness/startup 探针
- [concept-k8s-network-policy](concept-k8s-network-policy.md) - 网络策略与流量控制
- [concept-oom-killer](concept-oom-killer.md) - Linux OOM Killer 与 K8s 内存管理

## Procedures (操作/排障流程)
- [procedure-daily-inspection](procedure-daily-inspection.md) - 日常巡检清单
- [procedure-add-worker-node](procedure-add-worker-node.md) - 添加 Worker 节点
- [procedure-remove-node](procedure-remove-node.md) - 安全删除节点
- [procedure-pod-pending](procedure-pod-pending.md) - Pod Pending 排查
- [procedure-crashloopbackoff](procedure-crashloopbackoff.md) - CrashLoopBackOff 排查
- [procedure-service-unreachable](procedure-service-unreachable.md) - Service 不通排查
- [procedure-node-notready](procedure-node-notready.md) - 节点 NotReady 排查
- [procedure-ingress-503](procedure-ingress-503.md) - Ingress 503 排查
- [procedure-etcd-recovery](procedure-etcd-recovery.md) - etcd 异常恢复

## Incidents (故障记录)
- [incident-2026-03-20-oom](incident-2026-03-20-oom.md) - order-service OOM，根因内存泄漏
```

LLM 生成的 Wiki 页面示例 —— `wiki/procedure-crashloopbackoff.md`：

```markdown
---
type: procedure
related: [concept-oom-killer, concept-k8s-health-probe, entity-k8s-cluster]
sources: [source-k8s-faq, source-incident-2026-03-20-oom]
---

# Pod CrashLoopBackOff 排查流程

## 症状
Pod 反复重启，状态显示 CrashLoopBackOff。

## 排查步骤

### 1. 查看上一次崩溃日志
kubectl logs <pod-name> -n <ns> --previous

### 2. 查看退出码判断原因类别
kubectl describe pod <pod-name> -n <ns> | grep "Exit Code"

| Exit Code | 含义 | 排查方向 |
|-----------|------|---------|
| 1 | 应用异常退出 | 查看应用日志，检查配置 |
| 137 | OOM Killed | 内存不足，见下方 OOM 章节 |
| 143 | SIGTERM | 正常终止，检查是否 preStop 超时 |

### 3. 检查资源限制
kubectl get pod <pod-name> -n <ns> -o jsonpath='{.spec.containers[*].resources}'
# 确认 limits.memory 是否合理

### 4. 检查健康检查配置
kubectl get pod <pod-name> -n <ns> -o jsonpath='{.spec.containers[*].livenessProbe}'
# liveness probe 失败也会导致 Pod 被杀重启
详见 [concept-k8s-health-probe](concept-k8s-health-probe.md)

## OOM Killed 专项排查 (Exit Code 137)
真实案例：[incident-2026-03-20-oom](incident-2026-03-20-oom.md)
- 使用 kubectl top pod 观察内存趋势
- 检查是否存在内存泄漏（本地缓存未设上限、连接池未回收等）
- 临时方案：扩副本分摊压力 或 调大 limits.memory
- 详见 [concept-oom-killer](concept-oom-killer.md)

## See Also
- [procedure-node-notready](procedure-node-notready.md) - 节点级问题导致的 Pod 异常
- [concept-rolling-update](concept-rolling-update.md) - 紧急回滚操作
```

#### Step 4: 查询 —— 紧急排障

半夜值班，Pod 挂了：

```bash
llm-wiki query "Pod 一直重启，Exit Code 137，怎么处理？"
```

输出：
```
Searching wiki... found 3 relevant pages.

## Exit Code 137 (OOM Killed) 处理

Exit Code 137 表示 Pod 被 **OOM Killed**，内存超过 limits 限制。

**立即操作：**
  kubectl logs <pod-name> -n <ns> --previous     # 查看崩溃前日志
  kubectl top pod -n <ns>                          # 确认内存使用

**临时止血：**
  # 方案1：扩副本分摊压力
  kubectl scale deployment/<name> --replicas=5 -n <ns>
  # 方案2：调大内存限制
  kubectl edit deployment/<name> -n <ns>  # 修改 limits.memory

**根因排查：**
根据 [incident-2026-03-20-oom](incident-2026-03-20-oom.md) 的经验：
1. 检查是否新版本引入了内存泄漏
2. 检查本地缓存是否设置了容量上限和 TTL
3. 如确认是新版本问题，立即回滚：
   kubectl rollout undo deployment/<name> -n <ns>

**完整排查流程**: [procedure-crashloopbackoff](procedure-crashloopbackoff.md)
**OOM 原理**: [concept-oom-killer](concept-oom-killer.md)
```

#### Step 5: 查询 —— 跨文档综合

```bash
llm-wiki query "新人值班需要知道哪些东西？给一个速查手册"
```

输出：
```
Searching wiki... found 8 relevant pages.

## K8s 值班速查手册

### 日常巡检（每日执行）
详见 [procedure-daily-inspection](procedure-daily-inspection.md)
  kubectl get nodes                                # 节点状态
  kubectl get pods -A | grep -v Running            # 异常 Pod
  kubectl top nodes                                # 资源使用率

### 高频故障速查

| 现象 | 第一步 | 排查流程 |
|------|--------|---------|
| Pod Pending | `kubectl describe pod` 看 Events | [procedure-pod-pending](procedure-pod-pending.md) |
| CrashLoopBackOff | `kubectl logs --previous` 看日志 | [procedure-crashloopbackoff](procedure-crashloopbackoff.md) |
| Exit Code 137 | 确认 OOM，`kubectl top pod` | [concept-oom-killer](concept-oom-killer.md) |
| Service 不通 | `kubectl get endpoints` 是否为空 | [procedure-service-unreachable](procedure-service-unreachable.md) |
| Node NotReady | `kubectl describe node` 看 Conditions | [procedure-node-notready](procedure-node-notready.md) |
| Ingress 503 | 查 Ingress Controller 日志 | [procedure-ingress-503](procedure-ingress-503.md) |
| etcd 异常 | `etcdctl endpoint health` | [procedure-etcd-recovery](procedure-etcd-recovery.md) |

### 紧急操作
- **紧急扩容**: `kubectl scale deployment/<name> --replicas=<n> -n <ns>`
- **紧急回滚**: `kubectl rollout undo deployment/<name> -n <ns>`
- **节点隔离**: `kubectl cordon <node>` → `kubectl drain <node> --ignore-daemonsets`

### 历史故障参考
- [incident-2026-03-20-oom](incident-2026-03-20-oom.md) - OOM 事件，教训：缓存必须设 TTL

**Sources**: [source-k8s-cluster-ops-manual](source-k8s-cluster-ops-manual.md),
[source-k8s-faq](source-k8s-faq.md), [source-incident-2026-03-20-oom](source-incident-2026-03-20-oom.md)
```

归档为 Wiki 页面，下次新人直接看：

```bash
llm-wiki query "新人值班需要知道哪些东西？给一个速查手册" --save
```

```
Archived as: wiki/query-oncall-quick-reference.md
Updated: wiki/index.md, wiki/log.md
```

#### Step 6: Lint —— 发现知识缺口

```bash
llm-wiki lint
```

```
Wiki Health Check
=================

Structural Checks:
  [OK] All 22 pages registered in index.md
  [OK] No broken links
  [WARN] wiki/entity-calico.md has only 1 inbound link
  [WARN] wiki/concept-k8s-network-policy.md has only 1 inbound link

LLM Deep Analysis:
  [INFO] 多个 procedure 引用了 kubectl top 但没有 concept-k8s-resource-management.md 页面
  [INFO] 缺少 procedure-k8s-cert-renew.md：ops manual 提到了证书续期流程但没有独立流程页
  [INFO] entity-calico.md 内容过于简短，建议补充网络排查相关内容
  [INFO] incident 只有一条记录，建议摄入更多故障复盘以丰富排障经验

Issues: 0 errors, 2 warnings, 4 suggestions
```

### 核心使用循环

```
              ┌──────────────┐
              │  保存源材料    │
              │  到 raw/ 目录  │
              └──────┬───────┘
                     │
                     ▼
              ┌──────────────┐
              │ llm-wiki     │ ──→ 自动创建/更新 Wiki 页面
              │   ingest     │     更新索引和日志
              └──────┬───────┘
                     │
                     ▼
              ┌──────────────┐
              │ llm-wiki     │ ──→ 搜索相关页面，生成回答
              │   query      │     可选归档回 Wiki
              └──────┬───────┘
                     │
                     ▼
              ┌──────────────┐
              │ llm-wiki     │ ──→ 检查一致性、补全交叉引用
              │   lint        │    自动修复问题
              └──────┬───────┘
                     │
                     ▼
            持续迭代，知识不断积累
```

## 预期结果

完成后用户可以：
1. `llm-wiki init` 初始化 Wiki 项目
2. 将源材料放入 `raw/` 目录
3. `llm-wiki ingest raw/article.md` 摄入源材料，LLM 自动创建/更新 Wiki 页面
4. `llm-wiki query "某个问题"` 查询知识库，获得带引用的回答
5. `llm-wiki lint` 检查 Wiki 健康状况
6. 整个 Wiki 由 Markdown 文件组成，可用 Obsidian 浏览，可 Git 管理
