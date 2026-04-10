"""交互式 Ingest 工作流

提供分步的、用户可审查的 ingest 流程。
"""
import re
import uuid
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, List

from llm_wiki.llm import LLMClient
from llm_wiki.wiki import WikiManager
from llm_wiki.merge_strategies import MergeStrategy, parse_strategy, merge_pages


class IngestStage(Enum):
    """Ingest 流程阶段"""
    IDLE = "idle"
    EXTRACTING = "extracting"      # 提取关键点
    REVIEWING = "reviewing"        # 用户审查关键点
    PROPOSING = "proposing"        # 提出页面方案
    APPROVING = "approving"        # 用户批准页面
    APPLYING = "applying"          # 应用更改
    COMPLETED = "completed"


class IngestSession:
    """管理单次 ingest 会话状态"""

    def __init__(self, source_file: str, wiki: WikiManager):
        self.session_id = str(uuid.uuid4())[:8]
        self.source_file = source_file
        self.wiki = wiki
        self.stage = IngestStage.IDLE

        # 数据存储
        self.source_content: str = ""
        self.key_points: List[str] = []
        self.approved_key_points: List[str] = []
        self.user_feedback: str = ""
        self.proposed_pages: List[Dict] = []
        self.approved_pages: set = set()
        self.rejected_pages: set = set()
        self.page_strategies: Dict[str, MergeStrategy] = {}

        # 结果
        self.created: List[str] = []
        self.updated: List[str] = []
        self.error: Optional[str] = None

    def to_dict(self) -> Dict:
        """转换为字典（用于序列化）"""
        return {
            "session_id": self.session_id,
            "source_file": self.source_file,
            "stage": self.stage.value,
            "key_points": self.key_points,
            "approved_key_points": self.approved_key_points,
            "proposed_pages": self.proposed_pages,
            "approved_pages": list(self.approved_pages),
            "rejected_pages": list(self.rejected_pages),
            "created": self.created,
            "updated": self.updated,
            "error": self.error,
        }


# 会话存储（内存中，生产环境可用 Redis）
_sessions: Dict[str, IngestSession] = {}


def create_session(source_file: str, wiki: WikiManager) -> IngestSession:
    """创建新的 ingest 会话"""
    session = IngestSession(source_file, wiki)
    _sessions[session.session_id] = session
    return session


def get_session(session_id: str) -> Optional[IngestSession]:
    """获取会话"""
    return _sessions.get(session_id)


def delete_session(session_id: str) -> bool:
    """删除会话"""
    if session_id in _sessions:
        del _sessions[session_id]
        return True
    return False


def extract_key_points(
    session: IngestSession,
    wiki: WikiManager,
    llm: LLMClient
) -> List[str]:
    """步骤 1: 提取关键点

    Args:
        session: Ingest 会话
        wiki: Wiki 管理器
        llm: LLM 客户端

    Returns:
        提取的关键点列表
    """
    session.stage = IngestStage.EXTRACTING

    # 读取源文件
    try:
        session.source_content = wiki.read_raw_source(session.source_file)
    except FileNotFoundError:
        session.error = f"Source file not found: {session.source_file}"
        session.stage = IngestStage.COMPLETED
        return []

    # 构建 prompt
    system_prompt = """You are analyzing a source document for a wiki.

Extract the key information from the source document.
The source document may be in English or Chinese. Handle both languages appropriately.

Focus on:
1. Main entities (systems, tools, services)
2. Important concepts and patterns
3. Procedures and how-tos
4. Specific facts and configurations

For Chinese documents:
- Identify technical terms, proper nouns, and key concepts
- Extract meaningful phrases and sentences
- Preserve technical terminology

Return JSON:
{
  "key_points": [
    "clear, concise point in the source language",
    "clear, concise point in the source language"
  ]
}

Keep points in the same language as the source. Extract 5-15 key points."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Source document:\n\n{session.source_content}"},
    ]

    try:
        result = llm.chat_json(messages)
        session.key_points = result.get("key_points", [])
        session.approved_key_points = session.key_points.copy()
        session.stage = IngestStage.REVIEWING
    except Exception as e:
        import sys
        print(f"Error in extract_key_points: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        session.error = f"LLM error: {str(e)}"
        session.stage = IngestStage.COMPLETED
        session.key_points = []
        session.approved_key_points = []

    return session.key_points


def propose_pages(
    session: IngestSession,
    wiki: WikiManager,
    llm: LLMClient,
    user_feedback: str = ""
) -> List[Dict]:
    """步骤 2: 提出页面方案

    Args:
        session: Ingest 会话
        wiki: Wiki 管理器
        llm: LLM 客户端
        user_feedback: 用户对关键点的反馈

    Returns:
        提出的页面列表
    """
    session.stage = IngestStage.PROPOSING
    session.user_feedback = user_feedback

    # 获取现有页面上下文
    schema = wiki.read_schema()
    index = wiki.read_index()
    existing_pages = _get_existing_pages_context(wiki, max_pages=10)

    # 构建关键点文本
    points_text = "\n".join(f"- {p}" for p in session.approved_key_points)

    system_prompt = f"""You are a wiki maintainer. Create wiki pages based on key points.

