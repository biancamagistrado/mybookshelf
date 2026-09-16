import type { Stats } from "../types";
import { compactNumber, pluralize } from "../lib/format";
import { BarList, ChartFrame, ColumnChart, DataTable } from "./charts";
import { EmptyState } from "./Primitives";

function StatTile({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="rounded-xl border border-hairline bg-surface px-4 py-3">
      <dt className="text-[11px] font-light tracking-wide text-ink-secondary">{label}</dt>
      <dd className="mt-1 text-xl font-medium text-ink">{value}</dd>
      {hint && <p className="mt-0.5 text-[10px] text-ink-muted">{hint}</p>}
    </div>
  );
}

export function StatsView({ stats }: { stats: Stats | null }) {
  if (!stats) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }, (_, index) => (
          <div
            key={index}
            className="h-24 animate-pulse rounded-xl border border-hairline bg-surface"
          />
        ))}
      </div>
    );
  }

  if (stats.total_books === 0) {
    return (
      <EmptyState
        title="No reading stats yet"
        body="Import your library export or add a book by hand, and your reading year will start taking shape here."
      />
    );
  }

  const thisYear = new Date().getFullYear();
  const hasReadDates = stats.books_per_year.length > 0;

  return (
    <div className="flex flex-col gap-6">
      <section className="rounded-xl border border-hairline bg-surface px-6 py-6">
        {hasReadDates ? (
          <>
            <p className="text-[11px] font-light tracking-wide text-ink-secondary">
              Books finished in {thisYear}
            </p>
            <p className="mt-1 text-4xl font-medium leading-none text-ink">
              {stats.books_read_this_year.toLocaleString()}
            </p>
            <p className="mt-2 text-[11px] font-light text-ink-secondary">
              {stats.books_read.toLocaleString()}{" "}
              {pluralize(stats.books_read, "book")} read all time ·{" "}
              {compactNumber(stats.pages_read)} pages
            </p>
          </>
        ) : (
          <>
            <p className="text-[11px] font-light tracking-wide text-ink-secondary">
              Books read
            </p>
            <p className="mt-1 text-4xl font-medium leading-none text-ink">
              {stats.books_read.toLocaleString()}
            </p>
            <p className="mt-2 text-[11px] font-light text-ink-secondary">
              {compactNumber(stats.pages_read)} pages · add finish dates to
              your books to see a year-by-year breakdown
            </p>
          </>
        )}
      </section>

      <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile
          label="Total books"
          value={compactNumber(stats.total_books)}
          hint="Across every shelf"
        />
        <StatTile
          label="Currently reading"
          value={compactNumber(stats.currently_reading)}
        />
        <StatTile label="Want to read" value={compactNumber(stats.to_read)} />
      </dl>

      <div className="grid gap-4 lg:grid-cols-2">
        {stats.books_per_year.length > 0 && (
          <ChartFrame
            title="Books finished per year"
            subtitle="Counted by the date you marked each book read"
            table={
              <DataTable
                columns={["Year", "Books"]}
                rows={stats.books_per_year.map((row) => ({
                  label: String(row.year),
                  value: row.count,
                }))}
              />
            }
          >
            <ColumnChart
              unit="books"
              items={stats.books_per_year.map((row) => ({
                label: String(row.year),
                value: row.count,
              }))}
            />
          </ChartFrame>
        )}

        <ChartFrame
          title="Top genres"
          subtitle="From Google Books / Open Library lookups"
          table={
            <DataTable
              columns={["Genre", "Books"]}
              rows={stats.top_genres.map((row) => ({
                label: row.name,
                value: row.count,
              }))}
            />
          }
        >
          {stats.top_genres.length > 0 ? (
            <BarList
              unit="books"
              items={stats.top_genres.map((row) => ({
                label: row.name,
                value: row.count,
              }))}
            />
          ) : (
            <p className="py-8 text-center text-xs font-light text-ink-secondary">
              No genres yet.
            </p>
          )}
        </ChartFrame>

        <ChartFrame
          title="Most-read authors"
          table={
            <DataTable
              columns={["Author", "Books"]}
              rows={stats.top_authors.map((row) => ({
                label: row.name,
                value: row.count,
              }))}
            />
          }
        >
          <BarList
            unit="books"
            items={stats.top_authors.map((row) => ({
              label: row.name,
              value: row.count,
            }))}
          />
        </ChartFrame>
      </div>
    </div>
  );
}
