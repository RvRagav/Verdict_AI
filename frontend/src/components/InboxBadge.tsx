// Small badge showing how many concurrence requests await the current officer.

import { useEffect, useState } from 'react';
import { concurrenceApi } from '../api/endpoints';
import { getOfficer } from '../api/client';

export default function InboxBadge() {
  const [count, setCount] = useState<number | null>(null);

  useEffect(() => {
    let active = true;
    const tick = async () => {
      try {
        const items = await concurrenceApi.inbox('open');
        if (!active) return;
        setCount(items.length);
      } catch {
        if (active) setCount(null);
      }
    };
    tick();
    const id = window.setInterval(tick, 30_000);
    // Tick on officer switch
    const onStorage = (e: StorageEvent) => {
      if (e.key === 'verdictai.officer') tick();
    };
    window.addEventListener('storage', onStorage);
    // Touch officer to ensure currentOfficerId is hydrated
    void getOfficer();
    return () => {
      active = false;
      window.clearInterval(id);
      window.removeEventListener('storage', onStorage);
    };
  }, []);

  if (count === null || count === 0) return null;
  return (
    <span
      className="ml-auto inline-flex items-center justify-center h-5 min-w-5 px-1 text-[11px] font-bold rounded-full bg-warning text-ink-on"
      aria-label={`${count} pending concurrence request${count === 1 ? '' : 's'}`}
    >
      {count}
    </span>
  );
}
