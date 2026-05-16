// Officer picker — header dropdown. Sets the X-Officer-ID header for all
// subsequent API calls. Real FK to the officers table. No password
// because in govt-procurement context officers log in via SSO; this is
// the lightweight shim that proves the audit trail is real.

import { useEffect, useState } from 'react';
import { ChevronDown, UserCircle2 } from 'lucide-react';
import { officersApi } from '../api/endpoints';
import { getOfficer, setOfficer } from '../api/client';
import type { Officer } from '../types';
import Tooltip from './Tooltip';

export default function OfficerPicker() {
  const [open, setOpen] = useState(false);
  const [officers, setOfficers] = useState<Officer[]>([]);
  const [active, setActive] = useState<Officer | null>(null);

  useEffect(() => {
    officersApi.list().then(list => {
      setOfficers(list);
      const id = getOfficer();
      const found = list.find(o => o.id === id) || list[0];
      if (found) {
        setOfficer(found.id);
        setActive(found);
      }
    });
  }, []);

  if (!active) return null;

  return (
    <div className="relative">
      <Tooltip label="Switch acting officer">
        <button
          className="btn btn-ghost btn-sm"
          onClick={() => setOpen(o => !o)}
          aria-haspopup="listbox"
          aria-expanded={open}
        >
          <UserCircle2 size={16} />
          <span className="hidden sm:inline">{active.name}</span>
          <span className="text-ink-soft">·</span>
          <span className="text-ink-soft">{active.role}</span>
          <ChevronDown size={14} />
        </button>
      </Tooltip>
      {open && (
        <div
          className="card absolute right-0 mt-2 w-[280px] z-50 p-1"
          onMouseLeave={() => setOpen(false)}
          role="listbox"
        >
          {officers.map(o => (
            <button
              key={o.id}
              className={`w-full text-left p-3 rounded-md hover:bg-bg-sunk ${o.id === active.id ? 'bg-bg-tint' : ''}`}
              onClick={() => {
                setOfficer(o.id);
                setActive(o);
                setOpen(false);
                // Force-refresh the page so officer-scoped data reloads
                window.location.reload();
              }}
              role="option"
              aria-selected={o.id === active.id}
            >
              <div className="text-sm font-semibold text-ink">{o.name}</div>
              <div className="text-xs text-ink-soft">{o.department} · {o.role}</div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