## Schema
{schema}

## Current Index
{index}

## Existing Pages Context
{existing_pages}

## Key Points (Approved by User)
{points_text}

{"User Feedback: " + user_feedback if user_feedback else ""}

Analyze the key points and create wiki pages. Return JSON:
{{
  "pages": [
    {{
      "filename": "page-filename",
      "action": "create" or "update",
      "strategy": "merge" or "replace",
      "content": "Full markdown content for the page"
    }}
  ]
}}

Guidelines:
1. Create separate pages for different entities, concepts, or procedures
2. Check existing pages - update instead of creating duplicates
3. Use "merge" strategy to add new information to existing pages
4. Use "replace" strategy only when you're sure you want to completely replace content
5. Follow the schema for page types (entity, concept, procedure, etc.)
6. Include proper frontmatter in content
7. The content should be complete, well-formatted markdown"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Create wiki pages from these key points.\n\nKey points:\n{points_text}"}
    ]

    try:
        result = llm.chat_json(messages)
        proposed = result.get("pages", [])
    except Exception as e:
        import sys
        print(f"Error in propose_pages: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        session.error = f"LLM error: {str(e)}"
        session.stage = IngestStage.COMPLETED
        return []

    session.proposed_pages = proposed
    session.stage = IngestStage.APPROVING

    # 设置默认合并策略
    for page in proposed:
        filename = page.get("filename", "")
        strategy_str = page.get("strategy", "merge")
        session.page_strategies[filename] = parse_strategy(strategy_str)

    return proposed


def apply_pages(
    session: IngestSession,
    wiki: WikiManager,
    approved_pages: List[str],
    rejected_pages: List[str] = None,
    strategies: Dict[str, str] = None
) -> Dict:
    """步骤 3: 应用批准的页面

    Args:
        session: Ingest 会话
        wiki: Wiki 管理器
        approved_pages: 批准的页面文件名列表
        rejected_pages: 拒绝的页面文件名列表
        strategies: 各页面的合并策略

    Returns:
        结果字典 {created, updated, errors}
    """
    from llm_wiki.frontmatter import FrontMatter

    session.stage = IngestStage.APPLYING
    session.approved_pages = set(approved_pages)
    session.rejected_pages = set(rejected_pages or [])

    # 更新策略
    if strategies:
        for filename, strategy_str in strategies.items():
            session.page_strategies[filename] = parse_strategy(strategy_str)

    # 写入页面
    for page in session.proposed_pages:
        filename = page.get("filename", "")
        if filename not in approved_pages:
            continue

        content = page.get("content", "")
        action = page.get("action", "create")
        strategy = session.page_strategies.get(filename, parse_strategy("merge"))

        if not filename.endswith(".md"):
            filename += ".md"
        path = wiki.wiki_dir / filename

        if action == "update" and path.exists():
            # 合并页面
            existing = path.read_text(encoding="utf-8")

            # 解析 front-matter，添加来源追踪
            fm = FrontMatter(existing)
            source_name = session.source_file.replace("/", "-").replace("\\", "-")
            fm.add_source(source_name)

            # 合并内容
            merged_body = merge_pages(
                fm.body,
                content,
                strategy,
                source_name
            )

            # 重新组装
            final_content = fm.render_with_new_body(merged_body)
            path.write_text(final_content, encoding="utf-8")
            session.updated.append(filename)
        else:
            # 创建新页面
            source_name = session.source_file.replace("/", "-").replace("\\", "-")
            page_type = _infer_page_type(filename)

            fm = FrontMatter.create(
                page_type=page_type,
                sources=[source_name]
            )
            final_content = fm.render_with_new_body(content)
            path.write_text(final_content, encoding="utf-8")
            session.created.append(filename)

    # 更新 index
    _update_index(wiki, session.proposed_pages, approved_pages)

    # 记录日志
    log_details = []
    if session.created:
        log_details.append(f"Created: {', '.join(session.created)}")
    if session.updated:
        log_details.append(f"Updated: {', '.join(session.updated)}")
    source_name = Path(session.source_file).stem
    wiki.append_log("ingest", source_name, log_details)

    session.stage = IngestStage.COMPLETED

    return {
        "created": session.created,
        "updated": session.updated,
        "pages_affected": session.created + session.updated,
    }


def _get_existing_pages_context(
    wiki: WikiManager,
    max_pages: int = 10
) -> str:
    """获取现有页面上下文"""
    pages = wiki.list_wiki_pages()
    if not pages:
        return "(no existing pages)"

    # 读取最近的 N 个页面
    pages = pages[-max_pages:]

    parts = []
    for name in pages:
        try:
            content = wiki.read_wiki_page(name)
            # 截断
            if len(content) > 1000:
                content = content[:1000] + "\n...(truncated)"
            parts.append(f"### {name}.md\n{content}")
        except FileNotFoundError:
            continue

    return "\n\n".join(parts)


def _update_index(
    wiki: WikiManager,
    proposed_pages: List[Dict],
    approved_pages: List[str]
) -> None:
    """更新 index.md"""
    index_text = wiki.read_index()

    for page in proposed_pages:
        filename = page.get("filename", "")
        if filename not in approved_pages:
            continue

        if not filename.endswith(".md"):
            filename += ".md"

        # 确定显示名称
        content = page.get("content", "")
        display_name = _extract_title(content) or filename

        # 确定摘要
        summary = content[:100].replace("\n", " ")
        if len(summary) >= 100:
            summary += "..."

        # 确定分区
        section = _infer_section(filename)

        line = f"- [{display_name}]({filename}) - {summary}"

        # 检查是否已存在
        if filename in index_text:
            # 替换
            pattern = re.compile(
                rf"^- \[.*?\]\({re.escape(filename)}\).*$", re.MULTILINE
            )
            index_text = pattern.sub(line, index_text)
        else:
            # 插入到正确分区
            section_header = f"## {section}"
            if section_header in index_text:
                idx = index_text.index(section_header) + len(section_header)
                newline_idx = index_text.index("\n", idx)
                index_text = (
                    index_text[:newline_idx + 1]
                    + line
                    + "\n"
                    + index_text[newline_idx + 1:]
                )
            else:
                # 分区不存在，追加
                index_text += f"\n{section_header}\n{line}\n"

    wiki.write_index(index_text)


def _extract_title(content: str) -> Optional[str]:
    """从内容中提取标题"""
    match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    return match.group(1).strip() if match else None


def _infer_page_type(filename: str) -> str:
    """从文件名推断页面类型"""
    if filename.startswith("source-"):
        return "source"
    elif filename.startswith("entity-"):
        return "entity"
    elif filename.startswith("concept-"):
        return "concept"
    elif filename.startswith("procedure-"):
        return "procedure"
    elif filename.startswith("incident-"):
        return "incident"
    elif filename.startswith("query-"):
        return "query"
    return "page"


def _infer_section(filename: str) -> str:
    """从文件名推断 index 分区"""
    if filename.startswith("source-"):
        return "Sources"
    elif filename.startswith("entity-"):
        return "Entities"
    elif filename.startswith("concept-"):
        return "Concepts"
    elif filename.startswith("procedure-"):
        return "Procedures"
    elif filename.startswith("incident-"):
        return "Incidents"
    return "Other"
