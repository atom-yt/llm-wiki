"""Query the wiki and optionally archive the answer."""
import json
import re
import sys
from pathlib import Path
from datetime import datetime
from enum import Enum

import click

from llm_wiki.llm import LLMClient
from llm_wiki.wiki import WikiManager


class OutputFormat(Enum):
    """答案输出格式"""
    MARKDOWN = "markdown"
    TABLE = "table"
    COMPARISON = "comparison"
    LIST = "list"


def format_answer(
    question: str,
    answer: str,
    format_type: OutputFormat = OutputFormat.MARKDOWN
) -> str:
    """将答案格式化为不同输出

    Args:
        question: 用户问题
        answer: LLM 生成的答案
        format_type: 输出格式

    Returns:
        格式化后的答案
    """
    if format_type == OutputFormat.MARKDOWN:
        return answer

    if format_type == OutputFormat.LIST:
        # 提取要点列表
        lines = answer.split('\n')
        result = "# Answer (List Format)\n\n"
        in_list = False

        for line in lines:
            stripped = line.strip()
            if stripped.startswith('#'):
                # 跳过标题，因为会重新组织
                continue
            elif stripped.startswith('-') or stripped.startswith('*'):
                in_list = True
                result += stripped + '\n'
            elif in_list and stripped:
                # 列表的续行
                result += stripped + '\n'
            else:
                in_list = False

        return result

    if format_type == OutputFormat.TABLE:
        # 尝试提取表格数据
        # 简单实现：查找 Markdown 表格
        tables = re.findall(r'\|[^\n]+(?:\n\|[^\n]+)+', answer)
        if tables:
            return "# Answer (Table Format)\n\n" + tables[0]

        # 如果没有表格，尝试创建一个
        sections = re.split(r'##+\s+', answer)
        if len(sections) > 1:
            result = "# Answer (Table Format)\n\n"
            for section in sections[1:4]:  # 最多 3 个部分
                lines = section.split('\n')
                title = lines[0].strip()
                content = '\n'.join(lines[1:5]) if len(lines) > 1 else ''
                result += f"## {title}\n\n"
                result += f"| Aspect | Details |\n|---------|----------|\n"
                for line in content.split('\n')[:3]:
                    if line.strip() and not line.strip().startswith('#'):
                        result += f"| {line.strip()} |\n"
                result += '\n'
            return result

        return answer

    if format_type == OutputFormat.COMPARISON:
        # 创建对比格式
        # 提取可能的选项/替代方案
        options = re.findall(r'\*+\s*(.+?):', answer)
        if options:
            result = "# Answer (Comparison Format)\n\n"
            result += "| Option | Description |\n|---------|-------------|\n"
            for i, option in enumerate(options[:5], 1):
                result += f"| Option {i} | {option.strip()} |\n"
            return result

        # 按段落组织
        paragraphs = [p.strip() for p in answer.split('\n\n') if p.strip()]
        if len(paragraphs) > 1:
            result = "# Answer (Comparison Format)\n\n"
            for i, para in enumerate(paragraphs[:4], 1):
                result += f"### Point {i}\n\n{para}\n\n"
            return result

        return answer

    # 默认返回原始答案
    return answer


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
    use_qmd: bool = True,
) -> str:
    """Query the wiki and return the answer text."""

    # 初始化 QMD 检索器
    from llm_wiki.qmd_retriever import QMDRetriever
    from llm_wiki.page_selector import PageSelector

    retriever = QMDRetriever(wiki, enable_qmd=use_qmd)
    selector = PageSelector(wiki)

    # Step 1: 使用 QMD/BM25 语义搜索选择相关页面
    click.echo("Searching wiki...")

    if use_qmd:
        status = retriever.get_status()
        search_mode = status.get("search_mode", "Unknown")
        click.echo(f"Searching wiki ({search_mode})...")

        search_results = retriever.search(question, top_k=10)
        selected_pages = [f"{name}.md" for name, _ in search_results]
        click.echo(f"Found {len(selected_pages)} relevant pages.")
    else:
        # 使用页面选择器
        click.echo("Using page selector...")
        search_results = selector.select_for_query(question, top_k=10)
        selected_pages = [f"{name}.md" for name, _ in search_results]
        click.echo(f"Found {len(selected_pages)} relevant pages.")

    # 如果搜索没有结果，回退到 LLM 选择
    if not selected_pages:
        click.echo("No results from search, using LLM selection...")
        index_text = wiki.read_index()
        select_messages = [
            {
                "role": "system",
                "content": _SELECT_PAGES_PROMPT.format(index=index_text),
            },
            {"role": "user", "content": question},
        ]
        selection = llm.chat_json(select_messages)
        selected_pages = selection.get("pages", [])
        click.echo(f"Found {len(selected_pages)} relevant pages.")

    if not selected_pages:
        click.echo("No relevant pages found in the wiki.")
        return ""

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

    # Step 3: generate answer with streaming
    answer_messages = [
        {
            "role": "system",
            "content": _ANSWER_PROMPT.format(pages_content=pages_content),
        },
        {"role": "user", "content": question},
    ]

    click.echo("")
    click.echo("Generating answer...", nl=False)

    # Stream the answer
    answer_chunks = []
    for chunk in llm.chat_stream(answer_messages):
        click.echo(chunk, nl=False)
        answer_chunks.append(chunk)
        sys.stdout.flush()

    click.echo()  # New line after streaming

    answer = "".join(answer_chunks)

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
