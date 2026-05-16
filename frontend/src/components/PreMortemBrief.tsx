// Pre-Mortem Brief — the 90-second TEC briefing rendered on Tender Space.

import { useEffect, useState } from 'react';
import { Sparkles, RefreshCw, ShieldAlert, Trophy, Frown } from 'lucide-react';
import { briefApi } from '../api/endpoints';
import type { Brief } from '../types';
import { Card, CardBody, CardHeader } from './Card';
import Pill from './Pill';
import Button from './Button';

export default function PreMortemBrief({
  tenderId,
  onCellOpen,
}: {
  tenderId: string;
  onCellOpen?: (evaluationId: string) => void;
}) {
  const [brief, setBrief] = useState<Brief | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setBusy(true);
    briefApi.get(tenderId)
      .then(setBrief)
      .catch(e => setError((e as Error).message))
      .finally(() => setBusy(false));
  }, [tenderId]);

  async function regenerate() {
    setBusy(true);
    try {
      const fresh = await briefApi.regenerate(tenderId);
      setBrief(fresh);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (error) {
    return (
      <Card>
        <CardBody>
          <div className="text-sm text-danger">Brief unavailable: {error}</div>
        </CardBody>
      </Card>
    );
  }
  if (busy && !brief) {
    return (
      <Card>
        <CardBody>
          <div className="flex items-center gap-2 text-sm text-ink-soft">
            <Sparkles size={14} className="animate-pulse text-primary" />
            Reading the tender…
          </div>
        </CardBody>
      </Card>
    );
  }
  if (!brief) return null;
  const b = brief.brief;

  return (
    <Card className="card-pop">
      <CardHeader
        title={
          <span className="flex items-center gap-2 font-display">
            <Sparkles size={16} className="text-primary" />
            Pre-Mortem Brief
          </span>
        }
        subtitle="A 90-second briefing before you open the matrix. Decision-support, not decision-making."
        actions={
          <Button variant="ghost" size="sm" icon={<RefreshCw size={12} />} onClick={regenerate} disabled={busy}>
            {busy ? 'Refreshing…' : 'Refresh'}
          </Button>
        }
      />
      <CardBody className="space-y-4">
        <div>
          <div className="section-title mb-1">① Lay of the land</div>
          <div className="text-sm text-ink">{b.lay_of_land}</div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {b.strongest_bidder && (
            <div className="border border-success rounded-md bg-success-soft p-3">
              <div className="flex items-center gap-2 text-xs text-success-hover font-bold uppercase tracking-wide">
                <Trophy size={12} /> Strongest
              </div>
              <div className="text-sm font-semibold text-ink mt-1">{b.strongest_bidder.name}</div>
              <div className="text-xs text-ink-muted">{b.strongest_bidder.reason}</div>
            </div>
          )}
          {b.weakest_bidder && (
            <div className="border border-danger rounded-md bg-danger-soft p-3">
              <div className="flex items-center gap-2 text-xs text-danger-hover font-bold uppercase tracking-wide">
                <Frown size={12} /> Weakest
              </div>
              <div className="text-sm font-semibold text-ink mt-1">{b.weakest_bidder.name}</div>
              <div className="text-xs text-ink-muted">{b.weakest_bidder.reason}</div>
            </div>
          )}
        </div>

        {b.hitl_items?.length > 0 && (
          <div>
            <div className="section-title mb-1">④ Where you'll think hardest</div>
            <ul className="space-y-1">
              {b.hitl_items.slice(0, 6).map((item, i) => (
                <li key={i} className="flex items-start gap-2 text-sm">
                  <span className="text-ink-faint">•</span>
                  <button
                    className={`text-left ${item.evaluation_id ? 'text-primary hover:underline cursor-pointer' : 'text-ink'}`}
                    onClick={() => item.evaluation_id && onCellOpen?.(item.evaluation_id)}
                    disabled={!item.evaluation_id}
                  >
                    <span className="font-medium">{item.label}</span>
                    {item.why && <span className="text-ink-soft"> — {item.why}</span>}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {b.premortem_risks?.length > 0 && (
          <div>
            <div className="section-title mb-1 flex items-center gap-1.5">
              <ShieldAlert size={11} className="text-warning" /> ⑤ What might bite you later
            </div>
            <ul className="space-y-1.5">
              {b.premortem_risks.slice(0, 6).map((r, i) => (
                <li key={i} className="flex items-start gap-2 text-sm">
                  <Pill tone={r.severity === 'high' ? 'danger' : r.severity === 'medium' ? 'warning' : 'soft'}>
                    {r.severity}
                  </Pill>
                  <div>
                    <span className="font-medium text-ink">{r.label}</span>
                    <span className="text-ink-muted"> — {r.evidence}</span>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="text-[11px] text-ink-faint mono pt-2 border-t border-dashed border-line">
          pipeline {brief.pipeline_signature_hash} · generated {new Date(brief.generated_at).toLocaleString()}
        </div>
      </CardBody>
    </Card>
  );
}
