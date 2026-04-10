import axios from 'axios';

const api = axios.create({ baseURL: '/api' });

// ── Types ──────────────────────────────────────────────────────

export interface PageInfo {
  name: string;
  title: string;
}

export interface PageContent {
  name: string;
  content: string;
}

export interface IngestResponse {
  key_points: string[];
  created: string[];
  updated: string[];
}

export interface QueryResponse {
  answer: string;
  selected_pages: string[];
  archived_as: string | null;
}

export interface LintIssue {
  level: string;
  message: string;
  pages: string[];
}

export interface LintResponse {
  structural_issues: LintIssue[];
  llm_issues: LintIssue[];
  fixes: { created?: string[]; updated?: string[] };
}

// ── API calls ──────────────────────────────────────────────────

export async function fetchPages(): Promise<PageInfo[]> {
  const res = await api.get<PageInfo[]>('/pages');
  return res.data;
}

export async function fetchPage(name: string): Promise<PageContent> {
  const res = await api.get<PageContent>(`/pages/${name}`);
  return res.data;
}

export async function fetchIndex(): Promise<string> {
  const res = await api.get<{ content: string }>('/index');
  return res.data.content;
}

export async function fetchLog(): Promise<string> {
  const res = await api.get<{ content: string }>('/log');
  return res.data.content;
}

export async function fetchRawSources(): Promise<string[]> {
  const res = await api.get<{ sources: string[] }>('/raw');
  return res.data.sources;
}

export async function fetchRawSource(name: string): Promise<string> {
  const res = await api.get<{ name: string; content: string }>(`/raw/${name}`);
  return res.data.content;
}

export async function uploadRawSource(file: File): Promise<{ filename: string; size: number }> {
  const form = new FormData();
  form.append('file', file);
  const res = await api.post('/raw/upload', form);
  return res.data;
}

export async function ingestSource(sourceFile: string): Promise<IngestResponse> {
  const res = await api.post<IngestResponse>('/ingest', { source_file: sourceFile });
  return res.data;
}

// Streaming ingest with real-time progress
export interface IngestProgressUpdate {
  stage: string;
  progress: number;
  message: string;
  key_points?: string[];
  created?: string[];
  updated?: string[];
}

export interface IngestStreamCallbacks {
  onProgress: (update: IngestProgressUpdate) => void;
  onDone: (result: IngestResponse) => void;
  onError: (error: string) => void;
}

export async function ingestSourceStream(
  sourceFile: string,
  callbacks: IngestStreamCallbacks
): Promise<void> {
  console.log('[ingestSourceStream] Starting stream ingest:', { sourceFile });

  try {
    const res = await fetch('/api/ingest/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source_file: sourceFile }),
    });

    console.log('[ingestSourceStream] Response status:', res.status, 'ok:', res.ok);

    if (!res.ok) {
      console.error('[ingestSourceStream] Response not OK, status:', res.status);
      throw new Error(`HTTP error: ${res.status}`);
    }

    const reader = res.body?.getReader();
    if (!reader) {
      console.error('[ingestSourceStream] No response body reader');
      throw new Error('No response body reader');
    }

    console.log('[ingestSourceStream] Reader created, starting to read...');

    const decoder = new TextDecoder();
    let finalResult: IngestResponse | null = null;
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        console.log('[ingestSourceStream] Stream ended');
        break;
      }

      const chunk = decoder.decode(value, { stream: true });
      buffer += chunk;

      const lines = buffer.split('\n');
      // Keep the last partial line in buffer
      buffer = lines.pop() || '';

      let eventType: string | undefined;

      for (const line of lines) {
        const trimmedLine = line.trim();
        if (trimmedLine.startsWith('event: ')) {
          eventType = trimmedLine.slice(7).trim();
        } else if (trimmedLine.startsWith('data: ')) {
          const data = trimmedLine.slice(6).trim();
          if (!data) continue;

          try {
            const parsed = JSON.parse(data);
            console.log('[ingestSourceStream] Event:', eventType, 'Data:', data);

            if (parsed.key_points) {
              callbacks.onProgress(parsed);
            } else if (parsed.stage && parsed.progress !== undefined) {
              callbacks.onProgress(parsed);
            } else if (parsed.key_points !== undefined && parsed.created !== undefined) {
              // Final result
              finalResult = {
                key_points: parsed.key_points || [],
                created: parsed.created || [],
                updated: parsed.updated || [],
              };
            }
          } catch (e) {
            console.error('[ingestSourceStream] Failed to parse SSE data:', data, e);
          }
        }
      }
    }

    // Call onDone with final result
    if (finalResult) {
      callbacks.onDone(finalResult);
    }
  } catch (e: any) {
    console.error('[ingestSourceStream] Stream error:', e);
    callbacks.onError(e.message || 'Unknown error');
    throw e;
  }
}

export async function queryWiki(question: string, save = false): Promise<QueryResponse> {
  const res = await api.post<QueryResponse>('/query', { question, save });
  return res.data;
}

// Streaming query with Server-Sent Events
export interface StreamQueryCallbacks {
  onSelectedPages: (pages: string[]) => void;
  onChunk: (chunk: string) => void;
  onDone: (archivedAs?: string) => void;
  onError: (error: string) => void;
}

