
import type {
  Book,
  BookPage,
  BookPatch,
  BookSuggestion,
  EnrichmentStatus,
  FacetCount,
  ImportResult,
  ListImportResult,
  NewBook,
  ShelfCount,
  Stats,
} from "../types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

const SESSION_KEY = "bookshelf-library-id";

function libraryId(): string {
  try {
    const existing = localStorage.getItem(SESSION_KEY);
    if (existing) return existing;
    const created = crypto.randomUUID();
    localStorage.setItem(SESSION_KEY, created);
    return created;
  } catch {
    return sessionFallback;
  }
}

const sessionFallback = crypto.randomUUID();

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function readError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    const detail = body?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      return detail.map((d: { msg?: string }) => d.msg ?? "Invalid value").join("; ");
    }
  } catch {
  }
  return response.statusText || `Request failed (${response.status})`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers: {
        ...(init?.body instanceof FormData
          ? {}
          : { "Content-Type": "application/json" }),
        "X-Session-Id": libraryId(),
        ...init?.headers,
      },
    });
  } catch {
    throw new ApiError("Could not reach the API. Is the backend running?", 0);
  }

  if (!response.ok) {
    throw new ApiError(await readError(response), response.status);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

function buildQuery(params: Record<string, string | number | boolean | null | undefined>) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== "") {
      search.set(key, String(value));
    }
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

export const api = {
  listBooks: (params: {
    shelf?: string | null;
    author?: string | null;
    genre?: string | null;
    search?: string | null;
    sort?: string;
    direction?: string;
    limit?: number;
    offset?: number;
  }) => request<BookPage>(`/api/books${buildQuery(params)}`),

  getShelves: () => request<ShelfCount[]>("/api/books/shelves"),
  getAuthors: () => request<FacetCount[]>("/api/books/authors?limit=300"),
  getGenres: () => request<FacetCount[]>("/api/books/genres?limit=300"),

  createBook: (book: NewBook) =>
    request<Book>("/api/books", { method: "POST", body: JSON.stringify(book) }),

  updateBook: (id: number, patch: BookPatch) =>
    request<Book>(`/api/books/${id}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),

  deleteBook: (id: number) =>
    request<void>(`/api/books/${id}`, { method: "DELETE" }),

  clearLibrary: () =>
    request<{ deleted: number }>("/api/books", { method: "DELETE" }),

  importCsv: (file: File, enrich: boolean) => {
    const form = new FormData();
    form.append("file", file);
    return request<ImportResult>(
      `/api/import/goodreads${buildQuery({ enrich })}`,
      { method: "POST", body: form },
    );
  },

  lookupBooks: (query: string) =>
    request<BookSuggestion[]>(`/api/lookup${buildQuery({ q: query, limit: 8 })}`),

  importList: (lines: string[], shelf: string) =>
    request<ListImportResult>("/api/import/list", {
      method: "POST",
      body: JSON.stringify({ lines, exclusive_shelf: shelf }),
    }),

  getStats: () => request<Stats>("/api/stats"),

  getEnrichmentStatus: () => request<EnrichmentStatus>("/api/enrichment/status"),

  enrichBook: (id: number) =>
    request<Book>(`/api/enrichment/books/${id}`, { method: "POST" }),
};
