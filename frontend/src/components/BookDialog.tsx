import { useEffect, useId, useRef, useState } from "react";
import { api, ApiError } from "../api/client";
import type { Book, BookSuggestion, ShelfCount } from "../types";
import { shelfLabel } from "../lib/format";
import { Button, Field, inputClass } from "./Primitives";

const DEFAULT_SHELVES = [
  "currently-reading",
  "to-read",
  "read",
  "did-not-finish",
];

function CatalogueSearch({
  onPick,
}: {
  onPick: (suggestion: BookSuggestion) => void;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<BookSuggestion[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    const term = query.trim();
    if (term.length < 2) return;
    setSearching(true);
    setError(null);
    try {
      setResults(await api.lookupBooks(term));
    } catch (exc) {
      setError(
        exc instanceof ApiError ? exc.message : "The catalogue search failed.",
      );
      setResults(null);
    } finally {
      setSearching(false);
    }
  }

  return (
    <div className="rounded-lg border border-hairline bg-surface-2 p-3">
      <div className="flex gap-2">
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              void run();
            }
          }}
          placeholder="Type a title or ISBN…"
          aria-label="Search the book catalogue by title or ISBN"
          className={inputClass}
        />
        <Button type="button" onClick={() => void run()} disabled={searching}>
          {searching ? "Searching…" : "Search"}
        </Button>
      </div>

      {error && <p className="mt-2 text-xs text-critical">{error}</p>}

      {results && results.length === 0 && (
        <p className="mt-2 text-xs text-ink-secondary">
          No matches. Fill the fields in below instead.
        </p>
      )}

      {results && results.length > 0 && (
        <ul className="mt-2 max-h-56 divide-y divide-hairline overflow-y-auto">
          {results.map((result, index) => (
            <li key={`${result.title}-${index}`}>
              <button
                type="button"
                onClick={() => onPick(result)}
                className="flex w-full items-center gap-3 py-2 text-left transition hover:opacity-70"
              >
                {result.cover_url ? (
                  <img
                    src={result.cover_url}
                    alt=""
                    className="h-12 w-8 shrink-0 rounded object-cover"
                  />
                ) : (
                  <span className="h-12 w-8 shrink-0 rounded bg-surface" />
                )}
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-xs text-ink">
                    {result.title}
                  </span>
                  <span className="block truncate text-[11px] text-ink-secondary">
                    {result.author || "Unknown author"}
                    {result.year_published ? ` · ${result.year_published}` : ""}
                  </span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

interface FormState {
  title: string;
  author: string;
  exclusive_shelf: string;
  genres: string;
  number_of_pages: string;
  isbn13: string;
  date_read: string;
  cover_url: string | null;
  publisher: string | null;
  year_published: number | null;
}

function toFormState(book: Book | null): FormState {
  return {
    title: book?.title ?? "",
    author: book?.author ?? "",
    exclusive_shelf: book?.exclusive_shelf ?? "to-read",
    genres: book?.genres.map((genre) => genre.name).join(", ") ?? "",
    number_of_pages: book?.number_of_pages ? String(book.number_of_pages) : "",
    isbn13: book?.isbn13 ?? "",
    date_read: book?.date_read ?? "",
    cover_url: book?.cover_url ?? null,
    publisher: book?.publisher ?? null,
    year_published: book?.year_published ?? null,
  };
}

export function BookDialog({
  open,
  book,
  shelves,
  onClose,
  onSaved,
  onDelete,
  onNotify,
}: {
  open: boolean;
  book: Book | null;
  shelves: ShelfCount[];
  onClose: () => void;
  onSaved: () => void;
  onDelete: (book: Book) => Promise<void>;
  onNotify: (tone: "success" | "error" | "info", text: string) => void;
}) {
  const [form, setForm] = useState<FormState>(() => toFormState(book));
  const [saving, setSaving] = useState(false);
  const titleRef = useRef<HTMLInputElement>(null);
  const headingId = useId();

  useEffect(() => {
    if (open) {
      setForm(toFormState(book));
      const timer = window.setTimeout(() => titleRef.current?.focus(), 0);
      return () => window.clearTimeout(timer);
    }
  }, [open, book]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  const shelfOptions = Array.from(
    new Set([...DEFAULT_SHELVES, ...shelves.map((s) => s.shelf)]),
  );

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!form.title.trim()) {
      onNotify("error", "A title is required.");
      return;
    }

    const genres = form.genres
      .split(",")
      .map((genre) => genre.trim())
      .filter(Boolean);

    const payload = {
      title: form.title.trim(),
      author: form.author.trim(),
      exclusive_shelf: form.exclusive_shelf,
      genres,
      number_of_pages: form.number_of_pages ? Number(form.number_of_pages) : null,
      isbn13: form.isbn13.trim() || null,
      date_read: form.date_read || null,
      cover_url: form.cover_url,
      publisher: form.publisher,
      year_published: form.year_published,
    };

    setSaving(true);
    try {
      if (book) {
        await api.updateBook(book.id, payload);
        onNotify("success", `Updated “${payload.title}”.`);
      } else {
        await api.createBook(payload);
        onNotify("success", `Added “${payload.title}” to your shelves.`);
      }
      onSaved();
      onClose();
    } catch (error) {
      onNotify(
        "error",
        error instanceof ApiError ? error.message : "Could not save the book.",
      );
    } finally {
      setSaving(false);
    }
  }

  const set = (patch: Partial<FormState>) =>
    setForm((current) => ({ ...current, ...patch }));

  return (
    <div
      className="fixed inset-0 z-40 flex justify-center overflow-y-auto bg-black/40 p-4"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={headingId}
        className="my-auto w-full max-w-lg rounded-xl border border-hairline bg-surface p-6 shadow-xl"
      >
        <div className="mb-5 flex items-start justify-between gap-4">
          <div>
            <h2 id={headingId} className="text-sm font-medium text-ink">
              {book ? "Edit book" : "Add a book"}
            </h2>
            <p className="mt-0.5 text-[11px] font-light text-ink-secondary">
              {book
                ? "Change the details you track for this book."
                : "For books you have not imported from a library export."}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close dialog"
            className="text-ink-muted hover:text-ink"
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="grid gap-4">
          {book && form.cover_url && (
            <div className="flex items-start gap-4 rounded-lg border border-hairline bg-surface-2 p-3">
              <img
                src={form.cover_url}
                alt={`Cover of ${book.title}`}
                className="h-28 w-20 shrink-0 rounded object-cover shadow-sm"
              />
              <div className="min-w-0 flex-1 text-[11px] font-light text-ink-secondary">
                {form.publisher && <p className="truncate">{form.publisher}</p>}
                {form.year_published && <p>{form.year_published}</p>}
                {book.genres.length > 0 && (
                  <p className="mt-1 truncate">
                    {book.genres.map((genre) => genre.name).join(" · ")}
                  </p>
                )}
                <button
                  type="button"
                  onClick={() => set({ cover_url: null })}
                  className="mt-2 text-xs text-ink-muted underline-offset-2 hover:text-ink hover:underline"
                >
                  Remove cover
                </button>
              </div>
            </div>
          )}

          {!book && (
            <CatalogueSearch
              onPick={(suggestion) =>
                set({
                  title: suggestion.title,
                  author: suggestion.author,
                  isbn13: suggestion.isbn13 ?? "",
                  genres: suggestion.genres.join(", "),
                  number_of_pages: suggestion.number_of_pages
                    ? String(suggestion.number_of_pages)
                    : "",
                  cover_url: suggestion.cover_url,
                  publisher: suggestion.publisher,
                  year_published: suggestion.year_published,
                })
              }
            />
          )}

          <Field label="Title">
            <input
              ref={titleRef}
              required
              value={form.title}
              onChange={(event) => set({ title: event.target.value })}
              className={inputClass}
              placeholder="Piranesi"
            />
          </Field>

          <Field label="Author">
            <input
              value={form.author}
              onChange={(event) => set({ author: event.target.value })}
              className={inputClass}
              placeholder="Susanna Clarke"
            />
          </Field>

          <Field label="Shelf">
            <select
              value={form.exclusive_shelf}
              onChange={(event) => set({ exclusive_shelf: event.target.value })}
              className={inputClass}
            >
              {shelfOptions.map((shelf) => (
                <option key={shelf} value={shelf}>
                  {shelfLabel(shelf)}
                </option>
              ))}
            </select>
          </Field>

          <Field label="Genres" hint="Comma separated, for example Fantasy, Literary Fiction">
            <input
              value={form.genres}
              onChange={(event) => set({ genres: event.target.value })}
              className={inputClass}
              placeholder="Fantasy, Literary Fiction"
            />
          </Field>

          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Pages">
              <input
                type="number"
                min={0}
                value={form.number_of_pages}
                onChange={(event) => set({ number_of_pages: event.target.value })}
                className={inputClass}
              />
            </Field>
            <Field label="ISBN-13" hint="Improves lookups">
              <input
                value={form.isbn13}
                onChange={(event) => set({ isbn13: event.target.value })}
                className={inputClass}
                placeholder="9781635575637"
              />
            </Field>
            <Field label="Date read">
              <input
                type="date"
                value={form.date_read}
                onChange={(event) => set({ date_read: event.target.value })}
                className={inputClass}
              />
            </Field>
          </div>

          <div className="mt-2 flex items-center justify-end gap-2">
            {book && (
              <Button
                type="button"
                variant="danger"
                className="mr-auto"
                disabled={saving}
                onClick={async () => {
                  await onDelete(book);
                  onClose();
                }}
              >
                Remove
              </Button>
            )}
            <Button type="button" variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" disabled={saving}>
              {saving ? "Saving…" : book ? "Save changes" : "Add book"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
