// Overview — quick state summary + audit trail snapshot + Pre-Mortem Brief.

import { useEffect, useState } from 'react';
import { ShieldCheck, AlertTriangle, History } from 'lucide-react';
import { auditApi, evaluationsApi, biddersApi, criteriaApi, anomaliesApi } from '../../api/endpoints';
import type { AuditEvent, Tender } from '../../types';
import { Card, CardBody, CardHeader } from '../../components/Card';
import Pill from '../../components/Pill';
import PreMortemBrief from '../../components/PreMortemBrief';

export default function OverviewView({ tender }: { tender: Tender; onChanged: () => void }) {
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [verified, setVerified] = useState<{ ok: boolean; error: string | null } | null>(null);
  const [stats, setStats] = useState<{ bidders: number; criteria: number; evals: number; anomalies: number } | null>(null);

  useEffect(() => {
    Promise.all([
      auditApi.trail(tender.id),
      auditApi.verify(tender.id),
      biddersApi.list(tender.id),
      criteriaApi.list(tender.id),
      evaluationsApi.list(tender.id),
      anomaliesApi.list(tender.id),
    ]).then(([trail, verify, bidders, criteria, evals, anomalies]) => {
      setAudit(trail.items.slice(-30).reverse());
      setVerified(verify);
      setStats({
        bidders: bidders.length,
        criteria: criteria.length,
        evals: evals.length,
        anomalies: anomalies.length,
      });
    });
  }, [tender.id]);

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Bidders"     value={stats?.bidders} />
        <StatCard label="Criteria"    value={stats?.criteria} />
        <StatCard label="Evaluations" value={stats?.evals} />
        <StatCard label="Anomalies"   value={stats?.anomalies} tone={(stats?.anomalies ?? 0) > 0 ? 'warning' : 'soft'} />
      </div>

      {/* Pre-Mortem Brief — show only when there is meaningful data */}
      {(stats?.bidders ?? 0) > 0 && (stats?.criteria ?? 0) > 0 && (
        <PreMortemBrief
          tenderId={tender.id}
          onCellOpen={(evalId) => {
            window.location.href = `/tenders/${tender.id}/evaluation?eval=${evalId}`;
          }}
        />
      )}

      <Card>
        <CardHeader
          title={
            <span className="flex items-center gap-2">
              <ShieldCheck size={16} className="text-success" />
              Audit chain
            </span>
          }
          subtitle="Every state change is hash-linked. The chain is verifiable in one click."
          actions={
            verified ? (
              verified.ok
                ? <Pill tone="success">Verified</Pill>
                : <Pill tone="danger">Tampered</Pill>
            ) : null
          }
        />
        <CardBody>
          {verified && !verified.ok && (
            <div className="text-sm text-danger flex items-center gap-2 mb-3">
              <AlertTriangle size={14} /> {verified.error}
            </div>
          )}
          <ul className="divide-y divide-line">
            {audit.map(e => (
              <li key={e.id} className="py-2 flex items-start gap-3 text-sm">
                <History size={14} className="text-ink-soft mt-1" />
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-ink">{e.event_type.replace(/_/g, ' ')}</div>
                  <div className="text-xs text-ink-soft mono truncate" title={e.entry_hash}>
                    {new Date(e.timestamp).toLocaleString()} · {e.actor} · {e.entry_hash.slice(0, 12)}…
                  </div>
                </div>
              </li>
            ))}
            {audit.length === 0 && (
              <li className="py-3 text-sm text-ink-soft">No audit entries yet.</li>
            )}
          </ul>
        </CardBody>
      </Card>
    </div>
  );
}

function StatCard({ label, value, tone = 'primary' }: { label: string; value?: number; tone?: 'primary' | 'soft' | 'warning' }) {
  return (
    <Card>
      <CardBody>
        <div className="text-xs text-ink-soft uppercase tracking-wide">{label}</div>
        <div className="text-2xl font-semibold text-ink mt-1">
          {value ?? <span className="skeleton inline-block w-12 h-7" />}
        </div>
        <div className="mt-2">
          <Pill tone={tone as any}>recorded</Pill>
        </div>
      </CardBody>
    </Card>
  );
}
