
import { useState, type ReactNode } from "react";

function niceMax(value: number): number {
  if (value <= 0) return 1;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const normalised = value / magnitude;
  const step = normalised <= 1 ? 1 : normalised <= 2 ? 2 : normalised <= 5 ? 5 : 10;
  return step * magnitude;
}

export function ChartFrame({
  title,
  subtitle,
  children,
  table,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  table: ReactNode;
}) {
  const [showTable, setShowTable] = useState(false);

  return (
    <figure className="m-0 rounded-xl border border-hairline bg-surface p-5">
      <figcaption className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h3 className="text-xs font-medium text-ink">{title}</h3>
          {subtitle && (
            <p className="mt-0.5 text-[11px] font-light text-ink-secondary">{subtitle}</p>
          )}
        </div>
        <button
          type="button"
          onClick={() => setShowTable((current) => !current)}
          aria-expanded={showTable}
          className="shrink-0 rounded-md px-2 py-1 text-[11px] font-light text-ink-secondary hover:bg-surface-2 hover:text-ink"
        >
          {showTable ? "Show chart" : "Show table"}
        </button>
      </figcaption>
      {showTable ? table : children}
    </figure>
  );
}

export function DataTable({
  columns,
  rows,
}: {
  columns: [string, string];
  rows: { label: string; value: number }[];
}) {
  return (
    <div className="max-h-72 overflow-y-auto">
      <table className="w-full text-xs font-light">
        <thead className="sticky top-0 bg-surface">
          <tr className="border-b border-hairline text-left text-xs text-ink-secondary">
            <th scope="col" className="py-2 pr-4 font-medium">
              {columns[0]}
            </th>
            <th scope="col" className="py-2 text-right font-medium">
              {columns[1]}
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label} className="border-b border-hairline last:border-0">
              <th scope="row" className="py-2 pr-4 font-normal text-ink">
                {row.label}
              </th>
              <td className="py-2 text-right tabular-nums text-ink-secondary">
                {row.value.toLocaleString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function BarList({
  items,
  unit,
}: {
  items: { label: string; value: number }[];
  unit: string;
}) {
  const max = Math.max(...items.map((item) => item.value), 1);

  return (
    <ul className="flex flex-col gap-[2px]">
      {items.map((item) => (
        <li key={item.label} className="group grid grid-cols-[minmax(0,9rem)_1fr] items-center gap-3 py-1">
          <span
            className="truncate text-xs text-ink-secondary"
            title={item.label}
          >
            {item.label}
          </span>
          <span className="flex items-center gap-2">
            <span
              className="h-3 rounded-r-[4px] transition-[width]"
              style={{
                width: `${Math.max((item.value / max) * 100, 2)}%`,
                backgroundColor: "var(--accent)",
              }}
              title={`${item.label}: ${item.value.toLocaleString()} ${unit}`}
            />
            <span className="shrink-0 text-xs tabular-nums text-ink-secondary">
              {item.value.toLocaleString()}
            </span>
          </span>
        </li>
      ))}
    </ul>
  );
}

export function ColumnChart({
  items,
  unit,
}: {
  items: { label: string; value: number }[];
  unit: string;
}) {
  const [hovered, setHovered] = useState<number | null>(null);
  const max = niceMax(Math.max(...items.map((item) => item.value), 1));
  const ticks = [max, Math.round(max / 2), 0];

  return (
    <div className="relative">
      <div className="flex gap-3">
        <div
          aria-hidden="true"
          className="flex w-8 shrink-0 flex-col justify-between py-0 text-right text-[10px] tabular-nums text-ink-muted"
          style={{ height: "10rem" }}
        >
          {ticks.map((tick) => (
            <span key={tick} className="leading-none">
              {tick.toLocaleString()}
            </span>
          ))}
        </div>

        <div className="relative flex-1">
          <div aria-hidden="true" className="absolute inset-0 flex flex-col justify-between">
            {ticks.map((tick) => (
              <div key={tick} className="h-px w-full bg-grid" />
            ))}
          </div>

          <ol
            className="relative flex h-40 items-end gap-[2px]"
            style={{ margin: 0, padding: 0 }}
          >
            {items.map((item, index) => {
              const active = hovered === index;
              return (
                <li
                  key={item.label}
                  className="flex h-full flex-1 items-end justify-center"
                  onMouseEnter={() => setHovered(index)}
                  onMouseLeave={() => setHovered(null)}
                  onFocus={() => setHovered(index)}
                  onBlur={() => setHovered(null)}
                >
                  <button
                    type="button"
                    aria-label={`${item.label}: ${item.value.toLocaleString()} ${unit}`}
                    className="flex h-full w-full max-w-6 items-end justify-center"
                  >
                    <span
                      className="w-full rounded-t-[4px] transition-[height,opacity]"
                      style={{
                        height: `${Math.max((item.value / max) * 100, 1.5)}%`,
                        backgroundColor: "var(--accent)",
                        opacity: hovered === null || active ? 1 : 0.55,
                      }}
                    />
                  </button>
                </li>
              );
            })}
          </ol>
        </div>
      </div>

      <div className="mt-2 flex gap-3">
        <div className="w-8 shrink-0" />
        <ol className="flex flex-1 gap-[2px]">
          {items.map((item) => (
            <li
              key={item.label}
              className="min-w-0 flex-1 truncate text-center text-[10px] tabular-nums text-ink-muted"
            >
              {item.label}
            </li>
          ))}
        </ol>
      </div>

      {hovered !== null && (
        <div
          role="tooltip"
          className="pointer-events-none absolute -top-2 left-1/2 -translate-x-1/2 -translate-y-full whitespace-nowrap rounded-md border border-hairline bg-surface px-2 py-1 text-xs text-ink shadow-md"
        >
          <span className="font-medium">{items[hovered].label}</span>
          <span className="text-ink-secondary">
            {" "}
            · {items[hovered].value.toLocaleString()} {unit}
          </span>
        </div>
      )}
    </div>
  );
}
