import { useEffect } from "react";

export type ToastTone = "success" | "error" | "info";

export interface ToastMessage {
  id: number;
  tone: ToastTone;
  text: string;
}

const TONE_STYLES: Record<ToastTone, { color: string; icon: string }> = {
  success: { color: "var(--good)", icon: "✓" },
  error: { color: "var(--critical)", icon: "!" },
  info: { color: "var(--accent)", icon: "i" },
};

export function Toast({
  message,
  onDismiss,
}: {
  message: ToastMessage;
  onDismiss: (id: number) => void;
}) {
  useEffect(() => {
    const timer = window.setTimeout(() => onDismiss(message.id), 6000);
    return () => window.clearTimeout(timer);
  }, [message.id, onDismiss]);

  const tone = TONE_STYLES[message.tone];

  return (
    <div
      role="status"
      className="flex items-start gap-3 rounded-lg border border-hairline bg-surface px-4 py-3 shadow-lg"
      style={{ borderLeft: `3px solid ${tone.color}` }}
    >
      <span
        aria-hidden="true"
        className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full text-xs font-bold"
        style={{ backgroundColor: tone.color, color: "var(--surface-1)" }}
      >
        {tone.icon}
      </span>
      <p className="flex-1 text-xs font-light text-ink">{message.text}</p>
      <button
        type="button"
        onClick={() => onDismiss(message.id)}
        aria-label="Dismiss notification"
        className="text-ink-muted transition hover:text-ink"
      >
        ✕
      </button>
    </div>
  );
}

export function ToastStack({
  messages,
  onDismiss,
}: {
  messages: ToastMessage[];
  onDismiss: (id: number) => void;
}) {
  if (messages.length === 0) return null;
  return (
    <div
      aria-live="polite"
      className="fixed bottom-4 right-4 z-50 flex w-[min(24rem,calc(100vw-2rem))] flex-col gap-2"
    >
      {messages.map((message) => (
        <Toast key={message.id} message={message} onDismiss={onDismiss} />
      ))}
    </div>
  );
}
