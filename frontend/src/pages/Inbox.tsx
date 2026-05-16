// Review queue — concurrence requests for the signed-in officer.
// Now with RICH REVIEW CONTEXT: second officer sees full evaluation,
// source docs, officer comments, anomalies, and conditions.

import { useEffect, useState } from 'react';
import {
  Inbox as InboxIcon, CheckCircle2, XCircle, FileText,
  AlertTriangle, MessageSquare, ShieldAlert, Sparkles, Eye,
} from 'lucide-react';
import { concurrenceApi } from '../api/endpoints';
import type { ConcurrenceRequest, Evaluation, OfficerComment, AnomalyFlag } from '../types';
import { Card, CardBody } from '../components/Card';
import Pill from '../components/Pill';
import Button from '../components/Button';
import Drawer from '../components/Drawer';
import ConfidenceMosaic from '../components/ConfidenceMosaic';
import { useToast } from '../components/Toast';

type ReviewContext = {
  request: any;
  evaluation: Evaluation;
  criterion: any;
  bidder: any;
  comments: OfficerComment[];
  actionable_comments: OfficerComment[];
  anomalies: AnomalyFlag[];
  source_document: any;
  requesting_officer: any;
};

export default function Inbox() {
  const [items, setItems] = useState<ConcurrenceRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeReq, setActiveReq] = useState<ConcurrenceRequest | null>(null);
  const [reviewContext, setReviewContext] = useState<ReviewContext | null>(null);
  const [reviewDrawerOpen, setReviewDrawerOpen] = useState(false);
  const [decisionNote, setDecisionNote] = useState('');
  const [contextLoading, setContextLoading] = useState(false);
  const toast = useToast();

  const refresh = () => concurrenceApi.inbox('open').then(setItems).finally(() => setLoading(false));

  useEffect(() => { refresh(); }, []);

  async function openReq(req: ConcurrenceRequest) {
    setActiveReq(req);
    setDecisionNote('');
    setContextLoading(true);
    setReviewDrawerOpen(true);
    try {
      const ctx = await concurrenceApi.reviewContext(req.id);
      setReviewContext(ctx);
    } catch (e) {
      toast((e as Error).message, 'error');
    } finally {
      setContextLoading(false);
    }
  }

  async function decide(decision: 'concurred' | 'rejected') {
    if (!activeReq) return;
    if (decisionNote.trim().length < 5) {
      toast('Please add a short note for the audit trail.', 'error');
      return;
    }
    try {
      await concurrenceApi.decide(activeReq.id, { decision, decision_note: decisionNote });
      toast(decision === 'concurred' ? 'Concurred — second-officer signature recorded.' : 'Rejected and sent back.', 'success');
      setReviewDrawerOpen(false);
      setActiveReq(null);
      setReviewContext(null);
      refresh();
    } catch (e) {
      toast((e as Error).message, 'error');
    }
  }

  return (
    <div className="mx-auto max-w-[1100px] px-6 py-8">
      <div className="flex items-end justify-between mb-6">
        <div>
          <h1 className="font-display font-bold text-3xl text-ink">Review queue</h1>
          <div className="text-sm text-ink-soft mt-1">Items awaiting your concurrence as second officer.</div>
        </div>
      </div>

      {loading ? (
        <div className="empty">Loading …</div>
      ) : items.length === 0 ? (
        <Card>
          <div className="empty">
            <InboxIcon size={20} className="mx-auto text-ink-soft mb-2" />
            <div className="text-md font-semibold text-ink">Inbox empty</div>
            <div className="text-sm">Nothing currently waits on your sign-off.</div>
          </div>
        </Card>
      ) : (
        <div className="space-y-3">
          {items.map(req => (
            <Card key={req.id} hover>
              <CardBody className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <Pill tone="warning">awaiting concurrence</Pill>
                    <Pill tone="primary">{req.tender_number}</Pill>
                  </div>
                  <div className="font-semibold text-ink truncate">{req.title}</div>
                  <div className="text-sm text-ink-soft mt-1 line-clamp-2">{req.request_reason}</div>
                  <div className="text-xs text-ink-faint mt-2 mono">
                    requested {new Date(req.created_at).toLocaleString()} · evaluation {req.evaluation_id.slice(0, 8)}
                  </div>
                </div>
                <Button variant="primary" onClick={() => openReq(req)}>
                  Review
                </Button>
              </CardBody>
            </Card>
          ))}
        </div>
      )}

      {/* Review drawer — RICH CONTEXT */}
      {reviewDrawerOpen && activeReq && (
        <Drawer
          open
          onClose={() => { setReviewDrawerOpen(false); setReviewContext(null); }}
          title="Concurrence review"
          width="min(900px, 95vw)"
        >
          {contextLoading ? (
            <div className="empty" style={{ padding: '40px' }}>Loading full review context …</div>
          ) : reviewContext ? (
            <div style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>

              {/* Quick action: View in Tender Space */}
              <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                <a
                  href={`/tenders/${reviewContext.request.tender_id}/evaluation`}
                  target="_blank"
                  rel="noopener"
                  style={{
                    display: 'inline-flex', alignItems: 'center', gap: '6px',
                    fontSize: '12px', fontWeight: 600, color: 'var(--primary)',
                    textDecoration: 'none', padding: '6px 12px',
                    border: '1px solid var(--primary)', borderRadius: '4px',
                  }}
                >
                  ↗ Open in Tender Space for full verification
                </a>
              </div>

              {/* Section 1: Request header */}
              <Card className="p-4" style={{ borderLeft: '4px solid var(--primary)' }}>
                <div className="section-title mb-2" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <ShieldAlert size={14} style={{ color: 'var(--primary)' }} />
                  First officer's request
                </div>
                <div style={{ fontSize: '13px', color: 'var(--ink)', lineHeight: '1.5' }}>
                  {reviewContext.request.request_reason}
                </div>
                <div style={{ display: 'flex', gap: '12px', marginTop: '8px', fontSize: '11px', color: 'var(--ink-soft)' }}>
                  <span>
                    <strong>Requested by:</strong> {reviewContext.requesting_officer?.name || reviewContext.request.requested_by}
                    {reviewContext.requesting_officer?.role && ` (${reviewContext.requesting_officer.role})`}
                  </span>
                  <span>· {new Date(reviewContext.request.created_at).toLocaleString()}</span>
                </div>
              </Card>

              {/* Section 2: Evaluation verdict + confidence */}
              <Card className="p-4">
                <div className="section-title mb-2" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Sparkles size={14} style={{ color: 'var(--primary)' }} />
                  AI evaluation summary
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
                  <Pill tone={
                    reviewContext.evaluation.verdict === 'PASS' ? 'success'
                    : reviewContext.evaluation.verdict === 'FAIL' ? 'danger'
                    : 'warning'
                  }>
                    {reviewContext.evaluation.officer_decision === 'overridden' ? 'OVERRIDDEN → ' : ''}
                    {reviewContext.evaluation.verdict}
                  </Pill>
                  <Pill tone="primary">{Math.round(reviewContext.evaluation.confidence * 100)}% confidence</Pill>
                  <Pill tone={reviewContext.evaluation.route === 'mandatory_review' ? 'danger' : 'warning'}>
                    {reviewContext.evaluation.route.replace(/_/g, ' ')}
                  </Pill>
                </div>
                {reviewContext.evaluation.explanation?.headline && (
                  <div style={{ fontSize: '13px', color: 'var(--ink)', fontStyle: 'italic', marginBottom: '8px' }}>
                    "{reviewContext.evaluation.explanation.headline}"
                  </div>
                )}
                {reviewContext.evaluation.explanation?.detail && (
                  <div style={{ fontSize: '12px', color: 'var(--ink-muted)' }}>
                    {reviewContext.evaluation.explanation.detail}
                  </div>
                )}
                {reviewContext.evaluation.routing_reason && (
                  <div style={{ fontSize: '11px', color: 'var(--ink-soft)', marginTop: '6px', padding: '6px 8px', background: 'var(--bg-sunk)', borderRadius: '4px' }}>
                    <strong>Routing reason:</strong> {reviewContext.evaluation.routing_reason}
                  </div>
                )}
                {/* Confidence mosaic */}
                {reviewContext.evaluation.confidence_breakdown && (
                  <div style={{ marginTop: '12px' }}>
                    <ConfidenceMosaic breakdown={reviewContext.evaluation.confidence_breakdown} size="sm" />
                  </div>
                )}
              </Card>

              {/* Section 3: Criterion + Bidder context */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                {reviewContext.criterion && (
                  <Card className="p-4">
                    <div className="section-title mb-2">Criterion under review</div>
                    <div style={{ fontSize: '12px', color: 'var(--ink)', lineHeight: '1.5' }}>
                      {reviewContext.criterion.criterion_text}
                    </div>
                    <div style={{ display: 'flex', gap: '6px', marginTop: '8px', flexWrap: 'wrap' }}>
                      <Pill tone="soft">{reviewContext.criterion.criterion_type?.replace(/_/g, ' ')}</Pill>
                      {reviewContext.criterion.is_mandatory && <Pill tone="danger">mandatory</Pill>}
                      {reviewContext.criterion.source_clause_ref && (
                        <Pill tone="primary">{reviewContext.criterion.source_clause_ref}</Pill>
                      )}
                    </div>
                  </Card>
                )}
                {reviewContext.bidder && (
                  <Card className="p-4">
                    <div className="section-title mb-2">Bidder</div>
                    <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--ink)' }}>
                      {reviewContext.bidder.company_name}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--ink-soft)', marginTop: '4px' }}>
                      {reviewContext.bidder.pan_number && <span>PAN: {reviewContext.bidder.pan_number} · </span>}
                      {reviewContext.bidder.gstin && <span>GSTIN: {reviewContext.bidder.gstin}</span>}
                    </div>
                  </Card>
                )}
              </div>

              {/* Section 4: Dissent (devil's advocate) */}
              {reviewContext.evaluation.dissent_branch?.dissent && (
                <Card className="p-4" style={{ borderLeft: '4px solid var(--warning)' }}>
                  <div className="section-title mb-2" style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--warning)' }}>
                    <ShieldAlert size={13} />
                    Devil's-advocate review · severity {reviewContext.evaluation.dissent_branch.severity}
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--ink)', fontStyle: 'italic' }}>
                    "{reviewContext.evaluation.dissent_branch.dissent}"
                  </div>
                  {reviewContext.evaluation.dissent_branch.suggested_check && (
                    <div style={{ fontSize: '11px', color: 'var(--ink-soft)', marginTop: '6px' }}>
                      Suggested check: {reviewContext.evaluation.dissent_branch.suggested_check}
                    </div>
                  )}
                </Card>
              )}

              {/* Section 5: Anomalies */}
              {reviewContext.anomalies.length > 0 && (
                <Card className="p-4">
                  <div className="section-title mb-2" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <AlertTriangle size={13} style={{ color: 'var(--danger)' }} />
                    Anomaly signals ({reviewContext.anomalies.length})
                  </div>
                  <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                    {reviewContext.anomalies.slice(0, 6).map((a, i) => (
                      <li key={a.id || i} style={{ display: 'flex', alignItems: 'start', gap: '8px', padding: '6px 0', borderBottom: '1px solid var(--line)' }}>
                        <Pill tone={a.severity === 'high' ? 'danger' : a.severity === 'medium' ? 'warning' : 'soft'}>
                          {a.severity}
                        </Pill>
                        <div>
                          <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--ink)' }}>{a.flag_type.replace(/_/g, ' ')}</div>
                          <div style={{ fontSize: '11px', color: 'var(--ink-muted)' }}>{a.message}</div>
                        </div>
                      </li>
                    ))}
                  </ul>
                </Card>
              )}

              {/* Section 6: Officer comments — the key context */}
              {reviewContext.comments.length > 0 && (
                <Card className="p-4">
                  <div className="section-title mb-2" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <MessageSquare size={13} />
                    Officer comments ({reviewContext.comments.length})
                    {reviewContext.actionable_comments.length > 0 && (
                      <Pill tone="warning" style={{ marginLeft: '6px', fontSize: '9px' }}>
                        {reviewContext.actionable_comments.length} affect verdict
                      </Pill>
                    )}
                  </div>
                  <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                    {reviewContext.comments.map(c => (
                      <li key={c.id} style={{
                        borderLeft: `3px solid ${c.affects_verdict ? 'var(--warning)' : 'var(--line)'}`,
                        paddingLeft: '10px',
                        paddingTop: '6px',
                        paddingBottom: '6px',
                        marginBottom: '6px',
                        background: c.affects_verdict ? 'var(--warning-soft)' : undefined,
                        borderRadius: c.affects_verdict ? '0 4px 4px 0' : undefined,
                      }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '10px', color: 'var(--ink-soft)' }}>
                          <span style={{ fontWeight: 600, color: 'var(--ink)' }}>{c.officer_name || c.officer_id}</span>
                          {c.category && (
                            <Pill tone={c.affects_verdict ? 'warning' : 'soft'} style={{ fontSize: '9px' }}>
                              {c.category.replace(/_/g, ' ')}
                            </Pill>
                          )}
                          <span style={{ marginLeft: 'auto', fontFamily: 'monospace' }}>
                            {new Date(c.created_at).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}
                          </span>
                        </div>
                        <div style={{ fontSize: '12px', color: 'var(--ink)', whiteSpace: 'pre-wrap', marginTop: '3px' }}>{c.body}</div>
                        {c.key_insight && (
                          <div style={{ fontSize: '10px', color: 'var(--primary)', marginTop: '3px', fontStyle: 'italic' }}>
                            💡 {c.key_insight}
                          </div>
                        )}
                      </li>
                    ))}
                  </ul>
                </Card>
              )}

              {/* Section 7: Source document reference */}
              {reviewContext.source_document && (
                <Card className="p-4">
                  <div className="section-title mb-2" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <FileText size={13} />
                    Source document
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--ink)' }}>
                    <strong>{reviewContext.source_document.filename}</strong>
                    <span style={{ color: 'var(--ink-soft)', marginLeft: '8px' }}>
                      ({reviewContext.source_document.doc_type} · {reviewContext.source_document.page_count} pages)
                    </span>
                  </div>
                  {reviewContext.evaluation.source_page && (
                    <div style={{ fontSize: '11px', color: 'var(--ink-soft)', marginTop: '4px' }}>
                      Evidence found on page {reviewContext.evaluation.source_page}
                    </div>
                  )}
                </Card>
              )}

              {/* Section 8: Post-review checks */}
              {reviewContext.evaluation.post_review_checks && reviewContext.evaluation.post_review_checks.length > 0 && (
                <Card className="p-4">
                  <div className="section-title mb-2" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Eye size={13} />
                    Post-review checks (first officer's answers)
                  </div>
                  <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                    {reviewContext.evaluation.post_review_checks.map(c => (
                      <li key={c.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '4px 0', fontSize: '12px' }}>
                        <span style={{ color: 'var(--ink)' }}>{c.check_text}</span>
                        <Pill tone={c.answer === 'yes' ? 'success' : c.answer === 'no' ? 'danger' : 'soft'}>
                          {c.answer || 'unanswered'}
                        </Pill>
                      </li>
                    ))}
                  </ul>
                </Card>
              )}

              {/* Decision section */}
              <Card className="p-4" style={{ background: 'var(--bg-sunk)', borderTop: '2px solid var(--primary)' }}>
                <div className="section-title mb-3">Your concurrence decision</div>
                <div>
                  <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--ink)', display: 'block', marginBottom: '6px' }}>
                    Your note (recorded in audit chain) *
                  </label>
                  <textarea
                    className="textarea text-sm"
                    rows={3}
                    value={decisionNote}
                    onChange={e => setDecisionNote(e.target.value)}
                    placeholder="State your reasoning for the audit trail — reference specific evidence, comments, or conditions …"
                  />
                </div>

                <div className="flex gap-2 pt-3">
                  <Button
                    variant="success"
                    icon={<CheckCircle2 size={14} />}
                    onClick={() => decide('concurred')}
                    disabled={decisionNote.trim().length < 5}
                  >
                    Concur (sign off)
                  </Button>
                  <Button
                    variant="danger"
                    icon={<XCircle size={14} />}
                    onClick={() => decide('rejected')}
                    disabled={decisionNote.trim().length < 5}
                  >
                    Reject (send back)
                  </Button>
                </div>
              </Card>
            </div>
          ) : (
            <div className="empty" style={{ padding: '40px' }}>Failed to load review context.</div>
          )}
        </Drawer>
      )}
    </div>
  );
}
