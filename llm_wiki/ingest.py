import json
import re
from pathlib import Path

import click

from llm_wiki.llm import LLMClient
from llm_wiki.wiki import WikiManager


_INGEST_SYSTEM_PROMPT = """\
You are a wiki maintainer. Process source doc to produce structured wiki pages.

## Schema
{schema}

## Current index
{index}

## Existing pages (recent 10)
{existing_pages}

## Instructions
1. Extract key points
2. Create source-xxx.md summary
3. Create/update entity-xxx.md, concept-xxx.md, procedure-xxx.md as needed
4. Update index entries

## Output JSON (no markdown)
{{
  "key_points": ["point1", "point2"],
  "pages": [
    {{"filename": "source-xxx.md", "action": "create/update", "content": "markdown"}}
  ],
  "index_entries": [
    {{"section": "Sources/Entities/Concepts/Procedures", "filename": "source-xxx.md", "display_name": "Title", "summary": "one-line"}}
  ]
}}
"""


def _slugify(text: str) -> str:
    """Convert text to a kebab-case slug suitable for filenames."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def _build_existing_pages_context(
    wiki: WikiManager, index_text: str, source_content: str = ""
) -> str:
    """智能选择相关页面作为上下文"""
    from llm_wiki.page_selector import PageSelector

    selector = PageSelector(wiki)
    selected_pages = selector.select_for_ingest(source_content, max_pages=10)

    if not selected_pages:
        return "(no existing pages)"

    # 并行读取选定的页面
    from concurrent.futures import ThreadPoolExecutor, as_completed

    parts = []

    def read_page(name: str) -> tuple[str, str] | None:
        try:
            content = wiki.read_wiki_page(name)
            # Truncate to 1000 chars
            if len(content) > 1000:
                content = content[:1000] + "\n...(truncated)"
            return (name, content)
        except FileNotFoundError:
            return None

    # Read pages in parallel
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(read_page, name): name for name in selected_pages}
        for future in as_completed(futures):
            result = future.result()
            if result:
                name, content = result
                parts.append(f"### {name}.md\n{content}")

    return "\n\n".join(parts) if parts else "(no existing pages)"


def _update_index(wiki: WikiManager, entries: list[dict]) -> None:
    """Merge new index entries into the existing index.md."""
    index_text = wiki.read_index()

    for entry in entries:
        section = entry["section"]
        filename = entry["filename"]
        display = entry["display_name"]
        summary = entry["summary"]
        link_name = filename.replace(".md", "")
        line = f"- [{display}]({filename}) - {summary}"

        # Check if this entry already exists (by filename)
        if filename in index_text:
            # Replace existing line
            pattern = re.compile(
                rf"^- \[.*?\]\({re.escape(filename)}\).*$", re.MULTILINE
            )
            index_text = pattern.sub(line, index_text)
        else:
            # Insert under the correct section header
            section_header = f"## {section}"
            if section_header in index_text:
                idx = index_text.index(section_header) + len(section_header)
                # Find the end of the section header line
                newline_idx = index_text.index("\n", idx)
                index_text = (
                    index_text[: newline_idx + 1]
                    + line
                    + "\n"
                    + index_text[newline_idx + 1 :]
                )
            else:
                # Section doesn't exist, append it
                index_text += f"\n## {section}\n{line}\n"

    wiki.write_index(index_text)


def run_ingest(source_file: str, wiki: WikiManager, llm: LLMClient,
              update_qmd_index: bool = True) -> dict:
    """Ingest a source file and update the wiki.

    Returns a dict with keys: key_points, created, updated.
    """
    click.echo(f"Ingesting: {source_file}")

    # Read source
    source_content = wiki.read_raw_source(source_file)
    source_name = Path(source_file).stem

    # Build prompt context
    schema = wiki.read_schema()
    index = wiki.read_index()
    existing_pages = _build_existing_pages_context(wiki, index, source_content)

    system_msg = _INGEST_SYSTEM_PROMPT.format(
        schema=schema,
        index=index,
        existing_pages=existing_pages,
    )

    messages = [
        {"role": "system", "content": system_msg},
        {
            "role": "user",
            "content": f"Process this source document:\n\n{source_content}",
        },
    ]

    # Call LLM
    click.echo("Analyzing source material...")
    result = llm.chat_json(messages)

    # Extract results
    key_points = result.get("key_points", [])
    pages = result.get("pages", [])
    index_entries = result.get("index_entries", [])

    created = []
    updated = []

    # Write pages
    for page in pages:
        filename = page["filename"]
        content = page["content"]
        action = page.get("action", "create")
        wiki.write_wiki_page(filename, content)
        if action == "update":
            updated.append(filename)
        else:
            created.append(filename)

    # Update index
    if index_entries:
        _update_index(wiki, index_entries)
        updated.append("index.md")

    # Append log
    log_details = []
    if created:
        log_details.append(f"Created: {', '.join(created)}")
    if updated:
        log_details.append(f"Updated: {', '.join(updated)}")
    wiki.append_log("ingest", source_name, log_details)
    updated.append("log.md")

    # Output
    click.echo("")
    click.echo("Key Points:")
    for i, point in enumerate(key_points, 1):
        click.echo(f"  {i}. {point}")

    click.echo("")
    click.echo("Wiki Updates:")
    for f in created:
        click.echo(f"  [+] Created: wiki/{f}")
    for f in updated:
        click.echo(f"  [~] Updated: wiki/{f}")

    created_count = len(created)
    updated_count = len(updated)
    click.echo(
        f"\nDone. {created_count} pages created, {updated_count} pages updated."
    )

    return {"key_points": key_points, "created": created, "updated": updated}