export async function queryWikiStream(
  question: string,
  save = false,
  callbacks: StreamQueryCallbacks
): Promise<void> {
  console.log('[queryWikiStream] Starting stream query:', { question, save });

  try {
    const res = await fetch('/api/query/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, save }),
    });

    console.log('[queryWikiStream] Response status:', res.status, 'ok:', res.ok);

    if (!res.ok) {
      console.error('[queryWikiStream] Response not OK, status:', res.status);
      throw new Error(`HTTP error: ${res.status}`);
    }

    const reader = res.body?.getReader();
    if (!reader) {
      console.error('[queryWikiStream] No response body reader');
      throw new Error('No response body reader');
    }

    console.log('[queryWikiStream] Reader created, starting to read...');

    const decoder = new TextDecoder();
    let currentEvent: string | null = null;
    let chunkCount = 0;
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        console.log('[queryWikiStream] Stream ended, total chunks:', chunkCount);
        break;
      }

      const chunk = decoder.decode(value, { stream: true });
      buffer += chunk;

      const lines = buffer.split('\n');
      // Keep the last partial line in buffer
      buffer = lines.pop() || '';

      for (const line of lines) {
        const trimmedLine = line.trim();
        if (trimmedLine.startsWith('event: ')) {
          currentEvent = trimmedLine.slice(7).trim();
        } else if (trimmedLine.startsWith('data: ')) {
          const data = trimmedLine.slice(6).trim();
          if (!data) continue;

          try {
            const parsed = JSON.parse(data);
            console.log('[queryWikiStream] Event:', currentEvent, 'Data:', data);

            if (currentEvent === 'selected_pages' && Array.isArray(parsed)) {
              console.log('[queryWikiStream] ✓ Calling onSelectedPages with', parsed.length, 'pages');
              callbacks.onSelectedPages(parsed);
            } else if (parsed.error) {
              console.log('[queryWikiStream] ✗ Error received:', parsed.error);
              callbacks.onError(parsed.error);
              return;
            } else if (parsed.chunk) {
              chunkCount++;
              callbacks.onChunk(parsed.chunk);
            } else if (parsed.archived_as !== undefined) {
              console.log('[queryWikiStream] ✓ Calling onDone with:', parsed.archived_as);
              callbacks.onDone(parsed.archived_as);
            }
          } catch (e) {
            console.error('[queryWikiStream] Failed to parse SSE data:', data, e);
          }
        }
      }
    }
  } catch (e: any) {
    console.error('[queryWikiStream] Stream error:', e);
    callbacks.onError(e.message || 'Unknown error');
    throw e;
  }
}

export async function lintWiki(fix = false): Promise<LintResponse> {
  const res = await api.post<LintResponse>('/lint', { fix });
  return res.data;
}

// ── Interactive Ingest API ─────────────────────────────────

export interface KeyPointsResponse {
  key_points: string[];
  session_id: string;
}

export interface PageProposal {
  filename: string;
  action: 'create' | 'update';
  strategy: string;
  diff?: string;
  content_preview: string;
}

export interface ProposePagesResponse {
  proposals: PageProposal[];
  session_id: string;
}

export interface ApplyRequest {
  session_id: string;
  approved_pages: string[];
  rejected_pages?: string[];
  strategies?: Record<string, string>;
}

export interface ApplyResponse {
  created: string[];
  updated: string[];
  pages_affected: string[];
}

export async function ingestStart(sourceFile: string): Promise<KeyPointsResponse> {
  const res = await api.post<KeyPointsResponse>('/ingest/start', { source_file: sourceFile });
  return res.data;
}

export async function ingestPropose(
  sessionId: string,
  approvedKeyPoints?: string[],
  userFeedback?: string
): Promise<ProposePagesResponse> {
  const res = await api.post<ProposePagesResponse>('/ingest/propose', {
    session_id: sessionId,
    approved_key_points: approvedKeyPoints,
    user_feedback: userFeedback,
  });
  return res.data;
}

export async function ingestApply(req: ApplyRequest): Promise<ApplyResponse> {
  const res = await api.post<ApplyResponse>('/ingest/apply', req);
  return res.data;
}

// ── QMD API ──────────────────────────────────────────────

export interface QMDIndexRequest {
  force: boolean;
}

export interface QMDIndexResponse {
  indexed: number;
  message: string;
}

export interface QMDStatusResponse {
  available: boolean;
  cache_dir: string;
  cache_exists: boolean;
  indexed_pages: number;
  total_pages: number;
  search_mode: string;  // "QMD Semantic", "SimpleEmbedder (TF-IDF)", "BM25 Keyword"
}

export async function qmdIndex(force: boolean = false): Promise<QMDIndexResponse> {
  const res = await api.post<QMDIndexResponse>('/qmd/index', { force });
  return res.data;
}

export async function qmdStatus(): Promise<QMDStatusResponse> {
  const res = await api.get<QMDStatusResponse>('/qmd/status');
  return res.data;
}

// ── Graph API ──────────────────────────────────────────────

export interface GraphNode {
  id: string;
  title: string;
  type: string;
  inbound: number;
  outbound: number;
}

export interface GraphEdge {
  source: string;
  target: string;
}

export interface GraphStats {
  total_nodes: number;
  total_edges: number;
  orphan_pages: number;
  hubs: Array<{ page: string; links: number }>;
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  stats: GraphStats;
}

export async function fetchGraph(): Promise<GraphResponse> {
  const res = await api.get<GraphResponse>('/graph');
  return res.data;
}
