import json
import re
from pathlib import Path

import click

from llm_wiki.llm import LLMClient
from llm_wiki.wiki import WikiManager


_INGEST_SYSTEM_PROMPT = """\
You are a meticulous wiki maintainer. Your job is to process a raw source document \
and produce structured wiki pages.

## Wiki schema
{schema}

## Current wiki index
{index}

## Instructions
Given the source document below, you must:
1. Identify the key points of the source.
2. Create a summary page for the source (prefix: source-).
3. Identify entities (tools, services, systems) and create/update entity pages (prefix: entity-).
4. Identify concepts (ideas, patterns, principles) and create/update concept pages (prefix: concept-).
5. Identify procedures (step-by-step guides) and create/update procedure pages (prefix: procedure-).
6. Identify incidents (post-mortems) if any and create incident pages (prefix: incident-).
7. Produce index entries for all new/updated pages.

For pages that already exist in the index, you should merge new information into the \
existing content. I will provide the existing content for those pages.

## Existing pages content
{existing_pages}

## Output format
Respond with a JSON object (no markdown code fences) containing:
{{
  "key_points": ["point 1", "point 2", ...],
  "pages": [
    {{
      "filename": "source-xxx.md",
      "action": "create" or "update",
      "content": "full markdown content of the page"
    }},
    ...
  ],
  "index_entries": [
    {{
      "section": "Sources" or "Entities" or "Concepts" or "Procedures" or "Incidents",
      "filename": "source-xxx.md",
      "display_name": "Source Xxx",
      "summary": "one-line summary"
    }},
    ...
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
    wiki: WikiManager, index_text: str
) -> str:
    """Read all existing wiki pages referenced in the index to give LLM context."""
    pages = wiki.list_wiki_pages()
    if not pages:
        return "(no existing pages)"

    parts = []
    for name in pages:
        try:
            content = wiki.read_wiki_page(name)
            # Truncate very long pages to save tokens
            if len(content) > 2000:
                content = content[:2000] + "\n...(truncated)"
            parts.append(f"### {name}.md\n{content}")
        except FileNotFoundError:
            continue

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


def run_ingest(source_file: str, wiki: WikiManager, llm: LLMClient) -> dict:
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
    existing_pages = _build_existing_pages_context(wiki, index)

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
