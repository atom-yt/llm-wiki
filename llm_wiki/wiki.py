import os
import re
from datetime import datetime
from pathlib import Path


_INDEX_TEMPLATE = """\
# Wiki Index

## Sources

## Entities

## Concepts

## Procedures

## Incidents
"""

_LOG_TEMPLATE = """\
# Wiki Log
"""

_SCHEMA_TEMPLATE = """\
# Wiki Schema

## Directory Structure
- `raw/` — Raw source materials. Immutable. LLM reads only.
- `wiki/` — LLM-generated Markdown pages. LLM owns this layer.
- `schema/` — Configuration that tells the LLM how to maintain the wiki.

## Page Types
- **source-*** — Summary of a raw source document.
- **entity-*** — A specific tool, service, system, or component.
- **concept-*** — An idea, pattern, or principle.
- **procedure-*** — Step-by-step operational or troubleshooting guide.
- **incident-*** — Post-mortem / incident record.
- **query-*** — Archived query answer.

## Page Format
Every page should include YAML front-matter:
```yaml
---
type: source | entity | concept | procedure | incident | query
related: [page-name-1, page-name-2]
sources: [source-page-name]
---
```

## Conventions
- File names use kebab-case with type prefix, e.g. `entity-nginx.md`.
- Cross-reference other wiki pages using Markdown links: `[page](page.md)`.
- index.md lists every page with a one-line summary, grouped by type.
- log.md is append-only, recording every operation with a timestamp.
"""

_CONFIG_TEMPLATE = """\
llm:
  api_key: ""           # Or set LLM_WIKI_API_KEY env variable
  base_url: "https://api.openai.com/v1"
  model: "gpt-4o"

wiki:
  root: "."
  raw_dir: "raw"
  wiki_dir: "wiki"
  schema_dir: "schema"
"""


