import re

import click

from llm_wiki.llm import LLMClient
from llm_wiki.wiki import WikiManager


_LINT_SYSTEM_PROMPT = """\
You are a wiki quality auditor. Analyze the wiki pages below and identify issues.

## Wiki Index
{index}

## All Pages (title only)
{page_summaries}

## Instructions
Check for:
1. Contradictions between pages
2. Outdated statements superseded by newer sources
3. Important concepts mentioned across multiple pages that lack their own dedicated page
4. Missing cross-references between related pages
5. Pages that are too thin and should be enriched

Return JSON:
{{
  "issues": [
    {{
      "level": "warn" or "info",
      "message": "description of the issue",
      "pages": ["affected-page.md", ...]
    }},
    ...
  ]
}}
If no issues found, return {{"issues": []}}.
"""

_FIX_SYSTEM_PROMPT = """\
You are a wiki maintainer. Fix the issues listed below by creating or updating wiki pages.

## Wiki Schema
{schema}

## Current Index
{index}

## Issues to fix
{issues}

## Existing pages that may need updates
{existing_pages}

## Instructions
Return JSON:
{{
  "pages": [
    {{
      "filename": "concept-xxx.md",
      "action": "create" or "update",
      "content": "full markdown content"
    }},
    ...
  ],
  "index_entries": [
    {{
      "section": "Concepts",
      "filename": "concept-xxx.md",
      "display_name": "Concept Xxx",
      "summary": "one-line summary"
    }},
    ...
  ]
}}
Only create/update pages that address the issues. Do not make unnecessary changes.
"""


def _structural_checks(wiki: WikiManager) -> list[dict]:
    """Run local structural checks that don't need LLM."""
    issues = []
    index_text = wiki.read_index()
    all_pages = wiki.list_wiki_pages()

    # Check: pages not in index
    for page in all_pages:
        if f"{page}.md" not in index_text and f"({page}.md)" not in index_text:
            issues.append({
                "level": "warn",
                "type": "orphan",
                "message": f"wiki/{page}.md is not registered in index.md",
                "pages": [f"{page}.md"],
            })

    # Check: broken links
    for page in all_pages:
        links = wiki.find_links_in_page(page)
        for link in links:
            if link not in ("index", "log") and not wiki.wiki_page_exists(link):
                issues.append({
                    "level": "warn",
                    "type": "broken_link",
                    "message": f"wiki/{page}.md links to {link}.md which does not exist",
                    "pages": [f"{page}.md"],
                })

    # Check: empty or very short pages
    for page in all_pages:
        try:
            content = wiki.read_wiki_page(page)
            # Strip front-matter
            if content.startswith("---"):
                end = content.find("---", 3)
                if end != -1:
                    content = content[end + 3:]
            if len(content.strip()) < 50:
                issues.append({
                    "level": "warn",
                    "type": "thin_page",
                    "message": f"wiki/{page}.md has very little content",
                    "pages": [f"{page}.md"],
                })
        except FileNotFoundError:
            pass

    # Check: inbound link count
    inbound: dict[str, int] = {p: 0 for p in all_pages}
    for page in all_pages:
        links = wiki.find_links_in_page(page)
        for link in links:
            if link in inbound:
                inbound[link] += 1
    for page, count in inbound.items():
        if count <= 1 and not page.startswith("source-"):
            issues.append({
                "level": "warn",
                "type": "low_inbound",
                "message": f"wiki/{page}.md has only {count} inbound link(s)",
                "pages": [f"{page}.md"],
            })

    return issues


