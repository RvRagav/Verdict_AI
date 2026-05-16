// Evaluation detail panel — the big drawer.
// Confidence Veil headline + Mosaic + Dissent + Source pill + Decide.

import { useEffect, useState } from 'react';
import { CheckCircle2, RotateCcw, ShieldAlert, Sparkles, XCircle } from 'lucide-react';
import { evaluationsApi } from '../api/endpoints';
import { useToast } from './Toast';
import Drawer from './Drawer';
import Pill from './Pill';
import Button from './Button';
import ConfidenceMosaic from './ConfidenceMosaic';
import SourcePill, { SourceRef } from './SourcePill';
import PDFViewer from './PDFViewer';
import CommentThread from './CommentThread';
import EvidenceGraph from './EvidenceGraph';
import WhatIfPreview from './WhatIfPreview';
import TenderDNA from './TenderDNA';
import type { Evaluation } from '../types';

type Props = {
  evaluationId: string | null;
  onClose: () => void;
  onChanged?: () => void;
};

export default function EvaluationDrawer({ evaluationId, onClose, onChanged }: Props) {
  const [evalu, setEvalu] = useState<Evaluation | null>(null);
  const [loading, setLoading] = useState(false);
  const [overrideMode, setOverrideMode] = useState(false);
  const [overrideVerdict, setOverrideVerdict] = useState<'PASS'|'FAIL'|'REVIEW'>('PASS');
  const [reasonText, setReasonText] = useState('');
  const [saving, setSaving] = useState(false);
  const [sourceOpen, setSourceOpen] = useState<SourceRef | null>(null);
  const toast = useToast();

  useEffect(() => {
    if (!evaluationId) return;
    setLoading(true);
    evaluationsApi.get(evaluationId).then(e => {
      setEvalu(e);
      setLoading(false);
    });
  }, [evaluationId]);

  if (!evaluationId) return null;

  return (
    <>
      <Drawer
        open={Boolean(evaluationId)}
        onClose={onClose}
        title={evalu ? 'Evaluation detail' : 'Loading…'}
        width="min(820px, 92vw)"
      >
        {loading || !evalu ? (
          <div className="empty">Loading evaluation …</div>
        ) : (
          <div className="px-5 py-4 space-y-5">
            {/* Confidence Veil headline */}
            <div className="card p-4">
              <div className="flex items-center gap-2 text-xs text-ink-soft uppercase tracking-wide mb-2">
                <Sparkles size={12} className="text-primary" />
                What the AI sees
              </div>
              <div className="text-lg font-semibold text-ink leading-snug">
                {evalu.explanation?.headline ?? 'No headline available.'}
              </div>
              {evalu.explanation?.detail && (
                <div className="text-sm text-ink-muted mt-2">{evalu.explanation.detail}</div>
              )}
              <div className="mt-3 flex items-center gap-2 flex-wrap">
                <Pill tone={
                  evalu.verdict === 'PASS' ? 'success'
                  : evalu.verdict === 'FAIL' ? 'danger'
                  : 'warning'
                }>
                  AI suggests: {evalu.verdict}
                </Pill>
                <Pill tone="primary">{Math.round(evalu.confidence * 100)}% confident</Pill>
                <Pill tone={evalu.route === 'mandatory_review' ? 'danger' : (evalu.route === 'hitl_review' ? 'warning' : 'soft')}>
                  Route: {evalu.route.replace('_', ' ')}
                </Pill>
                {evalu.source_doc_id && evalu.source_page && (
                  <SourcePill
                    source={{
                      doc_id: evalu.source_doc_id,
                      page: evalu.source_page,
                      bbox: evalu.source_bbox || null,
                      label: `source · page ${evalu.source_page}`,
                    }}
                    onOpen={setSourceOpen}
                  />
                )}
              </div>
            </div>

            {/* Confidence Mosaic */}
            {evalu.confidence_breakdown && (
              <div className="card p-4">
                <div className="section-title mb-3">Confidence mosaic</div>
                <ConfidenceMosaic breakdown={evalu.confidence_breakdown} size="lg" />
                <div className="text-xs text-ink-soft mt-3">
                  {evalu.explanation?.confidence_note ??
                    'Composite confidence is the harmonic mean of the components above; any one weak component lowers the total.'}
                </div>
              </div>
            )}

            {/* Tender DNA — Institutional Memory */}
            <TenderDNA evaluationId={evalu.id} />

            {/* Dissent */}
            {evalu.dissent_branch && evalu.dissent_branch.dissent && (
              <div className="card p-4 border-warning">
                <div className="flex items-center gap-2 text-xs text-warning uppercase tracking-wide mb-2">
                  <ShieldAlert size={12} />
                  Devil's-advocate review · severity {evalu.dissent_branch.severity}
                </div>
                <div className="text-sm text-ink leading-relaxed italic">
                  "{evalu.dissent_branch.dissent}"
                </div>
                {evalu.dissent_branch.suggested_check && (
                  <div className="text-xs text-ink-soft mt-2">
                    Suggested check: {evalu.dissent_branch.suggested_check}
                  </div>
                )}
              </div>
            )}

            {/* Anomalies attached */}
            {evalu.anomalies_attached && evalu.anomalies_attached.length > 0 && (
              <div className="card p-4">
                <div className="section-title mb-3">Smell-test signals</div>
                <ul className="space-y-2">
                  {evalu.anomalies_attached.slice(0, 8).map(a => (
                    <li key={a.id} className="flex items-start gap-2 text-sm">
                      <Pill tone={a.severity === 'high' ? 'danger' : a.severity === 'medium' ? 'warning' : 'soft'}>
                        {a.severity}
                      </Pill>
                      <div>
                        <div className="font-medium text-ink">{a.flag_type.replace(/_/g, ' ')}</div>
                        <div className="text-xs text-ink-muted">{a.message}</div>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Post-review checks */}
            {evalu.post_review_checks && evalu.post_review_checks.length > 0 && (
              <div className="card p-4">
                <div className="section-title mb-3">Did you also check…</div>
                <ul className="space-y-2">
                  {evalu.post_review_checks.map(c => (
                    <li key={c.id} className="flex items-start justify-between gap-3 text-sm">
                      <span className="text-ink">{c.check_text}</span>
                      <PostReviewAnswer check={c} />
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Evidence Provenance Graph */}
            <div className="card p-4">
              <EvidenceGraph evaluationId={evalu.id} />
            </div>

            {/* Officer comment thread — Module 4 HITL */}
            <CommentThread evaluationId={evalu.id} />

            {/* Officer decision */}
            <div className="card p-4 bg-bg-sunk">
              <div className="section-title mb-3">Your decision</div>

              {/* What-If Preview — shows consequences before deciding */}
              <WhatIfPreview
                evaluationId={evalu.id}
                action={overrideMode ? 'override' : 'confirm'}
                newVerdict={overrideMode ? overrideVerdict : evalu.verdict}
              />

              {!overrideMode && (
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="success"
                    icon={<CheckCircle2 size={14} />}
                    disabled={saving}
                    onClick={async () => {
                      setSaving(true);
                      try {
                        await evaluationsApi.decide(evalu.id, { decision: 'confirmed', reason_text: reasonText });
                        toast('✓ Verdict confirmed.', 'success');
                        setTimeout(() => {
                          onChanged?.();
                          onClose();
                        }, 600);
                      } catch (e) {
                        toast(`Failed: ${(e as Error).message}`, 'error');
                        setSaving(false);
                      }
                    }}
                  >
                    {saving ? 'Saving…' : 'Confirm verdict'}
                  </Button>
                  <Button
                    variant="warning"
                    icon={<RotateCcw size={14} />}
                    onClick={() => setOverrideMode(true)}
                    disabled={saving}
                  >
                    Override
                  </Button>
                </div>
              )}

              {overrideMode && (
                <div className="space-y-3">
                  <div>
                    <label className="label">New verdict</label>
                    <div className="segmented">
                      {(['PASS','FAIL','REVIEW'] as const).map(v => (
                        <button
                          key={v}
                          type="button"
                          className={`segmented-item ${overrideVerdict === v ? 'is-active' : ''}`}
                          onClick={() => setOverrideVerdict(v)}
                        >
                          {v}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <label className="label">Reason for override</label>
                    <textarea
                      className="textarea text-sm"
                      placeholder="Document this decision for the audit trail …"
                      value={reasonText}
                      onChange={e => setReasonText(e.target.value)}
                      rows={3}
                    />
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="warning"
                      icon={<CheckCircle2 size={14} />}
                      disabled={reasonText.trim().length < 5 || saving}
                      onClick={async () => {
                        setSaving(true);
                        try {
                          await evaluationsApi.decide(evalu.id, {
                            decision: 'overridden',
                            new_verdict: overrideVerdict,
                            reason_text: reasonText,
                            structured_reason: 'officer_override',
                          });
                          toast('✓ Override saved successfully. Concurrence request opened.', 'success');
                          // Small delay so user sees the toast before drawer closes
                          setTimeout(() => {
                            onChanged?.();
                            onClose();
                          }, 800);
                        } catch (e) {
                          toast(`Failed: ${(e as Error).message}`, 'error');
                          setSaving(false);
                        }
                      }}
                    >
                      {saving ? 'Saving…' : 'Save override'}
                    </Button>
                    <Button
                      variant="ghost"
                      icon={<XCircle size={14} />}
                      onClick={() => { setOverrideMode(false); setReasonText(''); }}
                      disabled={saving}
                    >
                      Cancel
                    </Button>
                  </div>
                  {saving && (
                    <div style={{ fontSize: '11px', color: 'var(--success)', marginTop: '6px', fontWeight: 600 }}>
                      ✓ Override recorded. Opening concurrence request...
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Reproduce */}
            <div className="text-xs text-ink-soft">
              Pipeline signature:&nbsp;
              <span className="mono">{evalu.pipeline_signature_hash}</span>
            </div>
          </div>
        )}
      </Drawer>

      {/* Inner drawer for source PDF */}
      {sourceOpen && (
        <Drawer
          open
          onClose={() => setSourceOpen(null)}
          title="Source document"
          width="min(900px, 95vw)"
        >
          <div className="h-full">
            <PDFViewer
              docId={sourceOpen.doc_id}
              initialPage={sourceOpen.page}
              highlight={sourceOpen.bbox || null}
              highlightText={sourceOpen.quote || null}
            />
          </div>
        </Drawer>
      )}
    </>
  );
}

function PostReviewAnswer({ check }: { check: { id: string; answer?: string | null } }) {
  const [val, setVal] = useState(check.answer || '');
  return (
    <div className="segmented">
      {(['yes','no','not_applicable'] as const).map(opt => (
        <button
          key={opt}
          type="button"
          className={`segmented-item ${val === opt ? 'is-active' : ''}`}
          onClick={async () => {
            setVal(opt);
            try {
              await evaluationsApi.answerCheck(check.id, opt);
            } catch {/* ignore */}
          }}
        >
          {opt === 'not_applicable' ? 'N/A' : opt}
        </button>
      ))}
    </div>
  );
}