class WikiManager:
    """Manages the three-layer wiki directory structure and file I/O."""

    def __init__(self, root_dir: str = "."):
        self.root = Path(root_dir).resolve()
        self.raw_dir = self.root / "raw"
        self.wiki_dir = self.root / "wiki"
        self.schema_dir = self.root / "schema"

    # ── Initialisation ──────────────────────────────────────────────

    def is_initialised(self) -> bool:
        return (self.wiki_dir / "index.md").exists()

    def init_wiki(self) -> list[str]:
        """Create the full directory structure and seed files.

        Returns a list of created paths (relative to root).
        """
        created: list[str] = []

        for d in [
            self.raw_dir,
            self.raw_dir / "assets",
            self.wiki_dir,
            self.schema_dir,
        ]:
            d.mkdir(parents=True, exist_ok=True)
            created.append(str(d.relative_to(self.root)) + "/")

        seed_files: list[tuple[Path, str]] = [
            (self.wiki_dir / "index.md", _INDEX_TEMPLATE),
            (self.wiki_dir / "log.md", _LOG_TEMPLATE),
            (self.schema_dir / "schema.md", _SCHEMA_TEMPLATE),
            (self.root / "config.yaml", _CONFIG_TEMPLATE),
        ]

        for path, content in seed_files:
            if not path.exists():
                path.write_text(content, encoding="utf-8")
                created.append(str(path.relative_to(self.root)))

        return created

    # ── Wiki page I/O ───────────────────────────────────────────────

    def read_wiki_page(self, name: str) -> str:
        """Read a wiki page by name (with or without .md extension)."""
        if not name.endswith(".md"):
            name += ".md"
        path = self.wiki_dir / name
        if not path.exists():
            raise FileNotFoundError(f"Wiki page not found: {name}")
        return path.read_text(encoding="utf-8")

    def write_wiki_page(self, name: str, content: str) -> Path:
        """Write (create or overwrite) a wiki page. Returns the path."""
        if not name.endswith(".md"):
            name += ".md"
        path = self.wiki_dir / name
        path.write_text(content, encoding="utf-8")
        return path

    def update_wiki_page(
        self,
        name: str,
        new_content: str,
        strategy: str = "merge",
        source_name: str = "unknown"
    ) -> Path:
        """智能更新页面（合并而非覆盖）

        Parameters
        ----------
        name : str
            页面名称
        new_content : str
            新内容
        strategy : str
            合并策略: "merge", "append", "prepend", "replace"
        source_name : str
            来源名称

        Returns
        -------
        Path
            页面路径
        """
        from llm_wiki.merge_strategies import parse_strategy, merge_pages
        from llm_wiki.frontmatter import FrontMatter

        if not name.endswith(".md"):
            name += ".md"
        path = self.wiki_dir / name

        if path.exists():
            # 页面已存在，执行合并
            existing = path.read_text(encoding="utf-8")

            # 解析 front-matter，添加来源追踪
            fm = FrontMatter(existing)
            fm.add_source(source_name)

            # 合并内容
            merge_strategy = parse_strategy(strategy)
            merged_body = merge_pages(
                fm.body,
                new_content,
                merge_strategy,
                source_name
            )

            # 重新组装
            final_content = fm.render_with_new_body(merged_body)
            path.write_text(final_content, encoding="utf-8")
        else:
            # 新建页面
            from pathlib import Path as PathLib
            page_type = _infer_page_type(name)

            fm = FrontMatter.create(
                page_type=page_type,
                sources=[source_name]
            )
            final_content = fm.render_with_new_body(new_content)
            path.write_text(final_content, encoding="utf-8")

        return path

    def wiki_page_exists(self, name: str) -> bool:
        if not name.endswith(".md"):
            name += ".md"
        return (self.wiki_dir / name).exists()

    def list_wiki_pages(self) -> list[str]:
        """Return sorted list of wiki page names (without .md)."""
        if not self.wiki_dir.exists():
            return []
        return sorted(
            p.stem
            for p in self.wiki_dir.glob("*.md")
            if p.stem not in ("index", "log")
        )

    # ── Index management ────────────────────────────────────────────

    def read_index(self) -> str:
        return (self.wiki_dir / "index.md").read_text(encoding="utf-8")

    def write_index(self, content: str) -> None:
        (self.wiki_dir / "index.md").write_text(content, encoding="utf-8")

    # ── Log management ──────────────────────────────────────────────

    def read_log(self) -> str:
        return (self.wiki_dir / "log.md").read_text(encoding="utf-8")

    def append_log(self, action: str, title: str, details: list[str],
                 pages_affected: list[str] = None,
                 metadata: dict = None) -> str:
        """Append an entry to log.md (returns entry_id).

        Parameters
        ----------
        action : str   e.g. "ingest", "query", "lint"
        title  : str   human-readable title
        details : list  bullet-point lines
        pages_affected : list  pages that were changed
        metadata : dict  additional metadata

        Returns
        -------
        str
            entry_id for the log entry
        """
        from llm_wiki.wiki_log import WikiLog

        log = WikiLog(self)
        return log.append_entry(action, title, details, pages_affected, metadata)

    # ── Schema ──────────────────────────────────────────────────────

    def read_schema(self) -> str:
        path = self.schema_dir / "schema.md"
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    # ── Raw source I/O ──────────────────────────────────────────────

    def read_raw_source(self, path: str) -> str:
        """Read a raw source file. *path* is relative to root or absolute."""
        p = Path(path)
        if not p.is_absolute():
            p = self.root / p
        if not p.exists():
            raise FileNotFoundError(f"Source file not found: {p}")
        return p.read_text(encoding="utf-8")

    def list_raw_sources(self) -> list[str]:
        """List raw source files (relative to root)."""
        if not self.raw_dir.exists():
            return []
        results = []
        for p in sorted(self.raw_dir.rglob("*")):
            if p.is_file() and "assets" not in p.relative_to(self.raw_dir).parts:
                results.append(str(p.relative_to(self.root)))
        return results

    def save_raw_source(self, filename: str, content: bytes) -> Path:
        """Save uploaded content as a raw source file."""
        path = self.raw_dir / filename
        path.write_bytes(content)
        return path

    # ── Utilities ───────────────────────────────────────────────────

    def collect_all_pages_summary(self) -> dict[str, str]:
        """Return {page_name: first_heading_or_first_line} for all pages."""
        result = {}
        for name in self.list_wiki_pages():
            try:
                text = self.read_wiki_page(name)
                # Try to extract the first heading
                for line in text.splitlines():
                    stripped = line.strip()
                    if stripped.startswith("# "):
                        result[name] = stripped.lstrip("# ").strip()
                        break
                else:
                    # fallback to first non-empty line
                    for line in text.splitlines():
                        if line.strip():
                            result[name] = line.strip()[:120]
                            break
                    else:
                        result[name] = "(empty)"
            except Exception:
                result[name] = "(error reading page)"
        return result

    def find_links_in_page(self, name: str) -> list[str]:
        """Extract wiki page links from a page (Markdown link targets)."""
        try:
            text = self.read_wiki_page(name)
        except FileNotFoundError:
            return []
        # Match [text](target.md) patterns
        links = re.findall(r"\[.*?\]\(([^)]+\.md)\)", text)
        return [l.replace(".md", "") for l in links]


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
