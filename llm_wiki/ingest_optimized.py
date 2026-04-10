"""Optimized ingest with streaming progress support."""

from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class IngestProgressUpdate:
    """Progress update for streaming ingest."""

    def __init__(
        self,
        stage: str,
        progress: int,
        message: str,
        key_points: Optional[list] = None,
        created: Optional[list] = None,
        updated: Optional[list] = None,
    ):
        self.stage = stage
        self.progress = progress
        self.message = message
        self.key_points = key_points or []
        self.created = created or []
        self.updated = updated or []

    def to_dict(self):
        return {
            "stage": self.stage,
            "progress": self.progress,
            "message": self.message,
            "key_points": self.key_points,
            "created": self.created,
            "updated": self.updated,
        }


class AsyncIngestManager:
    """Manager for async ingest operations with progress callbacks."""

    def __init__(self, wiki, llm):
        self.wiki = wiki
        self.llm = llm

    def run_ingest(self, source_file: str, progress_callback):
        """Run ingest operation with progress callbacks."""
        source_content = self.wiki.read_raw_source(source_file)
        source_name = Path(source_file).stem

        progress_callback(IngestProgressUpdate(
            stage="analyzing",
            progress=10,
            message=f"正在分析: {source_file}"
        ))

        # Build context
        schema = self.wiki.read_schema()
        index = self.wiki.read_index()
        existing_pages = _build_existing_pages_context(self.wiki, index, source_content)

        progress_callback(IngestProgressUpdate(
            stage="extracting",
            progress=20,
            message="正在提取关键点..."
        ))

        # Build prompt
        system_msg = _INGEST_SYSTEM_PROMPT.format(
            schema=schema,
            index=index,
            existing_pages=existing_pages,
        )

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": f"Process this source document:\n\n{source_content}"},
        ]

        progress_callback(IngestProgressUpdate(
            stage="analyzing",
            progress=30,
            message="LLM 正在处理..."
        ))

        # Call LLM
        result = self.llm.chat_json(messages)

        key_points = result.get("key_points", [])
        pages = result.get("pages", [])
        index_entries = result.get("index_entries", [])

        progress_callback(IngestProgressUpdate(
            stage="analyzing",
            progress=50,
            message=f"提取到 {len(key_points)} 个关键点",
            key_points=key_points
        ))

        # Write pages
        created = []
        updated = []
        total_pages = len(pages) or 1

        for i, page in enumerate(pages):
            progress = 50 + (i + 1) / total_pages * 30
            filename = page.get("filename", "")
            progress_callback(IngestProgressUpdate(
                stage="writing",
                progress=int(progress),
                message=f"正在写入页面: {filename}"
            ))

            content = page.get("content", "")
            if "summary" in page and "sections" in page and not content:
                sections = page.get("sections", [])
                content = f"# {page.get('summary', '')}\n\n"
                for section in sections:
                    content += f"## {section}\n\n"

            action = page.get("action", "create")
            self.wiki.write_wiki_page(filename, content)
            if action == "update":
                updated.append(filename)
            else:
                created.append(filename)

        # Update index
        progress_callback(IngestProgressUpdate(
            stage="updating",
            progress=90,
            message="正在更新索引"
        ))

        if index_entries:
            _update_index(self.wiki, index_entries, source_name)

        # Log
        progress_callback(IngestProgressUpdate(
            stage="logging",
            progress=95,
            message="正在记录日志"
        ))

        self.wiki.log_ingest(
            source_file=source_file,
            key_points=key_points,
            pages_created=created,
            pages_updated=updated,
        )

        return {
            "key_points": key_points,
            "created": created,
            "updated": updated,
        }


def _build_existing_pages_context(wiki, index: str, source_content: str) -> str:
    """Build context from existing pages that might be related."""
    if not index:
        return ""

    # Simple keyword matching to find related pages
    lines = index.split('\n')
    related = []
    for line in lines[:50]:  # Limit to first 50 entries
        if line.strip():
            related.append(line.strip())

    return '\n'.join(related[:20]) if related else ""


_INGEST_SYSTEM_PROMPT = """你是一个智能知识库助手，负责从源文档中提取结构化知识并创建/更新 Wiki 页面。

当前知识库结构:
- Schema: {schema}
- Index: {index}
- Existing pages context: {existing_pages}

请分析提供的源文档并返回JSON格式的响应，包含以下字段:
- key_points: 从文档中提取的5-10个关键知识点（简短的要点）
- pages: 需要创建或更新的页面列表，每个页面包含:
  - filename: 页面文件名（如 procedures/upgrade_k8s.md）
  - title: 页面标题
  - action: "create" 或 "update"
  - content: 完整的 Markdown 内容（可选，如果提供 summary 和 sections 则自动生成）
  - summary: 页面摘要（可选）
  - sections: 页面章节列表（可选）
- index_entries: 需要添加到索引的条目列表（可选），每个条目包含:
  - term: 索引词
  - link: 指向的页面文件名

对于中文文档:
- 识别技术术语、专有名词和关键概念
- 提取有意义的短语和句子
- 保留专业术语

请始终返回有效的JSON。"""


def _update_index(wiki, index_entries: list, source_name: str = ""):
    """Update wiki index with new entries."""
    if not index_entries:
        return

    try:
        current_index = wiki.read_index() or ""
        lines = current_index.split('\n')

        # Add new entries
        for entry in index_entries:
            term = entry.get("term", "")
            link = entry.get("link", "")
            if term and link:
                new_line = f"- {term} -> [[{link}]]"
                if new_line not in lines:
                    lines.append(new_line)

        wiki.write_index('\n'.join(lines))
    except Exception as e:
        logger.error(f"Failed to update index: {e}")
