// Audit tab — hash-linked event log + verify chain action + time-travel replay.

import { useEffect, useState } from 'react';
import { ShieldCheck, History, RefreshCw, AlertTriangle } from 'lucide-react';
import { auditApi } from '../../api/endpoints';
import type { AuditEvent, Tender } from '../../types';
import { Card, CardBody, CardHeader } from '../../components/Card';
import Pill from '../../components/Pill';
import Button from '../../components/Button';
import AuditReplay from '../../components/AuditReplay';

export default function AuditView({ tender }: { tender: Tender; onChanged?: () => void }) {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [verified, setVerified] = useState<{ ok: boolean; error: string | null } | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = () => {
    setLoading(true);
    return Promise.all([
      auditApi.trail(tender.id),
      auditApi.verify(tender.id),
    ]).then(([t, v]) => {
      setEvents(t.items.slice().reverse());
      setVerified(v);
    }).finally(() => setLoading(false));
  };

  useEffect(() => { refresh(); }, [tender.id]);

  return (
    <div className="space-y-5">
      {/* Audit Replay — Time Travel */}
      <AuditReplay tenderId={tender.id} />

      <Card>
        <CardHeader
          title={
            <span className="flex items-center gap-2 font-display">
              <ShieldCheck size={16} className="text-success" />
              Audit chain
            </span>
          }
          subtitle="Append-only hash-linked log. UPDATE/DELETE blocked at the database level."
          actions={
            <div className="flex items-center gap-2">
              {verified && (
                verified.ok
                  ? <Pill tone="success">verified</Pill>
                  : <Pill tone="danger">tampered</Pill>
              )}
              <Button variant="ghost" size="sm" icon={<RefreshCw size={12} />} onClick={refresh} disabled={loading}>
                {loading ? 'Verifying…' : 'Re-verify'}
              </Button>
            </div>
          }
        />
        <CardBody>
          {verified && !verified.ok && (
            <div className="text-sm text-danger flex items-center gap-2 mb-3">
              <AlertTriangle size={14} /> {verified.error}
            </div>
          )}
          {verified?.ok && (
            <div className="text-sm text-ink-soft mb-3">
              Walked {events.length} event{events.length === 1 ? '' : 's'}.
              Every prev-hash matches; every entry-hash recomputes. Chain is intact.
            </div>
          )}

          <ul className="divide-y divide-line">
            {events.slice(0, 200).map(e => (
              <li key={e.id} className="py-2 flex items-start gap-3 text-sm">
                <History size={13} className="text-ink-soft mt-1" />
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-ink">{e.event_type.replace(/_/g, ' ')}</div>
                  <div className="text-xs text-ink-soft mono truncate" title={e.entry_hash}>
                    {new Date(e.timestamp).toLocaleString()} · {e.actor} · {e.entry_hash.slice(0, 16)}…
                  </div>
                </div>
              </li>
            ))}
            {events.length === 0 && (
              <li className="py-3 text-sm text-ink-soft">No audit entries yet.</li>
            )}
          </ul>
        </CardBody>
      </Card>
    </div>
  );
}
