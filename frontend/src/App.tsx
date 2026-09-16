import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "./api/client";
import type {
  Book,
  BookFilters,
  EnrichmentStatus,
  ShelfCount,
  Stats,
} from "./types";
import { useTheme } from "./lib/useTheme";
import { BookDialog } from "./components/BookDialog";
import { BookShelfView } from "./components/BookShelf";
import { ClearShelf } from "./components/ClearShelf";
import { ImportPanel } from "./components/ImportPanel";
import { StatsView } from "./components/StatsView";
import { ToastStack, type ToastMessage, type ToastTone } from "./components/Toast";

const PAGE_SIZE = 200;

const SHELVES: { value: string | null; label: string }[] = [
  { value: null, label: "All" },
  { value: "currently-reading", label: "Currently reading" },
  { value: "to-read", label: "Want to read" },
  { value: "read", label: "Read" },
  { value: "did-not-finish", label: "Did not finish" },
];

const INITIAL_FILTERS: BookFilters = {
  shelf: null,
  author: null,
  genre: null,
  search: "",
  sort: "date_added",
  direction: "desc",
};

type Panel = "import" | "clear" | "stats" | null;

const THEME_SWATCH: Record<string, string> = {
  light: "#ffffff",
  yellow: "#e8c882",
  dark: "#1a1a19",
};

