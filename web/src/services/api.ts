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
