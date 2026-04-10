import os
from pathlib import Path
from typing import Optional
import json

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from llm_wiki.config import get_config, ConfigError
from llm_wiki.wiki import WikiManager
from llm_wiki.llm import LLMClient


# ── Request / Response models ─────────────────────────────────────

class QueryRequest(BaseModel):
    question: str
    save: bool = False
    use_qmd: bool = True
    format: str = "markdown"


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


class QMDIndexRequest(BaseModel):
    force: bool = False


class QMDIndexResponse(BaseModel):
    indexed: int
    message: str


class QMDStatusResponse(BaseModel):
    available: bool
    cache_dir: str
    cache_exists: bool
    indexed_pages: int
    total_pages: int
    search_mode: str = "BM25 Keyword"  # QMD Semantic, SimpleEmbedder (TF-IDF), BM25 Keyword


# ── Graph API models ─────────────────────────────────────────────

class GraphNode(BaseModel):
    id: str
    title: str
    type: str
    inbound: int
    outbound: int


class GraphEdge(BaseModel):
    source: str
    target: str


class HubInfo(BaseModel):
    page: str
    links: int


class GraphStats(BaseModel):
    total_nodes: int
    total_edges: int
    orphan_pages: int
    hubs: list[HubInfo]


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    stats: GraphStats


# ── App factory ───────────────────────────────────────────────────