export default function App() {
  const { resolved, nextTheme, cycle } = useTheme();
  const [filters, setFilters] = useState<BookFilters>(INITIAL_FILTERS);
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [panel, setPanel] = useState<Panel>(null);

  const [books, setBooks] = useState<Book[]>([]);
  const [loading, setLoading] = useState(true);
  const [slowLoad, setSlowLoad] = useState(false);

  const [shelves, setShelves] = useState<ShelfCount[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [enrichment, setEnrichment] = useState<EnrichmentStatus | null>(null);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Book | null>(null);
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const notify = useCallback((tone: ToastTone, text: string) => {
    setToasts((current) => [
      ...current,
      { id: Date.now() + Math.random(), tone, text },
    ]);
  }, []);

  const dismissToast = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(filters.search), 300);
    return () => window.clearTimeout(timer);
  }, [filters.search]);

  useEffect(() => {
    if (!loading) {
      setSlowLoad(false);
      return;
    }
    const timer = window.setTimeout(() => setSlowLoad(true), 5000);
    return () => window.clearTimeout(timer);
  }, [loading]);

  const loadFacets = useCallback(async () => {
    try {
      setShelves(await api.getShelves());
    } catch (error) {
      if (error instanceof ApiError && error.status === 0) notify("error", error.message);
    }
  }, [notify]);

  const loadStats = useCallback(async () => {
    try {
      setStats(await api.getStats());
    } catch {
    }
  }, []);

  const loadEnrichment = useCallback(async () => {
    try {
      setEnrichment(await api.getEnrichmentStatus());
    } catch {
    }
  }, []);

  const requestId = useRef(0);
  const loadBooks = useCallback(async () => {
    const id = ++requestId.current;
    setLoading(true);
    try {
      const page = await api.listBooks({
        shelf: filters.shelf,
        author: filters.author,
        genre: filters.genre,
        search: debouncedSearch || null,
        sort: filters.sort,
        direction: filters.direction,
        limit: PAGE_SIZE,
        offset: 0,
      });
      if (id !== requestId.current) return;
      setBooks(page.items);
    } catch (error) {
      if (id !== requestId.current) return;
      notify(
        "error",
        error instanceof ApiError ? error.message : "Could not load your books.",
      );
    } finally {
      if (id === requestId.current) setLoading(false);
    }
  }, [filters, debouncedSearch, notify]);

  useEffect(() => {
    void loadBooks();
  }, [loadBooks]);

  useEffect(() => {
    void loadFacets();
    void loadStats();
    void loadEnrichment();
  }, [loadFacets, loadStats, loadEnrichment]);

  useEffect(() => {
    if (!enrichment?.running) return;
    const timer = window.setInterval(async () => {
      const status = await api.getEnrichmentStatus().catch(() => null);
      if (!status) return;
      setEnrichment(status);
      if (!status.running) {
        void loadBooks();
        void loadFacets();
        void loadStats();
      }
    }, 3000);
    return () => window.clearInterval(timer);
  }, [enrichment?.running, loadBooks, loadFacets, loadStats]);

  useEffect(() => {
    if (!panel) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setPanel(null);
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [panel]);

  const refreshAll = useCallback(() => {
    void loadBooks();
    void loadFacets();
    void loadStats();
    void loadEnrichment();
  }, [loadBooks, loadFacets, loadStats, loadEnrichment]);

  async function handleDelete(book: Book) {
    if (!window.confirm(`Remove \u201c${book.title}\u201d from your shelves?`)) return;
    try {
      await api.deleteBook(book.id);
      notify("success", `Removed \u201c${book.title}\u201d.`);
      refreshAll();
    } catch (error) {
      notify(
        "error",
        error instanceof ApiError ? error.message : "Could not remove the book.",
      );
    }
  }

  const set = (patch: Partial<BookFilters>) =>
    setFilters((current) => ({ ...current, ...patch }));

  const togglePanel = (next: Panel) =>
    setPanel((current) => (current === next ? null : next));

  const pill =
    "rounded-full border px-2.5 py-[3px] text-[11px] font-light tracking-wide transition whitespace-nowrap";
  const pillIdle =
    "border-hairline text-ink-secondary hover:border-ink-muted hover:text-ink";
  const pillActive = "border-ink-secondary bg-surface-2 text-ink";

  const totalBooks = shelves.reduce((sum, shelf) => sum + shelf.count, 0);

  const overlay =
    "fixed inset-0 z-40 flex justify-center overflow-y-auto bg-black/40 p-4";

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-page">
      <button
        type="button"
        onClick={cycle}
        aria-label={`Theme: ${resolved}. Switch to ${nextTheme}.`}
        className="fixed right-4 top-4 z-20 size-6 rounded-full border border-hairline shadow-sm transition hover:scale-110"
        style={{ backgroundColor: THEME_SWATCH[resolved] }}
      />

      <main className="mx-auto flex w-full max-w-5xl shrink-0 flex-col px-4 pt-6 pb-4 sm:pt-10">
        <h1
          className="text-center text-6xl leading-[1.1] text-ink sm:text-7xl"
          style={{ fontFamily: '"Parisienne", cursive' }}
        >
          My Bookshelf
        </h1>

        <p className="mt-5 text-center text-[10px] font-light uppercase tracking-[0.22em] text-ink-muted">
          {totalBooks.toLocaleString()} {totalBooks === 1 ? "Book" : "Books"}
        </p>

        <div className="mx-auto mt-9 w-full max-w-md">
          <input
            type="search"
            value={filters.search}
            onChange={(event) => set({ search: event.target.value })}
            placeholder="Search title, author or genre"
            aria-label="Search by title, author or genre"
            className="w-full border-0 border-b border-hairline bg-transparent px-1 py-2 text-center font-mono text-xs font-light tracking-wide text-ink placeholder:text-ink-muted focus:border-ink-secondary focus:outline-none"
          />
        </div>

        <div
          role="tablist"
          aria-label="Shelves"
          className="mx-auto mt-8 flex flex-wrap justify-center gap-2.5"
        >
          {SHELVES.map((shelf) => {
            const selected = filters.shelf === shelf.value;
            return (
              <button
                key={shelf.label}
                role="tab"
                aria-selected={selected}
                onClick={() => set({ shelf: shelf.value })}
                className={`${pill} ${selected ? pillActive : pillIdle}`}
              >
                {shelf.label}
              </button>
            );
          })}
        </div>

        <div className="mx-auto mt-3 flex flex-wrap items-center justify-center gap-2.5">
          <button
            className={`${pill} ${pillIdle}`}
            onClick={() => {
              setEditing(null);
              setDialogOpen(true);
            }}
          >
            <span aria-hidden="true" className="mr-1">
              +
            </span>
            Add book
          </button>
          <button
            className={`${pill} ${panel === "import" ? pillActive : pillIdle}`}
            aria-pressed={panel === "import"}
            onClick={() => togglePanel("import")}
          >
            <span aria-hidden="true" className="mr-1">
              ↓
            </span>
            Import
          </button>
          <button
            className={`${pill} ${
              panel === "clear" ? pillActive : pillIdle
            } disabled:cursor-not-allowed disabled:opacity-40`}
            aria-pressed={panel === "clear"}
            disabled={totalBooks === 0}
            onClick={() => togglePanel("clear")}
          >
            <svg
              aria-hidden="true"
              viewBox="0 0 16 16"
              className="mr-1 inline-block h-3 w-3 -translate-y-px"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M2.5 4h11M6 4V2.5h4V4M4 4l.7 9.5h6.6L12 4M6.8 6.5v4.5M9.2 6.5v4.5" />
            </svg>
            Clear shelf
          </button>
          <button
            className={`${pill} ${panel === "stats" ? pillActive : pillIdle}`}
            aria-pressed={panel === "stats"}
            onClick={() => togglePanel("stats")}
          >
            Stats
          </button>
        </div>
      </main>

      <div className="min-h-0 flex-1 pb-5">
        {loading && books.length === 0 ? (
          <div
            role="status"
            className="flex h-full flex-col items-center justify-center gap-4 px-6 text-center"
          >
            <span
              aria-hidden="true"
              className="size-8 animate-spin rounded-full border-2 border-accent border-t-transparent"
            />
            <p className="text-sm font-light text-ink-secondary">
              Loading your shelf…
            </p>
            {slowLoad && (
              <p className="max-w-xs text-xs font-light text-ink-muted">
                The server sleeps when nobody is using it. Waking it up takes up
                to a minute.
              </p>
            )}
          </div>
        ) : !loading && books.length === 0 ? (
          <p className="flex h-full items-center justify-center px-6 text-center text-sm text-ink-secondary">
            {filters.search
              ? "Nothing here matches that search."
              : "This shelf is empty."}
          </p>
        ) : (
          <BookShelfView
            books={books}
            loading={loading}
            onSelect={(book) => {
              setEditing(book);
              setDialogOpen(true);
            }}
          />
        )}
      </div>

      {panel && (
        <div
          className={overlay}
          onClick={(event) => {
            if (event.target === event.currentTarget) setPanel(null);
          }}
        >
          <div
            className={`relative my-auto w-full ${
              panel === "clear" ? "max-w-sm" : panel === "import" ? "max-w-lg" : "max-w-3xl"
            }`}
          >
            {panel === "import" ? (
              <ImportPanel
                enrichment={enrichment}
                onImported={refreshAll}
                onNotify={notify}
              />
            ) : panel === "clear" ? (
              <ClearShelf
                bookCount={totalBooks}
                onCleared={() => {
                  refreshAll();
                  setPanel(null);
                }}
                onCancel={() => setPanel(null)}
                onNotify={notify}
              />
            ) : (
              <div className="rounded-xl border border-hairline bg-surface p-5">
                <StatsView stats={stats} />
              </div>
            )}
            {panel !== "clear" && (
              <button
                type="button"
                onClick={() => setPanel(null)}
                aria-label="Close"
                className="absolute right-3 top-2.5 leading-none text-ink-muted hover:text-ink"
              >
                ✕
              </button>
            )}
          </div>
        </div>
      )}

      <BookDialog
        open={dialogOpen}
        book={editing}
        shelves={shelves}
        onClose={() => setDialogOpen(false)}
        onSaved={refreshAll}
        onDelete={handleDelete}
        onNotify={notify}
      />

      <ToastStack messages={toasts} onDismiss={dismissToast} />
    </div>
  );
}
