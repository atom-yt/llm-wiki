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

export async function lintWiki(fix = false): Promise<LintResponse> {
  const res = await api.post<LintResponse>('/lint', { fix });
  return res.data;
}
