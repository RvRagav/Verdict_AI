// Verifiers (Module 2) — bidder × external-authority matrix.

import { useEffect, useState } from 'react';
import {
  ShieldCheck, RefreshCw, ExternalLink, AlertTriangle,
  CheckCircle2, XCircle, HelpCircle, Loader,
} from 'lucide-react';
import { verificationsApi } from '../../api/endpoints';
import type { Tender } from '../../types';
import { Card, CardBody, CardHeader } from '../../components/Card';
import Button from '../../components/Button';
import Pill from '../../components/Pill';
import Drawer from '../../components/Drawer';
import { useToast } from '../../components/Toast';

type MatrixData = Awaited<ReturnType<typeof verificationsApi.matrix>>;

const VERIFIER_LABELS: Record<string, string> = {
  gst: 'GST',
  pan: 'PAN',
  udin: 'UDIN',
  frn: 'FRN (CA)',
  udyam: 'Udyam',
  mca: 'MCA / CIN',
  debarment: 'Debarment',
};

export default function VerifiersView({ tender }: { tender: Tender; onChanged?: () => void }) {
  const [data, setData] = useState<MatrixData | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [activeCell, setActiveCell] = useState<{ bidder: string; verifier: string; result: any } | null>(null);
  const toast = useToast();

  const refresh = () => {
    setLoading(true);
    return verificationsApi.matrix(tender.id).then(setData).finally(() => setLoading(false));
  };
  useEffect(() => { refresh(); }, [tender.id]);

  async function runAll() {
    setRunning(true);
    try {
      const summary = await verificationsApi.run(tender.id);
      toast(
        `Ran ${data?.verifiers.length ?? 7} verifiers across ${summary.bidder_count} bidders.`,
        'success'
      );
      refresh();
    } catch (e) {
      toast((e as Error).message, 'error');
    } finally { setRunning(false); }
  }

  if (loading || !data) return <div className="empty">Loading verifications …</div>;

  const cellMap = new Map<string, any>();
  for (const c of data.cells) cellMap.set(`${c.bidder_id}::${c.verifier_name}`, c);

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader
          title={
            <span className="flex items-center gap-2 font-display">
              <ShieldCheck size={16} className="text-primary" />
              External-source verifiers
            </span>
          }
          subtitle={
            <span>
              Each cell is one independent check against the issuing authority.
              <span className="ml-2 text-warning">
                Most verifiers run in <em>stub mode</em> for the demo — see badge per cell.
              </span>
            </span>
          }
          actions={
            <Button variant="primary" icon={<RefreshCw size={14} />} onClick={runAll} disabled={running}>
              {running ? <><Loader size={14} className="animate-spin" /> Running…</> : 'Run all checks'}
            </Button>
          }
        />
        <CardBody>
          {data.bidders.length === 0 ? (
            <div className="empty">No bidders registered yet — add bidders first.</div>
          ) : (
            <div className="overflow-auto card-flat p-0">
              <table className="min-w-full text-sm border-collapse">
                <thead>
                  <tr className="bg-bg-soft border-b border-line">
                    <th className="text-left px-4 py-2.5 font-semibold text-ink sticky left-0 bg-bg-soft z-10">
                      Bidder
                    </th>
                    {data.verifiers.map(v => (
                      <th key={v} className="text-left px-3 py-2.5 font-semibold text-ink min-w-[120px]">
                        <div>{VERIFIER_LABELS[v] || v}</div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.bidders.map(b => (
                    <tr key={b.id} className="border-b border-line hover:bg-bg-soft">
                      <td className="px-4 py-2.5 align-top sticky left-0 bg-bg z-10 max-w-[260px]">
                        <div className="text-sm font-medium text-ink truncate">{b.company_name}</div>
                      </td>
                      {data.verifiers.map(v => {
                        const cell = cellMap.get(`${b.id}::${v}`);
                        return (
                          <td key={v} className="px-3 py-2.5 align-top">
                            <VerifierCell
                              cell={cell}
                              onClick={() => cell?.result && setActiveCell({ bidder: b.company_name, verifier: v, result: cell.result })}
                            />
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardBody>
      </Card>

      {/* Source-of-truth panel — what does an authority actually return? */}
      {activeCell && (
        <Drawer
          open
          onClose={() => setActiveCell(null)}
          title={`${VERIFIER_LABELS[activeCell.verifier] || activeCell.verifier} — ${activeCell.bidder}`}
          width="min(640px, 90vw)"
        >
          <div className="px-5 py-4 space-y-4">
            <div className="card p-4">
              <div className="section-title mb-1">Verdict</div>
              <div className="flex items-center gap-2 mb-2">
                <StatusPill status={activeCell.result.status} />
                <Pill tone="soft">{activeCell.result.verified_via}</Pill>
                <Pill tone="primary">{Math.round((activeCell.result.confidence ?? 0) * 100)}% conf</Pill>
              </div>
              <div className="text-sm text-ink-muted">{activeCell.result.notes}</div>
            </div>

            <div className="card p-4">
              <div className="section-title mb-2">Source of truth</div>
              <a
                href={activeCell.result.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-primary hover:underline inline-flex items-center gap-1"
              >
                {activeCell.result.source_url}
                <ExternalLink size={12} />
              </a>
              <div className="text-[11px] text-ink-faint mono mt-2">
                snapshot sha256 {activeCell.result.snapshot_sha256?.slice(0, 24)}…
              </div>
            </div>

            <div className="card p-4">
              <div className="section-title mb-2">Authority response (snapshot)</div>
              <pre className="text-[11px] text-ink mono overflow-auto bg-bg-soft p-3 rounded-md border border-line">
                {JSON.stringify(activeCell.result.source_snapshot, null, 2)}
              </pre>
              <div className="text-[11px] text-ink-faint mt-2">
                verified at {new Date(activeCell.result.verified_at).toLocaleString()}
              </div>
            </div>
          </div>
        </Drawer>
      )}
    </div>
  );
}

function VerifierCell({
  cell, onClick,
}: {
  cell: { result: any | null } | undefined;
  onClick: () => void;
}) {
  if (!cell || !cell.result) {
    return (
      <button type="button" className="vc-empty rounded-md w-full px-3 py-2 text-xs" onClick={onClick}>
        not run
      </button>
    );
  }
  const r = cell.result;
  let klass = 'vc-empty';
  let Icon = HelpCircle;
  if (r.status === 'verified') { klass = 'vc-pass'; Icon = CheckCircle2; }
  else if (r.status === 'mismatch') { klass = 'vc-fail'; Icon = XCircle; }
  else if (r.status === 'unreachable') { klass = 'vc-review'; Icon = AlertTriangle; }
  else if (r.status === 'not_found') { klass = 'vc-empty'; Icon = HelpCircle; }

  return (
    <button
      type="button"
      onClick={onClick}
      className={`${klass} rounded-md w-full px-3 py-2 text-xs text-left transition-transform hover:scale-[1.02] hover:shadow-2`}
      title={r.notes}
    >
      <div className="flex items-center justify-between mb-1">
        <span className="flex items-center gap-1 font-bold">
          <Icon size={11} />
          {r.status}
        </span>
        <span className="text-[10px] opacity-70">{r.verified_via}</span>
      </div>
      <div className="text-[10px] opacity-80 line-clamp-2 leading-tight">{r.notes}</div>
    </button>
  );
}

function StatusPill({ status }: { status: string }) {
  const tone = status === 'verified' ? 'success'
    : status === 'mismatch' ? 'danger'
    : status === 'unreachable' ? 'warning'
    : 'soft';
  return <Pill tone={tone as any}>{status}</Pill>;
}
