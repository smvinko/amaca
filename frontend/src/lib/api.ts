/**
 * Typed wrappers around the amaca HTTP API.
 *
 * All calls are credentialed (cookies are sent) so the same session
 * cookie set by the OAuth callback (or the dev-login endpoint) carries
 * through. Errors are thrown as ApiError with the parsed body.
 */

export class ApiError extends Error {
  constructor(public status: number, public body: unknown, message?: string) {
    super(message ?? `HTTP ${status}`);
  }
}

async function req<T = unknown>(
  path: string,
  init: RequestInit = {}
): Promise<T> {
  const r = await fetch(path, {
    credentials: 'include',
    headers: { 'content-type': 'application/json', ...(init.headers ?? {}) },
    ...init
  });
  let body: unknown = null;
  const ct = r.headers.get('content-type') ?? '';
  if (ct.includes('application/json')) {
    try { body = await r.json(); } catch { /* empty body is fine */ }
  } else if (r.status !== 204) {
    body = await r.text();
  }
  if (!r.ok) throw new ApiError(r.status, body, `${init.method ?? 'GET'} ${path} → ${r.status}`);
  return body as T;
}

// ------------------------------------------------------------------- types

export interface UserOut {
  id: number;
  github_username: string;
  email: string | null;
  role: 'user' | 'admin';
  disabled: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface CodeOut {
  name: string;
  title: string;
  version: string;
  input_schema: JsonSchema;
  output_schema: JsonSchema;
}

export interface JsonSchema {
  type?: string;
  title?: string;
  description?: string;
  properties?: Record<string, JsonSchemaProperty>;
  required?: string[];
  // amaca custom: UI form grouping. If present, the form renders each
  // group as a labelled section; any field absent from every group
  // falls into an "Other" section at the end. `columns`, when present,
  // is an explicit multi-column layout: each inner array is one column
  // (top-to-bottom). Group fields not listed in any column render
  // full-width, in declared order, before the column block.
  'x-input-groups'?: {
    title: string;
    fields: string[];
    columns?: string[][];
    // Optional read-only preview plot rendered below the group. `kind`
    // selects a renderer; `fields` maps each role the renderer needs
    // to a form field name (the plot recomputes live from their values).
    plot?: {
      kind: string;
      title?: string;
      fields: Record<string, string>;
      x_label?: string;
      y_label?: string;
    };
  }[];
  [k: string]: unknown;
}

export interface JsonSchemaProperty {
  type?: string;
  title?: string;
  description?: string;
  default?: unknown;
  minimum?: number;
  maximum?: number;
  exclusiveMinimum?: number;
  exclusiveMaximum?: number;
  minLength?: number;
  maxLength?: number;
  enum?: unknown[];
  anyOf?: { type?: string; const?: unknown }[];
  // `disabled` options are shown but not selectable (rendered inert /
  // greyed, same as an out-of-policy periodic-table element).
  oneOf?: { const?: unknown; title?: string; disabled?: boolean }[];
  // amaca custom: display-unit override (user types in `label` units;
  // bound value = input * factor in the field's native unit).
  'x-display-unit'?: { factor: number; label: string };
  // amaca custom: visibility gate driven by another field's value.
  // Exactly one of equals / not_equals is set.
  'x-show-when'?: { field: string; equals?: unknown; not_equals?: unknown };
  // amaca custom: render this field with a richer named widget instead
  // of the type-default control (e.g. 'periodic-table' for an enum of
  // element symbols).
  'x-widget'?: string;
  // amaca custom: this field must occupy its own full-width row in its
  // group (siblings never share/wrap beside it, at any width).
  'x-full-row'?: boolean;
  [k: string]: unknown;
}

export type JobStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled';

export interface JobListItem {
  id: number;
  code_name: string;
  status: JobStatus;
  created_at: string;
  finished_at: string | null;
}

export interface JobOut {
  id: number;
  owner_id: number;
  code_name: string;
  code_version: string;
  status: JobStatus;
  inputs: Record<string, unknown>;
  outputs: Record<string, unknown> | null;
  error_text: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface JobLogLine { ts: string; line: string; }

export interface TokenOut {
  id: number;
  name: string;
  prefix: string;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
}

// --------------------------------------------------------------- endpoints

export const api = {
  // auth
  me:        ()                  => req<UserOut>('/api/auth/me'),
  logout:    ()                  => req<void>('/api/auth/logout', { method: 'POST' }),
  devLogin:  (username: string)  => req<UserOut>('/api/auth/dev-login', {
    method: 'POST', body: JSON.stringify({ username })
  }),
  // codes
  listCodes: ()                  => req<CodeOut[]>('/api/codes'),
  getCode:   (name: string)      => req<CodeOut>(`/api/codes/${encodeURIComponent(name)}`),
  // jobs
  submitJob: (code: string, inputs: Record<string, unknown>) =>
    req<JobOut>('/api/jobs', { method: 'POST', body: JSON.stringify({ code, inputs }) }),
  listJobs:  (params?: { code?: string; status?: string; limit?: number }) => {
    const q = new URLSearchParams();
    if (params?.code)   q.set('code',   params.code);
    if (params?.status) q.set('status', params.status);
    if (params?.limit)  q.set('limit',  String(params.limit));
    const qs = q.toString();
    return req<JobListItem[]>(`/api/jobs${qs ? '?' + qs : ''}`);
  },
  getJob:    (id: number)        => req<JobOut>(`/api/jobs/${id}`),
  cancelJob: (id: number)        => req<void>(`/api/jobs/${id}`, { method: 'DELETE' }),
  jobLogs:   (id: number)        => req<JobLogLine[]>(`/api/jobs/${id}/logs`),
  // tokens
  listTokens:  ()                  => req<TokenOut[]>('/api/auth/tokens'),
  createToken: (name: string)      =>
    req<{ token: string; info: TokenOut }>('/api/auth/tokens', {
      method: 'POST', body: JSON.stringify({ name })
    }),
  revokeToken: (id: number)        => req<void>(`/api/auth/tokens/${id}`, { method: 'DELETE' })
};
