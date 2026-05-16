// Evaluation step — the matrix + smell-test chips + drawer.

import { useEffect, useState } from 'react';
import { AlertTriangle, ShieldAlert, RefreshCcw, Sparkles, ArrowRight } from 'lucide-react';
import { evaluationsApi, anomaliesApi } from '../../api/endpoints';
import type { Matrix, AnomalyFlag, Tender, MatrixCell } from '../../types';
import { Card, CardBody, CardHeader } from '../../components/Card';
import Button from '../../components/Button';
import Pill from '../../components/Pill';
import MatrixView from '../../components/Matrix';
import EvaluationDrawer from '../../components/EvaluationDrawer';
import BidderRadar from '../../components/BidderRadar';
import RiskHeatmap from '../../components/RiskHeatmap';
import LiveEvalStream from '../../components/LiveEvalStream';
import Tooltip from '../../components/Tooltip';
import { useToast } from '../../components/Toast';

type Props = { tender: Tender; onChanged?: () => void };

export default function EvaluationView({ tender }: Props) {
  const [matrix, setMatrix] = useState<Matrix | null>(null);
  const [anomalies, setAnomalies] = useState<AnomalyFlag[]>([]);
  const [activeEval, setActiveEval] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const toast = useToast();

  const refresh = () => Promise.all([
    evaluationsApi.matrix(tender.id),
    anomaliesApi.list(tender.id, 'open'),
  ]).then(([m, a]) => { setMatrix(m); setAnomalies(a); });

  useEffect(() => { refresh(); }, [tender.id]);

  async function rerun() {
    setBusy(true);
    try {
      const summary = await evaluationsApi.run(tender.id);
      toast(`Evaluation complete: ${summary.total_cells} cells, ${summary.hitl_review + summary.mandatory_review} need review.`, 'success');
      refresh();
    } catch (e) {
      toast((e as Error).message, 'error');
    } finally { setBusy(false); }
  }

  const reviewable = matrix?.cells.filter(c =>
    c.evaluation_id && (c.route === 'mandatory_review' || c.route === 'hitl_review')) ?? [];

  const anomalyByBidder = new Map<string, AnomalyFlag[]>();
  for (const a of anomalies) {
    const bid = (a.evidence_data as { bidder_ids?: string[] } | undefined)?.bidder_ids?.[0]
      ?? (a as { bidder_id?: string }).bidder_id ?? 'unknown';
    if (!anomalyByBidder.has(bid)) anomalyByBidder.set(bid, []);
    anomalyByBidder.get(bid)!.push(a);
  }

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader
          title={
            <span className="flex items-center gap-2">
              <Sparkles size={16} className="text-primary" />
              Evaluation matrix
            </span>
          }
          subtitle="Each cell is the AI's *suggested* verdict — click any cell to see the evidence."
          actions={
            <div className="flex items-center gap-2">
              <LiveEvalStream tenderId={tender.id} onComplete={refresh} />
              <Tooltip label="Re-run evaluation (reuses cache)">
                <Button variant="ghost" icon={<RefreshCcw size={14} />} onClick={rerun} disabled={busy}>
                  {busy ? 'Running…' : 'Re-run'}
                </Button>
              </Tooltip>
              {reviewable.length === 0 && (matrix?.cells.length ?? 0) > 0 && (
                <Button
                  variant="primary"
                  icon={<ArrowRight size={14} />}
                  onClick={() => window.location.href = `/tenders/${tender.id}/report`}
                >
                  Continue to report
                </Button>
              )}
            </div>
          }
        />
        <CardBody>
          <div className="flex flex-wrap items-center gap-3 mb-4">
            <Stat label="Total cells" value={matrix?.cells.length ?? 0} />
            <Stat label="High confidence" value={matrix?.cells.filter(c => c.route === 'auto_commit').length ?? 0} tone="soft" />
            <Stat label="Officer review" value={matrix?.cells.filter(c => c.route === 'hitl_review').length ?? 0} tone="warning" />
            <Stat label="Mandatory review" value={matrix?.cells.filter(c => c.route === 'mandatory_review').length ?? 0} tone="danger" />
          </div>
          {matrix && <MatrixView data={matrix} onCellClick={(c: MatrixCell) => c.evaluation_id && setActiveEval(c.evaluation_id)} />}
        </CardBody>
      </Card>

      {/* Bidder Comparison Radar + Risk Heatmap */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
        <BidderRadar tenderId={tender.id} />
        <RiskHeatmap tenderId={tender.id} />
      </div>

      {/* Smell test panel */}
      {anomalies.length > 0 && (
        <Card>
          <CardHeader
            title={
              <span className="flex items-center gap-2 font-display">
                <ShieldAlert size={16} className="text-warning" />
                Cross-bidder signals
              </span>
            }
            subtitle={`${anomalies.length} signal${anomalies.length === 1 ? '' : 's'} flagged across the bidder set.`}
          />
          <CardBody className="space-y-2">
            {anomalies.slice(0, 12).map(a => (
              <div key={a.id} className="flex items-start gap-3 text-sm border border-line rounded-md p-3">
                <AlertTriangle
                  size={14}
                  className={
                    a.severity === 'high' ? 'text-danger'
                    : a.severity === 'medium' ? 'text-warning'
                    : 'text-ink-soft'
                  }
                />
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-ink">{a.flag_type.replace(/_/g, ' ')}</div>
                  <div className="text-xs text-ink-muted">{a.message}</div>
                </div>
                <Pill tone={
                  a.severity === 'high' ? 'danger'
                  : a.severity === 'medium' ? 'warning'
                  : 'soft'
                }>
                  {a.severity}
                </Pill>
              </div>
            ))}
          </CardBody>
        </Card>
      )}

      <EvaluationDrawer
        evaluationId={activeEval}
        onClose={() => setActiveEval(null)}
        onChanged={refresh}
      />
    </div>
  );
}

function Stat({ label, value, tone = 'primary' }: { label: string; value: number; tone?: 'primary' | 'soft' | 'warning' | 'danger' }) {
  return (
    <div className="flex items-baseline gap-2">
      <span className="text-2xl font-bold text-ink">{value}</span>
      <Pill tone={tone}>{label}</Pill>
    </div>
  );
}
