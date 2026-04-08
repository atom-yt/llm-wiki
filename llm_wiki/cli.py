import click

from llm_wiki.wiki import WikiManager
from llm_wiki.config import get_config, ConfigError
from llm_wiki.llm import LLMClient


@click.group()
@click.option("--root", "-r", default="wiki-data", help="Wiki data directory (default: wiki-data)")
@click.pass_context
def main(ctx, root):
    """LLM Wiki - AI-powered personal knowledge base"""
    ctx.ensure_object(dict)
    ctx.obj["root"] = root


# ── helpers ────────────────────────────────────────────────────────

def _wiki(root: str) -> WikiManager:
    return WikiManager(root)


def _require_init(wm: WikiManager) -> None:
    if not wm.is_initialised():
        raise click.ClickException(
            "Wiki not initialised. Run 'llm-wiki init' first."
        )


def _llm_client(root: str) -> LLMClient:
    try:
        config = get_config(root)
    except ConfigError as e:
        raise click.ClickException(str(e))
    return LLMClient(config)


# ── commands ───────────────────────────────────────────────────────

@main.command()
@click.argument("directory", default=None, required=False)
@click.pass_context
def init(ctx, directory):
    """Initialize a new LLM Wiki in DIRECTORY (default: wiki-data)"""
    root = directory or ctx.obj["root"]
    wm = _wiki(root)
    if wm.is_initialised():
        click.echo(f"Wiki is already initialised in {wm.root}")
        return
    created = wm.init_wiki()
    click.echo(f"Initialized LLM Wiki in {wm.root}")
    for c in created:
        click.echo(f"  Created: {c}")
    click.echo(f"\nPlease edit {wm.root / 'config.yaml'} to set your LLM API key.")


@main.command()
@click.argument("source_file")
@click.option("--update-index/--no-update-index", default=True, help="Update QMD index after ingest")
@click.pass_context
def ingest(ctx, source_file, update_index):
    """Ingest a source file into the wiki"""
    root = ctx.obj["root"]
    wm = _wiki(root)
    _require_init(wm)
    llm = _llm_client(root)

    from llm_wiki.ingest import run_ingest

    run_ingest(source_file, wm, llm, update_qmd_index=update_index)


@main.command()
@click.argument("question")
@click.option("--save", is_flag=True, help="Archive answer as a wiki page")
@click.option("--qmd/--no-qmd", default=True, help="Use QMD semantic search (default: true)")
@click.pass_context
def query(ctx, question, save, qmd):
    """Query the wiki"""
    root = ctx.obj["root"]
    wm = _wiki(root)
    _require_init(wm)
    llm = _llm_client(root)

    from llm_wiki.query import run_query

    run_query(question, save, wm, llm, use_qmd=qmd)


@main.command()
@click.option("--force", "-f", is_flag=True, help="Force reindex all pages")
@click.pass_context
def index(ctx, force):
    """Build QMD semantic search index for wiki pages"""
    root = ctx.obj["root"]
    wm = _wiki(root)
    _require_init(wm)

    from llm_wiki.qmd_retriever import QMDRetriever

    retriever = QMDRetriever(wm)

    click.echo("Building QMD index...")
    indexed = retriever.index_pages(force=force)

    if indexed > 0:
        click.echo(f"Indexed {indexed} pages.")
    else:
        click.echo("All pages are already indexed.")
        click.echo("Use --force to rebuild the index.")

    # 显示状态
    status = retriever.get_status()
    click.echo(f"\nQMD Available: {status['available']}")
    click.echo(f"Indexed Pages: {status['indexed_pages']}/{status['total_pages']}")
    click.echo(f"Search Mode: {status.get('search_mode', 'Unknown')}")


@main.command()
@click.option("--analyze", is_flag=True, help="Analyze wiki and suggest schema improvements")
@click.pass_context
def schema(ctx, analyze):
    """Manage wiki schema"""
    root = ctx.obj["root"]
    wm = _wiki(root)
    _require_init(wm)

    if not analyze:
        # 显示当前 schema
        schema_text = wm.read_schema()
        click.echo("Current Wiki Schema:")
        click.echo("=" * 40)
        click.echo(schema_text)
        return

    # 执行分析
    llm = _llm_client(root)
    from llm_wiki.schema_analyzer import analyze_and_suggest

    click.echo("Analyzing wiki structure...")
    suggestions = analyze_and_suggest(wm, llm)

    if not suggestions:
        click.echo("No improvements suggested. Your wiki looks good!")
        return

    click.echo("Schema Analysis:")
    click.echo("=" * 40)

    for suggestion in suggestions:
        priority = suggestion.get("priority", "medium").upper()
        title = suggestion.get("title", "")
        description = suggestion.get("description", "")
        code = suggestion.get("code", "")

        click.echo(f"\n[{priority}] {title}")
        click.echo(f"  {description}")
        if code:
            click.echo(f"\n  Suggested change:")
            click.echo(f"  {code}")


@main.command()
@click.option("--fix", is_flag=True, help="Auto-fix discovered issues")
@click.pass_context
def lint(ctx, fix):
    """Check wiki health"""
    root = ctx.obj["root"]
    wm = _wiki(root)
    _require_init(wm)
    llm = _llm_client(root)

    from llm_wiki.lint import run_lint

    run_lint(fix, wm, llm)


@main.command()
@click.option("--port", default=8000, help="Port to listen on")
@click.option("--host", default="127.0.0.1", help="Host to bind to")
@click.pass_context
def serve(ctx, port, host):
    """Start the web UI server"""
    import uvicorn
    from pathlib import Path

    from llm_wiki.server import create_app

    root = ctx.obj["root"]

    # Resolve root to absolute path relative to current working directory
    root_path = Path(root).resolve()
    root = str(root_path)

    app = create_app(root)
    click.echo(f"Starting LLM Wiki server at http://{host}:{port} (data: {root})")
    uvicorn.run(app, host=host, port=port)
