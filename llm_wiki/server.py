import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from llm_wiki.config import get_config, ConfigError
from llm_wiki.wiki import WikiManager
from llm_wiki.llm import LLMClient


# ── Request / Response models ─────────────────────────────────────

class QueryRequest(BaseModel):
    question: str
    save: bool = False


class QueryResponse(BaseModel):
    answer: str
    selected_pages: list[str] = []
    archived_as: Optional[str] = None


class IngestRequest(BaseModel):
    source_file: str


class IngestResponse(BaseModel):
    key_points: list[str]
    created: list[str]
    updated: list[str]


class LintRequest(BaseModel):
    fix: bool = False


class LintIssue(BaseModel):
    level: str
    message: str
    pages: list[str] = []


class LintResponse(BaseModel):
    structural_issues: list[LintIssue]
    llm_issues: list[LintIssue]
    fixes: dict = {}


class PageInfo(BaseModel):
    name: str
    title: str


class PageContent(BaseModel):
    name: str
    content: str


# ── App factory ───────────────────────────────────────────────────

def create_app(root_dir: str = ".") -> FastAPI:
    app = FastAPI(title="LLM Wiki", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    wiki = WikiManager(root_dir)

    def _llm() -> LLMClient:
        try:
            config = get_config(root_dir)
        except ConfigError as e:
            raise HTTPException(status_code=500, detail=str(e))
        return LLMClient(config)

    # ── Wiki browsing ─────────────────────────────────────────

    @app.get("/api/pages", response_model=list[PageInfo])
    def list_pages():
        summaries = wiki.collect_all_pages_summary()
        return [PageInfo(name=n, title=t) for n, t in summaries.items()]

    @app.get("/api/pages/{name}", response_model=PageContent)
    def get_page(name: str):
        try:
            content = wiki.read_wiki_page(name)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"Page not found: {name}")
        return PageContent(name=name, content=content)

    @app.get("/api/index")
    def get_index():
        try:
            return {"content": wiki.read_index()}
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="index.md not found")

    @app.get("/api/log")
    def get_log():
        try:
            return {"content": wiki.read_log()}
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="log.md not found")

    # ── Raw sources ───────────────────────────────────────────

    @app.get("/api/raw")
    def list_raw_sources():
        return {"sources": wiki.list_raw_sources()}

    @app.get("/api/raw/{name:path}")
    def get_raw_source(name: str):
        try:
            content = wiki.read_raw_source(name)
            return {"name": name, "content": content}
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"Source not found: {name}")

    @app.post("/api/raw/upload")
    async def upload_raw_source(file: UploadFile = File(...)):
        content = await file.read()
        filename = file.filename or "uploaded.md"
        path = wiki.save_raw_source(filename, content)
        return {"filename": str(path.relative_to(wiki.root)), "size": len(content)}

    # ── Ingest ────────────────────────────────────────────────

    @app.post("/api/ingest", response_model=IngestResponse)
    def ingest(req: IngestRequest):
        llm = _llm()
        from llm_wiki.ingest import run_ingest
        # Suppress click.echo in API mode by capturing
        import io, contextlib
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            result = run_ingest(req.source_file, wiki, llm)
        return IngestResponse(**result)

    # ── Query ─────────────────────────────────────────────────

    @app.post("/api/query", response_model=QueryResponse)
    def query(req: QueryRequest):
        llm = _llm()

        # We inline the query logic here to get structured results
        from llm_wiki.query import (
            _SELECT_PAGES_PROMPT,
            _ANSWER_PROMPT,
            _slugify,
        )

        index_text = wiki.read_index()

        # Step 1: select pages
        select_messages = [
            {
                "role": "system",
                "content": _SELECT_PAGES_PROMPT.format(index=index_text),
            },
            {"role": "user", "content": req.question},
        ]
        selection = llm.chat_json(select_messages)
        selected_pages = selection.get("pages", [])

        if not selected_pages:
            return QueryResponse(answer="No relevant pages found in the wiki.")

        # Step 2: read pages
        parts = []
        for pf in selected_pages:
            pn = pf.replace(".md", "")
            try:
                content = wiki.read_wiki_page(pn)
                parts.append(f"### {pf}\n{content}")
            except FileNotFoundError:
                continue

        if not parts:
            return QueryResponse(
                answer="Could not read any of the selected pages.",
                selected_pages=selected_pages,
            )

        # Step 3: generate answer
        answer_messages = [
            {
                "role": "system",
                "content": _ANSWER_PROMPT.format(pages_content="\n\n".join(parts)),
            },
            {"role": "user", "content": req.question},
        ]
        answer = llm.chat(answer_messages)

        archived_as = None
        if req.save:
            slug = f"query-{_slugify(req.question)}"
            page_content = (
                f'---\ntype: query\nquestion: "{req.question}"\n---\n\n'
                f"# {req.question}\n\n{answer}"
            )
            wiki.write_wiki_page(slug, page_content)

            # Update index
            idx_text = wiki.read_index()
            section_header = "## Queries"
            link_line = f"- [{slug}]({slug}.md) - {req.question[:80]}"
            if section_header not in idx_text:
                idx_text += f"\n{section_header}\n{link_line}\n"
            elif f"{slug}.md" not in idx_text:
                pos = idx_text.index(section_header) + len(section_header)
                nl = idx_text.index("\n", pos)
                idx_text = idx_text[: nl + 1] + link_line + "\n" + idx_text[nl + 1 :]
            wiki.write_index(idx_text)

            wiki.append_log(
                "query",
                req.question[:60],
                [
                    f"Generated answer based on {len(selected_pages)} wiki pages",
                    f"Archived as: {slug}.md",
                ],
            )
            archived_as = f"{slug}.md"
        else:
            wiki.append_log(
                "query",
                req.question[:60],
                [f"Generated answer based on {len(selected_pages)} wiki pages"],
            )

        return QueryResponse(
            answer=answer,
            selected_pages=selected_pages,
            archived_as=archived_as,
        )

    # ── Lint ──────────────────────────────────────────────────

    @app.post("/api/lint", response_model=LintResponse)
    def lint(req: LintRequest):
        llm = _llm()
        import io, contextlib
        from llm_wiki.lint import run_lint

        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            result = run_lint(req.fix, wiki, llm)

        return LintResponse(
            structural_issues=[
                LintIssue(**i) for i in result["structural_issues"]
            ],
            llm_issues=[LintIssue(**i) for i in result["llm_issues"]],
            fixes=result["fixes"],
        )

    # ── Static files (frontend) ───────────────────────────────

    dist_dir = Path(__file__).parent.parent / "web" / "dist"
    if dist_dir.exists():
        @app.get("/{full_path:path}")
        async def serve_frontend(full_path: str):
            file_path = dist_dir / full_path
            if file_path.is_file():
                return FileResponse(file_path)
            return FileResponse(dist_dir / "index.html")

    return app