def run_lint(fix: bool, wiki: WikiManager, llm: LLMClient) -> dict:
    """Run wiki health checks and optionally fix issues.

    Returns dict with keys: structural_issues, llm_issues, fixes.
    """
    click.echo("Wiki Health Check")
    click.echo("=" * 40)

    # Structural checks
    click.echo("\nStructural Checks:")
    structural = _structural_checks(wiki)

    if not structural:
        click.echo("  [OK] No structural issues found")
    else:
        for issue in structural:
            tag = "WARN" if issue["level"] == "warn" else "INFO"
            click.echo(f"  [{tag}] {issue['message']}")

    # LLM deep analysis
    click.echo("\nLLM Deep Analysis:")
    index_text = wiki.read_index()
    page_summaries = wiki.collect_all_pages_summary()
    summary_text = "\n".join(
        f"- {name}: {title}" for name, title in page_summaries.items()
    )

    if not page_summaries:
        click.echo("  [OK] No pages to analyze")
        llm_issues = []
    else:
        messages = [
            {
                "role": "system",
                "content": _LINT_SYSTEM_PROMPT.format(
                    index=index_text,
                    page_summaries=summary_text,
                ),
            },
            {"role": "user", "content": "Analyze this wiki for issues."},
        ]

        result = llm.chat_json(messages)
        llm_issues = result.get("issues", [])

        if not llm_issues:
            click.echo("  [OK] No issues found")
        else:
            for issue in llm_issues:
                tag = "WARN" if issue["level"] == "warn" else "INFO"
                click.echo(f"  [{tag}] {issue['message']}")

    all_issues = structural + llm_issues
    warns = sum(1 for i in all_issues if i.get("level") == "warn")
    infos = sum(1 for i in all_issues if i.get("level") == "info")
    click.echo(f"\nIssues: 0 errors, {warns} warnings, {infos} suggestions")

    # Fix mode
    fixes = {"created": [], "updated": []}
    if fix and all_issues:
        click.echo("\nFixing issues...")
        issues_text = "\n".join(
            f"- [{i.get('level', 'info').upper()}] {i['message']}"
            for i in all_issues
        )

        # Collect affected pages content
        affected_pages = set()
        for issue in all_issues:
            for p in issue.get("pages", []):
                affected_pages.add(p.replace(".md", ""))

        existing_parts = []
        for name in affected_pages:
            try:
                content = wiki.read_wiki_page(name)
                if len(content) > 2000:
                    content = content[:2000] + "\n...(truncated)"
                existing_parts.append(f"### {name}.md\n{content}")
            except FileNotFoundError:
                pass

        existing_text = "\n\n".join(existing_parts) if existing_parts else "(none)"

        fix_messages = [
            {
                "role": "system",
                "content": _FIX_SYSTEM_PROMPT.format(
                    schema=wiki.read_schema(),
                    index=index_text,
                    issues=issues_text,
                    existing_pages=existing_text,
                ),
            },
            {"role": "user", "content": "Fix these issues."},
        ]

        fix_result = llm.chat_json(fix_messages)

        for page in fix_result.get("pages", []):
            filename = page["filename"]
            content = page["content"]
            action = page.get("action", "create")
            wiki.write_wiki_page(filename, content)
            if action == "update":
                fixes["updated"].append(filename)
                click.echo(f"  [~] Updated: wiki/{filename}")
            else:
                fixes["created"].append(filename)
                click.echo(f"  [+] Created: wiki/{filename}")

        # Update index
        from llm_wiki.ingest import _update_index

        index_entries = fix_result.get("index_entries", [])
        if index_entries:
            _update_index(wiki, index_entries)
            fixes["updated"].append("index.md")
            click.echo("  [~] Updated: wiki/index.md")

        # Log
        log_details = []
        if fixes["created"]:
            log_details.append(f"Created: {', '.join(fixes['created'])}")
        if fixes["updated"]:
            log_details.append(f"Updated: {', '.join(fixes['updated'])}")
        if log_details:
            wiki.append_log("lint --fix", "Auto-fix", log_details)
            click.echo("  [~] Updated: wiki/log.md")

        click.echo(
            f"\nFixed: {len(fixes['created'])} pages created, "
            f"{len(fixes['updated'])} pages updated."
        )
    elif fix:
        click.echo("\nNo issues to fix.")

    wiki.append_log(
        "lint",
        "Health check",
        [f"{warns} warnings, {infos} suggestions"],
    )

    return {
        "structural_issues": structural,
        "llm_issues": llm_issues,
        "fixes": fixes,
    }
