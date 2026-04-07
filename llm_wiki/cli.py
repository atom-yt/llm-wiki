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
@click.pass_context
def ingest(ctx, source_file):
    """Ingest a source file into the wiki"""
    root = ctx.obj["root"]
    wm = _wiki(root)
    _require_init(wm)
    llm = _llm_client(root)

    from llm_wiki.ingest import run_ingest

    run_ingest(source_file, wm, llm)


@main.command()
@click.argument("question")
@click.option("--save", is_flag=True, help="Archive answer as a wiki page")
@click.pass_context
def query(ctx, question, save):
    """Query the wiki"""
    root = ctx.obj["root"]
    wm = _wiki(root)
    _require_init(wm)
    llm = _llm_client(root)

    from llm_wiki.query import run_query

    run_query(question, save, wm, llm)


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

    from llm_wiki.server import create_app

    root = ctx.obj["root"]
    app = create_app(root)
    click.echo(f"Starting LLM Wiki server at http://{host}:{port} (data: {root})")
    uvicorn.run(app, host=host, port=port)
