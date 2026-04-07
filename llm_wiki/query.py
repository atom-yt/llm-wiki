import json
import re
from pathlib import Path

import click

from llm_wiki.llm import LLMClient
from llm_wiki.wiki import WikiManager


_SELECT_PAGES_PROMPT = """\
You are a wiki search assistant. Given a user question and the wiki index, \
select the most relevant pages that could help answer the question.

## Wiki Index
{index}

## Instructions
Return a JSON object with a single key "pages" containing a list of filenames \
(with .md extension) that are most relevant. Select up to 10 pages. \
Only select pages that actually exist in the index above.

Example: {{"pages": ["entity-nginx.md", "procedure-nginx-502-troubleshoot.md"]}}
"""

_ANSWER_PROMPT = """\
You are a knowledgeable wiki assistant. Answer the user's question based on \
the wiki pages provided below. Follow these rules:

1. Use Markdown formatting.
2. Reference source wiki pages using Markdown links: [page-name](page-name.md).
3. Be concise but thorough.
4. If the wiki doesn't contain enough information, say so honestly.
5. At the end, list the source pages under a "**Sources**:" line.

## Wiki Pages
{pages_content}
"""

_ARCHIVE_PROMPT = """\
Given this Q&A, generate a suitable kebab-case filename (without extension) \
for archiving it as a wiki page. The filename should start with "query-". \
Return JSON: {{"filename": "query-xxx-yyy"}}

Question: {question}
"""


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")[:60]


def run_query(
    question: str,
    save: bool,
    wiki: WikiManager,
    llm: LLMClient,
) -> str:
    """Query the wiki and return the answer text."""
    index_text = wiki.read_index()

    # Step 1: select relevant pages
    click.echo("Searching wiki...")
    select_messages = [
        {
            "role": "system",
            "content": _SELECT_PAGES_PROMPT.format(index=index_text),
        },
        {"role": "user", "content": question},
    ]
    selection = llm.chat_json(select_messages)
    selected_pages = selection.get("pages", [])

    if not selected_pages:
        click.echo("No relevant pages found in the wiki.")
        return ""

    click.echo(f"Found {len(selected_pages)} relevant pages.")

    # Step 2: read selected pages
    pages_content_parts = []
    for page_file in selected_pages:
        page_name = page_file.replace(".md", "")
        try:
            content = wiki.read_wiki_page(page_name)
            pages_content_parts.append(f"### {page_file}\n{content}")
        except FileNotFoundError:
            continue

    if not pages_content_parts:
        click.echo("Could not read any of the selected pages.")
        return ""

    pages_content = "\n\n".join(pages_content_parts)

    # Step 3: generate answer
    answer_messages = [
        {
            "role": "system",
            "content": _ANSWER_PROMPT.format(pages_content=pages_content),
        },
        {"role": "user", "content": question},
    ]
    answer = llm.chat(answer_messages)

    click.echo("")
    click.echo(answer)

    # Step 4: optionally archive
    if save:
        # Generate filename
        slug = f"query-{_slugify(question)}"
        if len(slug) > 60:
            # Ask LLM for a better name
            name_messages = [
                {
                    "role": "system",
                    "content": "Return only JSON, no markdown fences.",
                },
                {
                    "role": "user",
                    "content": _ARCHIVE_PROMPT.format(question=question),
                },
            ]
            try:
                name_result = llm.chat_json(name_messages)
                slug = name_result.get("filename", slug)
            except Exception:
                pass

        page_content = f"---\ntype: query\nquestion: \"{question}\"\n---\n\n# {question}\n\n{answer}"
        wiki.write_wiki_page(slug, page_content)

        # Update index
        index_text = wiki.read_index()
        section_header = "## Queries"
        link_line = f"- [{slug}]({slug}.md) - {question[:80]}"

        if section_header not in index_text:
            index_text += f"\n{section_header}\n{link_line}\n"
        elif f"{slug}.md" not in index_text:
            idx = index_text.index(section_header) + len(section_header)
            newline_idx = index_text.index("\n", idx)
            index_text = (
                index_text[: newline_idx + 1]
                + link_line
                + "\n"
                + index_text[newline_idx + 1 :]
            )
        wiki.write_index(index_text)

        wiki.append_log(
            "query",
            question[:60],
            [
                f"Generated answer based on {len(selected_pages)} wiki pages",
                f"Archived as: {slug}.md",
            ],
        )
        click.echo(f"\nArchived as: wiki/{slug}.md")
        click.echo("Updated: wiki/index.md, wiki/log.md")
    else:
        wiki.append_log(
            "query",
            question[:60],
            [f"Generated answer based on {len(selected_pages)} wiki pages"],
        )

    return answer
