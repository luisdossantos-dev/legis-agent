/**
 * HTTP client for communication with the FastAPI backend.
 */

import { validateUploadFile, isValidUUID } from "./validation";

const API_BASE = "http://localhost:8000";
const API_PREFIX = "/api/v1";

// ── Types ────────────────────────────────────────────────────

export interface DocumentSummary {
  id: string;
  filename: string;
  pages: number;
  chunks: number;
  status: string;
  created_at: string;
}

export interface DocumentListResponse {
  documents: DocumentSummary[];
  total: number;
}

export interface AnalysisResult {
  document_id: string;
  document_type: string | null;
  parties: string[];
  dates: string[];
  amounts: Array<{ description: string }>;
  clauses: Array<{ title: string; content: string; risk_level: string | null }>;
  risks: string[];
  summary: string;
}

export interface AnalyzeResponse {
  analysis: AnalysisResult;
  tokens_used: number;
  processing_time_ms: number;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  references?: string[];
}

export interface ChatResponse {
  response: string;
  references: string[];
  tokens_used: number;
}

// ── Helper ────────────────────────────────────────────────────

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${path}`;

  const defaultHeaders: Record<string, string> = {};
  if (!(options.body instanceof FormData)) {
    defaultHeaders["Content-Type"] = "application/json";
  }

  const res = await fetch(url, {
    ...options,
    headers: {
      ...defaultHeaders,
      ...(options.headers as Record<string, string>),
    },
  });

  if (!res.ok) {
    const errorBody = await res.text();
    throw new Error(`HTTP ${res.status}: ${errorBody}`);
  }

  return res.json();
}

// ── API Methods ───────────────────────────────────────────────

export const apiClient = {
  /** Backend health check */
  async health(): Promise<boolean> {
    try {
      const res = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(3000) });
      const data = await res.json();
      return data.status === "ok";
    } catch {
      return false;
    }
  },

  /** Upload a document */
  async uploadDocument(file: File, onProgress?: (percent: number) => void): Promise<{ id: string }> {
    const validation = validateUploadFile(file);
    if (!validation.valid) {
      throw new Error(validation.error ?? "Invalid file.");
    }

    return new Promise((resolve, reject) => {
      const formData = new FormData();
      formData.append("file", file);

      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${API_BASE}${API_PREFIX}/documents/upload`);

      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable && onProgress) {
          onProgress(Math.round((e.loaded / e.total) * 100));
        }
      };

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            resolve(JSON.parse(xhr.responseText));
          } catch {
            reject(new Error("Invalid response from server"));
          }
        } else {
          try {
            const err = JSON.parse(xhr.responseText);
            reject(new Error(err.detail || `HTTP ${xhr.status}`));
          } catch {
            reject(new Error(`HTTP ${xhr.status}: Upload failed`));
          }
        }
      };

      xhr.onerror = () => reject(new Error("Network error during upload"));
      xhr.onabort = () => reject(new Error("Upload aborted"));

      xhr.send(formData);
    });
  },

  /** List documents */
  async listDocuments(): Promise<DocumentSummary[]> {
    const data = await request<DocumentListResponse>(`${API_PREFIX}/documents/`);
    return data.documents;
  },

  /** Run analysis */
  async analyze(documentId: string, query?: string): Promise<AnalyzeResponse> {
    if (!isValidUUID(documentId)) {
      throw new Error("Invalid document ID format.");
    }
    return request<AnalyzeResponse>(`${API_PREFIX}/agents/analyze`, {
      method: "POST",
      body: JSON.stringify({
        document_id: documentId,
        query: query || "Analyze this legal document and extract its main components.",
      }),
    });
  },

  /** Chat with the agent */
  async chat(
    documentId: string,
    messages: ChatMessage[],
    query: string
  ): Promise<ChatResponse> {
    if (!isValidUUID(documentId)) {
      throw new Error("Invalid document ID format.");
    }
    return request<ChatResponse>(`${API_PREFIX}/agents/chat`, {
      method: "POST",
      body: JSON.stringify({
        document_id: documentId,
        messages,
        query,
      }),
    });
  },

  /** Email drafting */
  async draftEmail(body: {
    act_type: string;
    fields: Record<string, string>;
    sensitivity?: string;
    language?: string;
    urgent?: boolean;
    custom_query?: string;
    document_id?: string;
  }): Promise<EmailDraftResponse> {
    if (body.custom_query && body.custom_query.length > 2000) {
      throw new Error("Custom query is too long (max 2000 chars).");
    }
    return request<EmailDraftResponse>(`${API_PREFIX}/email/draft`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  async getEmailTemplates(): Promise<{ templates: any[] }> {
    return request<{ templates: any[] }>(`${API_PREFIX}/email/templates`);
  },

  /** Clause review */
  async reviewClause(body: {
    clause_text: string;
    clause_type?: string;
    context?: string;
  }): Promise<any> {
    return request<any>(`${API_PREFIX}/clauses/review`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  async getClauseTypes(): Promise<{ types: any[]; labels: Record<string, string> }> {
    return request<{ types: any[]; labels: Record<string, string> }>(`${API_PREFIX}/clauses/types`);
  },

  async getClauseChecklist(clauseType: string): Promise<any> {
    return request<any>(`${API_PREFIX}/clauses/checklist/${clauseType}`);
  },
};

export interface EmailDraftResponse {
  to: string;
  subject: string;
  body: string;
  attachments: string[];
  model_used: string;
  template_used: string | null;
  tokens_used: number;
}
