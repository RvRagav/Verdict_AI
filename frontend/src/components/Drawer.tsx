// Slide-in side drawer. Closes on overlay click + Escape.

import { ReactNode, useEffect } from 'react';
import { X } from 'lucide-react';

export default function Drawer({
  open,
  onClose,
  title,
  children,
  width = 'min(720px, 90vw)',
}: {
  open: boolean;
  onClose: () => void;
  title?: ReactNode;
  children: ReactNode;
  width?: string;
}) {
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <>
      <div className="drawer-overlay" onClick={onClose} aria-hidden />
      <aside className="drawer" style={{ width }} role="dialog" aria-modal="true">
        <header className="px-5 py-2.5 border-b border-line flex items-center justify-between flex-shrink-0">
          <div className="text-md font-semibold text-ink">{title}</div>
          <button
            type="button"
            onClick={onClose}
            className="btn btn-ghost btn-sm"
            aria-label="Close"
            title="Close"
          >
            <X size={16} />
          </button>
        </header>
        <div className="flex-1 min-h-0 overflow-y-auto">{children}</div>
      </aside>
    </>
  );
}
