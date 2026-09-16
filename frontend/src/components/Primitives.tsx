
import type { ReactNode } from "react";

export function Card({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`rounded-xl border border-hairline bg-surface ${className}`}
    >
      {children}
    </section>
  );
}

export function Button({
  children,
  variant = "secondary",
  className = "",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
}) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-lg px-3 py-1.5 text-[11px] font-light tracking-wide transition disabled:cursor-not-allowed disabled:opacity-50";
  const variants = {
    primary:
      "bg-accent text-accent-contrast hover:bg-accent-strong",
    secondary:
      "border border-hairline bg-surface text-ink hover:bg-surface-2",
    ghost: "text-ink-secondary hover:bg-surface-2 hover:text-ink",
    danger: "border border-hairline text-critical hover:bg-surface-2",
  } as const;

  return (
    <button className={`${base} ${variants[variant]} ${className}`} {...props}>
      {children}
    </button>
  );
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-[11px] font-light tracking-wide text-ink-secondary">
        {label}
      </span>
      {children}
      {hint && <span className="text-[10px] text-ink-muted">{hint}</span>}
    </label>
  );
}

export const inputClass =
  "w-full rounded-lg border border-hairline bg-surface px-3 py-1.5 text-xs font-light text-ink placeholder:text-ink-muted focus:border-accent focus:outline-none";

export function Spinner({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-xs font-light text-ink-secondary">
      <span
        aria-hidden="true"
        className="size-3.5 animate-spin rounded-full border-2 border-accent border-t-transparent"
      />
      {label}
    </span>
  );
}

export function EmptyState({
  title,
  body,
  action,
}: {
  title: string;
  body: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-hairline bg-surface px-6 py-16 text-center">
      <span aria-hidden="true" className="text-3xl">
        📚
      </span>
      <h3 className="text-sm font-medium text-ink">{title}</h3>
      <p className="max-w-md text-xs font-light text-ink-secondary">{body}</p>
      {action}
    </div>
  );
}