def create_app(root_dir: str = ".") -> FastAPI:
    # Support root from environment variable for uvicorn --factory mode
    root_dir = os.environ.get("LLM_WIKI_ROOT", root_dir)
    app = FastAPI(title="LLM Wiki", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Use absolute path for root_dir
    root_path = Path(root_dir).resolve()
    wiki = WikiManager(str(root_path))

    def _llm() -> LLMClient:
        try:
            config = get_config(str(root_path))
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

    @app.post("/api/ingest/stream")
    async def ingest_stream(req: IngestRequest):
        """流式 ingest，实时返回进度更新"""
        import asyncio
        import json
        from queue import Queue
        from concurrent.futures import ThreadPoolExecutor

        llm = _llm()
        from llm_wiki.ingest_optimized import AsyncIngestManager, IngestProgressUpdate

        # Queue for SSE events
        progress_queue: Queue = Queue()

        # Progress callback (called from thread)
        def on_progress(update: IngestProgressUpdate):
            progress_queue.put(("progress", update))

        # Run ingest in a thread (since LLM calls are blocking)
        def run_ingest_in_thread():
            try:
                # Create a sync wrapper that calls progress callback
                source_file = req.source_file
                source_content = wiki.read_raw_source(source_file)
                source_name = Path(source_file).stem

                progress_queue.put(("progress", {"stage": "analyzing", "progress": 10, "message": f"正在分析: {source_file}"}))

                # Build context
                from llm_wiki.ingest_optimized import _build_existing_pages_context, _INGEST_SYSTEM_PROMPT, _update_index
                schema = wiki.read_schema()
                index = wiki.read_index()
                existing_pages = _build_existing_pages_context(wiki, index, source_content)

                progress_queue.put(("progress", {"stage": "analyzing", "progress": 20, "message": "正在提取关键点..."}))

                system_msg = _INGEST_SYSTEM_PROMPT.format(
                    schema=schema,
                    index=index,
                    existing_pages=existing_pages,
                )

                messages = [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": f"Process this source document:\n\n{source_content}"},
                ]

                # Call LLM (blocking)
                progress_queue.put(("progress", {"stage": "analyzing", "progress": 30, "message": "LLM 正在处理..."}))
                result = llm.chat_json(messages)

                key_points = result.get("key_points", [])
                pages = result.get("pages", [])
                index_entries = result.get("index_entries", [])

                progress_queue.put(("progress", {"stage": "analyzing", "progress": 50, "message": f"提取到 {len(key_points)} 个关键点", "key_points": key_points}))

                # Write pages
                created = []
                updated = []
                total_pages = len(pages) or 1

                for i, page in enumerate(pages):
                    progress = 50 + (i + 1) / total_pages * 30
                    filename = page.get("filename", "")
                    progress_queue.put(("progress", {"stage": "writing", "progress": progress, "message": f"正在写入页面: {filename}"}))

                    content = page.get("content", "")
                    if "summary" in page and "sections" in page and not content:
                        # Generate content from summary/sections
                        sections = page.get("sections", [])
                        content = f"# {page.get('summary', '')}\n\n"
                        for section in sections:
                            content += f"## {section}\n\n"

                    action = page.get("action", "create")
                    wiki.write_wiki_page(filename, content)
                    if action == "update":
                        updated.append(filename)
                    else:
                        created.append(filename)

                progress_queue.put(("progress", {"stage": "writing", "progress": 80, "message": f"创建了 {len(created)} 个页面", "created": created, "updated": updated}))

                # Update index
                if index_entries:
                    progress_queue.put(("progress", {"stage": "indexing", "progress": 90, "message": "正在更新索引..."}))
                    _update_index(wiki, index_entries)
                    updated.append("index.md")

                # Log
                progress_queue.put(("progress", {"stage": "logging", "progress": 95, "message": "正在记录日志..."}))
                log_details = []
                if created:
                    log_details.append(f"Created: {', '.join(created)}")
                if updated:
                    log_details.append(f"Updated: {', '.join(updated)}")
                wiki.append_log("ingest", source_name, log_details)

                # Final result
                progress_queue.put(("progress", {"stage": "completed", "progress": 100, "message": "完成！"}))
                progress_queue.put(("result", {"key_points": key_points, "created": created, "updated": updated}))
                progress_queue.put(("done", None))

            except Exception as e:
                import traceback
                traceback.print_exc()
                progress_queue.put(("error", str(e)))
                progress_queue.put(("done", None))

        # Start thread
        executor = ThreadPoolExecutor(max_workers=1)
        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(executor, run_ingest_in_thread)

        async def event_generator():
            """Send SSE events"""
            while True:
                # Non-blocking check
                await asyncio.sleep(0.05)
                while not progress_queue.empty():
                    event_type, data = progress_queue.get()

                    if event_type == "done":
                        yield f"event: done\ndata: \n\n"
                        return

                    elif event_type == "error":
                        yield f"event: error\ndata: {json.dumps({'error': data})}\n\n"
                        return

                    elif event_type == "progress":
                        data_json = json.dumps(data)
                        yield f"event: progress\ndata: {data_json}\n\n"

                    elif event_type == "result":
                        data_json = json.dumps(data)
                        yield f"event: result\ndata: {data_json}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # ── Interactive Ingest ─────────────────────────────────────

    class IngestStartRequest(BaseModel):
        source_file: str
        mode: str = "interactive"  # "auto", "interactive"

    class KeyPointsResponse(BaseModel):
        key_points: list[str]
        session_id: str

    class PageProposal(BaseModel):
        filename: str
        action: str  # "create" or "update"
        strategy: str = "merge"
        diff: Optional[str] = None  # 对于 update，显示 diff
        content_preview: str

    class ProposePagesRequest(BaseModel):
        session_id: str
        approved_key_points: Optional[list[str]] = None
        user_feedback: Optional[str] = None

    class ProposePagesResponse(BaseModel):
        proposals: list[PageProposal]
        session_id: str

    class ApplyRequest(BaseModel):
        session_id: str
        approved_pages: list[str]  # 要创建/更新的页面文件名
        rejected_pages: list[str] = []
        strategies: Optional[dict] = None  # {filename: strategy}

    class ApplyResponse(BaseModel):
        created: list[str]
        updated: list[str]
        pages_affected: list[str]

    @app.post("/api/ingest/start", response_model=KeyPointsResponse)
    def ingest_start(req: IngestStartRequest):
        """开始交互式 ingest，提取关键点"""
        llm = _llm()
        from llm_wiki.ingest_interactive import create_session, extract_key_points

        session = create_session(req.source_file, wiki)
        key_points = extract_key_points(session, wiki, llm)

        return KeyPointsResponse(
            key_points=key_points,
            session_id=session.session_id
        )

    @app.post("/api/ingest/propose", response_model=ProposePagesResponse)
    def ingest_propose(req: ProposePagesRequest):
        """基于批准的关键点，提出页面方案"""
        llm = _llm()
        from llm_wiki.ingest_interactive import (
            get_session,
            propose_pages,
            parse_strategy
        )

        session = get_session(req.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        proposals_data = propose_pages(
            session, wiki, llm, req.user_feedback or ""
        )

        # 转换为响应格式
        proposals = []
        for p in proposals_data:
            filename = p.get("filename", "")
            action = p.get("action", "create")
            strategy = p.get("strategy", "merge")
            content = p.get("content", "")

            # 如果是 update，生成 diff
            diff = None
            if action == "update" and wiki.wiki_page_exists(filename):
                existing = wiki.read_wiki_page(filename)
                diff = _generate_diff(existing, content)

            # 截取预览
            preview = content[:500] + "..." if len(content) > 500 else content

            proposals.append(PageProposal(
                filename=filename,
                action=action,
                strategy=strategy,
                diff=diff,
                content_preview=preview
            ))

        return ProposePagesResponse(
            proposals=proposals,
            session_id=req.session_id
        )

    @app.post("/api/ingest/apply", response_model=ApplyResponse)
    def ingest_apply(req: ApplyRequest):
        """应用批准的页面更改"""
        from llm_wiki.ingest_interactive import (
            get_session,
            apply_pages,
            delete_session
        )

        session = get_session(req.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        result = apply_pages(
            session,
            wiki,
            req.approved_pages,
            req.rejected_pages,
            req.strategies
        )

        # 清理会话
        delete_session(req.session_id)

        return ApplyResponse(**result)

    def _generate_diff(old: str, new: str) -> str:
        """生成简单的 diff"""
        import difflib
        lines = difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile="existing",
            tofile="proposed",
            lineterm=""
        )
        return "".join(lines)[:1000] + "... (truncated)" if len("".join(lines)) > 1000 else "".join(lines)

    # ── QMD ────────────────────────────────────────────────

    @app.post("/api/qmd/index", response_model=QMDIndexResponse)
    def qmd_index(req: QMDIndexRequest):
        """Build or update QMD semantic search index."""
        from llm_wiki.qmd_retriever import QMDRetriever

        retriever = QMDRetriever(wiki)

        indexed = retriever.index_pages(force=req.force)

        message = f"Indexed {indexed} pages." if indexed > 0 else "No pages to index."
        return QMDIndexResponse(indexed=indexed, message=message)

    @app.get("/api/qmd/status", response_model=QMDStatusResponse)
    def qmd_status():
        """Check QMD availability and index status."""
        from llm_wiki.qmd_retriever import QMDRetriever

        retriever = QMDRetriever(wiki)

        status = retriever.get_status()
        return QMDStatusResponse(**status)

    # ── Query ─────────────────────────────────────────────────

    @app.post("/api/query", response_model=QueryResponse)
    def query(req: QueryRequest):
        """Query wiki with QMD/BM25/SimpleEmbedder semantic search."""
        from llm_wiki.qmd_retriever import QMDRetriever
        from llm_wiki.query import _ANSWER_PROMPT, _slugify

        llm = _llm()

        # Step 1: Use QMDRetriever for fast page selection (no LLM call!)
        retriever = QMDRetriever(wiki, enable_qmd=req.use_qmd)
        search_results = retriever.search(req.question, top_k=10)
        selected_pages = [f"{name}.md" for name, _ in search_results]

        if not selected_pages:
            return QueryResponse(answer="No relevant pages found in wiki.", selected_pages=[])

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

    @app.post("/api/query/stream")
    async def query_stream(req: QueryRequest):
        """Stream query response with Server-Sent Events."""
        import asyncio
        import functools
        import json
        import queue
        import threading

        llm = _llm()

        from llm_wiki.qmd_retriever import QMDRetriever
        from llm_wiki.query import _ANSWER_PROMPT, _slugify

        llm = _llm()

        # Step 1: Use QMDRetriever for fast page selection (no LLM call!)
        retriever = QMDRetriever(wiki, enable_qmd=req.use_qmd)
        search_results = retriever.search(req.question, top_k=10)
        selected_pages = [f"{name}.md" for name, _ in search_results]

        # Helper to run blocking generator in thread and yield items
        async def stream_from_blocking(gen_func):
            """Run a blocking generator in a thread and yield items asynchronously."""
            q = queue.Queue()
            exc = [None]  # Use list to allow assignment in nested function

            def run():
                try:
                    for item in gen_func():
                        q.put(item)
                    q.put(None)  # Sentinel for end of stream
                except Exception as e:
                    exc[0] = e
                    q.put(None)

            thread = threading.Thread(target=run, daemon=True)
            thread.start()

            loop = asyncio.get_event_loop()
            while True:
                # Wait for item from queue (non-blocking via executor)
                item = await loop.run_in_executor(None, q.get)
                if item is None:
                    if exc[0]:
                        raise exc[0]
                    break
                yield item

        async def event_generator():
            # Send selected pages event first
            selected_pages_json = json.dumps(selected_pages)
            yield f"event: selected_pages\ndata: {selected_pages_json}\n\n"

            if not selected_pages:
                error_json = json.dumps({'error': 'No relevant pages found in wiki.'})
                yield f"event: done\ndata: {error_json}\n\n"
                return

            # Step 2: read pages (selected_pages from QMDRetriever)
            parts = []
            for pf in selected_pages:
                pn = pf.replace(".md", "")
                try:
                    content = wiki.read_wiki_page(pn)
                    parts.append(f"### {pf}\n{content}")
                except FileNotFoundError:
                    continue

            if not parts:
                error_json = json.dumps({'error': 'Could not read any of the selected pages.'})
                yield f"event: done\ndata: {error_json}\n\n"
                return

            # Step 3: stream answer
            answer_messages = [
                {
                    "role": "system",
                    "content": _ANSWER_PROMPT.format(pages_content="\n\n".join(parts)),
                },
                {"role": "user", "content": req.question},
            ]

            archived_as = None
            chunk_count = 0

            if req.save:
                # Collect full answer for archiving (stream to user and collect)
                full_answer = ""
                gen_func = functools.partial(llm.chat_stream, answer_messages)
                async for chunk in stream_from_blocking(gen_func):
                    chunk_count += 1
                    full_answer += chunk
                    chunk_json = json.dumps({'chunk': chunk})
                    yield f"event: chunk\ndata: {chunk_json}\n\n"

                answer = full_answer

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
                # Just stream without archiving
                gen_func = functools.partial(llm.chat_stream, answer_messages)
                async for chunk in stream_from_blocking(gen_func):
                    chunk_count += 1
                    chunk_json = json.dumps({'chunk': chunk})
                    yield f"event: chunk\ndata: {chunk_json}\n\n"

                wiki.append_log(
                    "query",
                    req.question[:60],
                    [f"Generated answer based on {len(selected_pages)} wiki pages"],
                )

            # Send done event
            done_json = json.dumps({'archived_as': archived_as})
            yield f"event: done\ndata: {done_json}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
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

    # ── Graph ───────────────────────────────────────────────────

    @app.get("/api/graph", response_model=GraphResponse)
    def get_graph():
        """Get wiki graph data for visualization."""
        from llm_wiki.link_graph import LinkGraph

        graph = LinkGraph(wiki)
        graph.load()

        # Build nodes with stats
        pages = wiki.list_wiki_pages()
        summaries = wiki.collect_all_pages_summary()

        nodes = []
        for page in pages:
            stats = graph.get_page_stats(page)
            title = summaries.get(page, page)

            # Infer page type from frontmatter or filename
            try:
                from llm_wiki.frontmatter import FrontMatter
                content = wiki.read_wiki_page(page)
                fm = FrontMatter(content)
                page_type = fm.get("type", "page")
            except:
                page_type = "page"
                if page.startswith("source-"):
                    page_type = "source"
                elif page.startswith("entity-"):
                    page_type = "entity"
                elif page.startswith("concept-"):
                    page_type = "concept"
                elif page.startswith("procedure-"):
                    page_type = "procedure"
                elif page.startswith("incident-"):
                    page_type = "incident"
                elif page.startswith("query-"):
                    page_type = "query"

            nodes.append(GraphNode(
                id=page,
                title=title,
                type=page_type,
                inbound=stats["inbound"],
                outbound=stats["outbound"],
            ))

        # Build edges
        edges = []
        all_pages = graph.get_all_pages()
        for page in all_pages:
            outbound = graph.get_outbound(page)
            for target in outbound:
                edges.append(GraphEdge(source=page, target=target))

        # Stats
        orphans = graph.find_orphans()
        hub_data = graph.find_hubs(limit=10)

        stats = GraphStats(
            total_nodes=len(nodes),
            total_edges=len(edges),
            orphan_pages=len(orphans),
            hubs=[HubInfo(page=h[0], links=h[1]) for h in hub_data],
        )

        return GraphResponse(nodes=nodes, edges=edges, stats=stats)

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
