// Tiny global toast hook.

import { createContext, useCallback, useContext, useState, ReactNode } from 'react';

type Toast = { id: number; message: string; tone?: 'info' | 'success' | 'error' };

const ToastCtx = createContext<{ push: (m: string, t?: Toast['tone']) => void } | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const push = useCallback((message: string, tone: Toast['tone'] = 'info') => {
    const id = Date.now() + Math.random();
    setToasts(prev => [...prev, { id, message, tone }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 3500);
  }, []);
  return (
    <ToastCtx.Provider value={{ push }}>
      {children}
      <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2">
        {toasts.map(t => (
          <div
            key={t.id}
            className="toast"
            style={{
              background:
                t.tone === 'error' ? 'var(--danger)' :
                t.tone === 'success' ? 'var(--success)' : 'var(--ink)',
            }}
            role="status"
            aria-live="polite"
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastCtx);
  if (!ctx) throw new Error('useToast must be used inside ToastProvider');
  return ctx.push;
}
