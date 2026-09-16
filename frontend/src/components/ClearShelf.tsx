import { useState } from "react";
import { api, ApiError } from "../api/client";
import { Card, Spinner } from "./Primitives";

const pill =
  "rounded-full border px-2.5 py-[3px] text-[11px] font-light tracking-wide transition whitespace-nowrap";

export function ClearShelf({
  bookCount,
  onCleared,
  onCancel,
  onNotify,
}: {
  bookCount: number;
  onCleared: () => void;
  onCancel: () => void;
  onNotify: (tone: "success" | "error" | "info", text: string) => void;
}) {
  const [busy, setBusy] = useState(false);

  async function clear() {
    setBusy(true);
    try {
      const { deleted } = await api.clearLibrary();
      onNotify("success", `Removed ${deleted} ${deleted === 1 ? "book" : "books"}.`);
      onCleared();
    } catch (error) {
      onNotify(
        "error",
        error instanceof ApiError ? error.message : "Could not clear the shelf.",
      );
    } finally {
      setBusy(false);
    }
  }

  if (bookCount === 0) {
    return (
      <Card className="p-6 text-center">
        <p className="text-xs font-light text-ink">Your shelf is already empty.</p>
      </Card>
    );
  }

  return (
    <Card className="p-6 text-center">
      <p className="text-sm font-light text-ink">
        Remove all {bookCount.toLocaleString()} {bookCount === 1 ? "book" : "books"}?
      </p>
      <p className="mt-1 text-[11px] font-light text-ink-secondary">
        This cannot be undone.
      </p>

      <div className="mt-5 flex items-center justify-center gap-2">
        <button
          type="button"
          onClick={onCancel}
          disabled={busy}
          className={`${pill} border-hairline text-ink-secondary hover:text-ink`}
        >
          Cancel
        </button>
        {busy ? (
          <Spinner label="Removing…" />
        ) : (
          <button
            type="button"
            onClick={() => void clear()}
            className={`${pill} border-hairline text-critical hover:bg-surface-2`}
          >
            Remove all
          </button>
        )}
      </div>
    </Card>
  );
}
