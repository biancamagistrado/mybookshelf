import { useRef, useState } from "react";
import { api, ApiError } from "../api/client";
import { shelfLabel } from "../lib/format";
import type { EnrichmentStatus, ImportResult, ListImportResult } from "../types";
import { Button, Card, Spinner, inputClass } from "./Primitives";

const SHELF_OPTIONS = ["to-read", "currently-reading", "read", "did-not-finish"];
const MAX_LINES = 25;

function TypedList({
  onImported,
  onNotify,
}: {
  onImported: () => void;
  onNotify: (tone: "success" | "error" | "info", text: string) => void;
}) {
  const [text, setText] = useState("");
  const [shelf, setShelf] = useState("to-read");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ListImportResult | null>(null);

  const lines = text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  async function submit() {
    if (lines.length === 0) return;
    setBusy(true);
    setResult(null);
    try {
      const summary = await api.importList(lines.slice(0, MAX_LINES), shelf);
      setResult(summary);
      if (summary.created > 0) {
        setText("");
        onNotify(
          "success",
          `Added ${summary.created} ${summary.created === 1 ? "book" : "books"}.`,
        );
        onImported();
      } else {
        onNotify("info", "Nothing new was added.");
      }
    } catch (error) {
      onNotify(
        "error",
        error instanceof ApiError ? error.message : "Could not look those up.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <p className="mb-2 text-xs font-light text-ink">
        Or type book titles or ISBNs, one per line
      </p>
      <textarea
        value={text}
        onChange={(event) => setText(event.target.value)}
        rows={5}
        placeholder={"Piranesi\nDune\n9780441172719"}
        aria-label="Book titles or ISBNs, one per line"
        className={`${inputClass} resize-y font-mono`}
      />

      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <label className="flex items-center gap-2 text-[11px] font-light text-ink-secondary">
          Add to
          <select
            value={shelf}
            onChange={(event) => setShelf(event.target.value)}
            className={`${inputClass} w-auto py-1`}
          >
            {SHELF_OPTIONS.map((value) => (
              <option key={value} value={value}>
                {shelfLabel(value)}
              </option>
            ))}
          </select>
        </label>

        {busy ? (
          <Spinner label="Looking them up…" />
        ) : (
          <Button variant="primary" type="button" onClick={() => void submit()} disabled={lines.length === 0}>
            Add {lines.length > 0 ? `${Math.min(lines.length, MAX_LINES)} ` : ""}
            {lines.length === 1 ? "book" : "books"}
          </Button>
        )}
      </div>

      {lines.length > MAX_LINES && (
        <p className="mt-2 text-[11px] font-light text-ink-secondary">
          Only the first {MAX_LINES} lines will be looked up.
        </p>
      )}

      {result && result.not_found.length > 0 && (
        <p className="mt-3 text-[11px] font-light text-ink-secondary">
          Not found: {result.not_found.join(", ")}
        </p>
      )}
      {result && result.already_on_shelf.length > 0 && (
        <p className="mt-1 text-[11px] font-light text-ink-secondary">
          Already on your shelves: {result.already_on_shelf.join(", ")}
        </p>
      )}
    </div>
  );
}

export function ImportPanel({
  enrichment,
  onImported,
  onNotify,
}: {
  enrichment: EnrichmentStatus | null;
  onImported: () => void;
  onNotify: (tone: "success" | "error" | "info", text: string) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);

  async function upload(file: File) {
    if (!file.name.toLowerCase().endsWith(".csv")) {
      onNotify("error", "That is not a .csv file.");
      return;
    }
    setUploading(true);
    setResult(null);
    try {
      const summary = await api.importCsv(file, true);
      setResult(summary);
      onNotify(
        "success",
        `Added ${summary.created} ${summary.created === 1 ? "book" : "books"}` +
          (summary.updated ? `, updated ${summary.updated}.` : "."),
      );
      onImported();
    } catch (error) {
      onNotify(
        "error",
        error instanceof ApiError ? error.message : "The import failed.",
      );
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <Card className="p-6">
      <div
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          const file = event.dataTransfer.files?.[0];
          if (file) void upload(file);
        }}
        className={`flex flex-col items-center gap-3 rounded-xl border-2 border-dashed px-6 py-12 text-center transition ${
          dragging ? "border-accent bg-accent-soft/30" : "border-hairline"
        }`}
      >
        <p className="text-xs font-light text-ink">Drop a CSV file here</p>

        <input
          ref={inputRef}
          type="file"
          accept=".csv,text/csv"
          className="sr-only"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void upload(file);
          }}
        />
        {uploading ? (
          <Spinner label="Reading your file…" />
        ) : (
          <Button
            variant="primary"
            type="button"
            onClick={() => inputRef.current?.click()}
          >
            Choose a file
          </Button>
        )}
      </div>

      {result?.warnings.map((warning) => (
        <p
          key={warning}
          className="mt-4 rounded-lg border border-hairline bg-surface-2 px-3 py-2 text-[11px] font-light text-ink-secondary"
        >
          {warning}
        </p>
      ))}

      {result && (
        <p className="mt-4 text-center text-xs font-light text-ink-secondary">
          Added {result.created.toLocaleString()}
          {result.updated > 0 && `, updated ${result.updated.toLocaleString()}`}
          {result.skipped > 0 && `, skipped ${result.skipped.toLocaleString()}`}.
        </p>
      )}

      {enrichment?.running && (
        <p className="mt-4 flex justify-center">
          <Spinner label="Finding covers and genres…" />
        </p>
      )}

      <hr className="my-6 border-hairline" />

      <TypedList onImported={onImported} onNotify={onNotify} />
    </Card>
  );
}
