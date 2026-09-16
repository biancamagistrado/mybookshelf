import { useCallback, useEffect, useRef, useState } from "react";
import type { Book } from "../types";
import { SPINE_GAP, spineStyle } from "../lib/spine";

const CAPTION_HEIGHT = 36;
const PLANK_HEIGHT = 22;
const HEADROOM = 16;
const MIN_BOOKS_HEIGHT = 80;
const MAX_BOOKS_HEIGHT = 260;

function useMeasuredHeight<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [height, setHeight] = useState(0);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) =>
      setHeight(entry.contentRect.height),
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return { ref, height };
}

function useScrollEdges(deps: unknown) {
  const ref = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  const measure = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    setCanScrollLeft(el.scrollLeft > 1);
    setCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 1);
  }, []);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    measure();
    el.addEventListener("scroll", measure, { passive: true });
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => {
      el.removeEventListener("scroll", measure);
      observer.disconnect();
    };
  }, [measure, deps]);

  const scrollByPage = useCallback((direction: 1 | -1) => {
    const el = ref.current;
    if (!el) return;
    el.scrollBy({ left: direction * el.clientWidth * 0.8, behavior: "smooth" });
  }, []);

  return { ref, canScrollLeft, canScrollRight, scrollByPage };
}

function ScrollArrow({
  direction,
  onClick,
}: {
  direction: "left" | "right";
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={direction === "left" ? "Show earlier books" : "Show more books"}
      className={`absolute bottom-0 z-10 flex size-8 items-center justify-center rounded-full border border-hairline bg-page/85 text-ink-secondary backdrop-blur transition hover:text-ink ${
        direction === "left" ? "left-2" : "right-2"
      }`}
      style={{ marginBottom: PLANK_HEIGHT + 8 }}
    >
      <span aria-hidden="true" className="text-lg leading-none">
        {direction === "left" ? "‹" : "›"}
      </span>
    </button>
  );
}

function BookSpine({
  book,
  shelfHeight,
  active,
  onActivate,
  onDeactivate,
  onSelect,
}: {
  book: Book;
  shelfHeight: number;
  active: boolean;
  onActivate: () => void;
  onDeactivate: () => void;
  onSelect: (book: Book) => void;
}) {
  const { width, heightPct, color } = spineStyle(book);
  const height = Math.round((heightPct / 100) * shelfHeight);
  const showAuthor = width >= 30 && height > 120;

  return (
    <li className="flex shrink-0 items-end" style={{ width }}>
      <button
        type="button"
        onClick={() => onSelect(book)}
        onMouseEnter={onActivate}
        onMouseLeave={onDeactivate}
        onFocus={onActivate}
        onBlur={onDeactivate}
        aria-label={`${book.title} by ${book.author || "unknown author"}`}
        className="relative w-full overflow-hidden rounded-t-[3px] transition-transform duration-200 ease-out"
        style={{
          height,
          backgroundColor: color,
          backgroundImage:
            "linear-gradient(90deg, rgba(0,0,0,0.42) 0%, rgba(0,0,0,0.08) 14%, rgba(255,255,255,0.10) 45%, rgba(0,0,0,0.10) 82%, rgba(0,0,0,0.40) 100%)",
          boxShadow: active
            ? "0 14px 20px -6px rgba(0,0,0,0.45)"
            : "0 1px 2px rgba(0,0,0,0.2)",
          transform: active ? `translateY(-${HEADROOM}px)` : "none",
        }}
      >
        <span
          aria-hidden="true"
          className="absolute inset-x-[3px] top-3 h-px bg-white/25"
        />
        <span className="absolute inset-0 flex items-center justify-center px-1 py-4">
          <span
            className="flex max-h-full items-center gap-2 overflow-hidden text-center"
            style={{ writingMode: "vertical-rl" }}
          >
            <span className="truncate text-[11px] font-medium tracking-wide text-white/95">
              {book.title}
            </span>
            {showAuthor && book.author && (
              <span className="truncate text-[9px] text-white/60">
                {book.author}
              </span>
            )}
          </span>
        </span>
      </button>
    </li>
  );
}

export function BookShelfView({
  books,
  loading,
  onSelect,
}: {
  books: Book[];
  loading: boolean;
  onSelect: (book: Book) => void;
}) {
  const [activeId, setActiveId] = useState<number | null>(null);
  const active = books.find((book) => book.id === activeId) ?? null;
  const { ref: sizeRef, height: available } =
    useMeasuredHeight<HTMLElement>();
  const { ref, canScrollLeft, canScrollRight, scrollByPage } = useScrollEdges(
    books.length,
  );

  const shelfHeight = Math.max(
    MIN_BOOKS_HEIGHT,
    Math.min(
      MAX_BOOKS_HEIGHT,
      available - CAPTION_HEIGHT - PLANK_HEIGHT - HEADROOM,
    ),
  );

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const onWheel = (event: WheelEvent) => {
      if (event.deltaX !== 0) return;
      const delta = event.deltaY;
      const atStart = el.scrollLeft <= 1;
      const atEnd = el.scrollLeft + el.clientWidth >= el.scrollWidth - 1;
      if ((delta < 0 && atStart) || (delta > 0 && atEnd)) return;
      event.preventDefault();
      el.scrollLeft += delta;
    };

    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [ref]);

  return (
    <section
      ref={sizeRef}
      className={`flex h-full min-h-0 flex-col justify-end ${
        loading ? "opacity-60 transition-opacity" : ""
      }`}
    >
      <div
        className="flex shrink-0 items-end justify-center px-6 text-center"
        style={{ height: CAPTION_HEIGHT }}
      >
        {active && (
          <p className="truncate text-sm text-ink">
            <span className="font-medium">{active.title}</span>
            {active.author && (
              <span className="text-ink-secondary"> · {active.author}</span>
            )}
          </p>
        )}
      </div>

      <div className="relative shrink-0">
        {canScrollLeft && (
          <ScrollArrow direction="left" onClick={() => scrollByPage(-1)} />
        )}
        {canScrollRight && (
          <ScrollArrow direction="right" onClick={() => scrollByPage(1)} />
        )}

        <div
          ref={ref}
          className="carousel overflow-x-auto overflow-y-hidden"
          style={{ height: shelfHeight + HEADROOM }}
        >
          <div
            className="flex w-max min-w-full px-6 sm:px-10"
            style={{ height: shelfHeight + HEADROOM, paddingTop: HEADROOM }}
          >
            <ul
              className="mx-auto flex h-full w-max items-end"
              style={{ gap: SPINE_GAP }}
            >
              {books.map((book) => (
                <BookSpine
                  key={book.id}
                  book={book}
                  shelfHeight={shelfHeight}
                  active={activeId === book.id}
                  onActivate={() => setActiveId(book.id)}
                  onDeactivate={() => setActiveId(null)}
                  onSelect={onSelect}
                />
              ))}
            </ul>
          </div>
        </div>

        <div className="shelf-plank" aria-hidden="true" />
      </div>
    </section>
  );
}
