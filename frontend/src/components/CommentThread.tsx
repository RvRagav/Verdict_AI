// Per-cell officer comment thread with AI classification.
//
// Comments are classified by AI into categories (observation, logic,
// action_required, brainstorm, concern). When a comment challenges the
// verdict, the system surfaces it as a "re-evaluate" suggestion — making
// officer thinking and AI analysis feel like one unified channel.

import { useEffect, useState } from 'react';
import { MessageSquare, Send, Brain, AlertTriangle, Lightbulb, Eye, HelpCircle, RefreshCcw } from 'lucide-react';
import { commentsApi } from '../api/endpoints';
import { useToast } from './Toast';
import Button from './Button';
import Pill from './Pill';
import type { OfficerComment } from '../types';

const CATEGORY_CONFIG: Record<string, { icon: typeof Brain; label: string; color: string }> = {
  observation: { icon: Eye, label: 'Observation', color: 'var(--ink-soft)' },
  logic: { icon: Brain, label: 'Logic / Reasoning', color: 'var(--primary)' },
  action_required: { icon: AlertTriangle, label: 'Action Required', color: 'var(--danger)' },
  brainstorm: { icon: Lightbulb, label: 'Brainstorm', color: '#856404' },
  concern: { icon: AlertTriangle, label: 'Concern', color: 'var(--warning)' },
};

export default function CommentThread({
  evaluationId,
  onReEvaluate,
}: {
  evaluationId: string;
  onReEvaluate?: () => void;
}) {
  const [comments, setComments] = useState<OfficerComment[]>([]);
  const [draft, setDraft] = useState('');
  const [sending, setSending] = useState(false);
  const toast = useToast();

  const refresh = () => commentsApi.forEvaluation(evaluationId).then(setComments);

  useEffect(() => {
    if (!evaluationId) return;
    refresh();
  }, [evaluationId]);

  async function send() {
    const body = draft.trim();
    if (!body || sending) return;
    setSending(true);
    try {
      await commentsApi.addForEvaluation(evaluationId, body);
      setDraft('');
      await refresh();
    } catch (e) {
      toast(`Couldn't add comment: ${(e as Error).message}`, 'error');
    } finally {
      setSending(false);
    }
  }

  const actionableComments = comments.filter(c => c.affects_verdict);
  const hasActionable = actionableComments.length > 0;

  return (
    <div className="card p-4">
      <div className="flex items-center gap-2 section-title mb-3">
        <MessageSquare size={12} />
        Officer notes <span className="text-ink-soft">({comments.length})</span>
        {hasActionable && (
          <Pill tone="warning" style={{ marginLeft: '8px', fontSize: '10px' }}>
            {actionableComments.length} affect{actionableComments.length === 1 ? 's' : ''} verdict
          </Pill>
        )}
      </div>

      {/* AI Pre-mortem: actionable comments summary */}
      {hasActionable && (
        <div style={{
          background: 'var(--warning-soft)',
          border: '1px solid var(--warning)',
          borderRadius: '6px',
          padding: '10px 12px',
          marginBottom: '12px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
            <Brain size={13} style={{ color: 'var(--warning)' }} />
            <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--warning)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              AI Pre-mortem — Re-evaluate based on your comments
            </span>
          </div>
          <ul style={{ margin: 0, paddingLeft: '16px', fontSize: '12px', color: 'var(--ink)' }}>
            {actionableComments.map(c => (
              <li key={c.id} style={{ marginBottom: '4px' }}>
                <span style={{ fontWeight: 600 }}>{c.officer_name || c.officer_id}:</span>{' '}
                {c.key_insight || c.body.slice(0, 80)}
                {c.suggested_action && (
                  <Pill tone="warning" style={{ marginLeft: '6px', fontSize: '9px' }}>
                    {c.suggested_action.replace(/_/g, ' ')}
                  </Pill>
                )}
              </li>
            ))}
          </ul>
          {onReEvaluate && (
            <Button
              variant="warning"
              icon={<RefreshCcw size={12} />}
              onClick={onReEvaluate}
              style={{ marginTop: '8px', fontSize: '11px' }}
            >
              Re-evaluate considering these points
            </Button>
          )}
        </div>
      )}

      {comments.length === 0 && (
        <div className="text-xs text-ink-soft mb-3 italic">
          No notes yet. Write the why behind your decision so a successor
          three years from now can read it back.
        </div>
      )}

      <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 12px 0' }}>
        {comments.map(c => {
          const catConfig = c.category ? CATEGORY_CONFIG[c.category] : null;
          const CatIcon = catConfig?.icon || HelpCircle;
          return (
            <li key={c.id} style={{
              borderLeft: `3px solid ${c.affects_verdict ? 'var(--warning)' : catConfig?.color || 'var(--line)'}`,
              paddingLeft: '12px',
              paddingTop: '6px',
              paddingBottom: '6px',
              marginBottom: '8px',
              background: c.affects_verdict ? 'var(--warning-soft)' : undefined,
              borderRadius: c.affects_verdict ? '0 4px 4px 0' : undefined,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: 'var(--ink-soft)' }}>
                <span style={{ fontWeight: 600, color: 'var(--ink)' }}>{c.officer_name || c.officer_id}</span>
                {c.officer_role && <span>· {c.officer_role}</span>}
                {catConfig && (
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '3px', color: catConfig.color, fontWeight: 500 }}>
                    <CatIcon size={10} />
                    {catConfig.label}
                  </span>
                )}
                <span style={{ marginLeft: 'auto', fontFamily: 'monospace', fontSize: '10px' }}>{formatTime(c.created_at)}</span>
              </div>
              <div style={{ fontSize: '13px', color: 'var(--ink)', whiteSpace: 'pre-wrap', marginTop: '4px' }}>{c.body}</div>
              {c.key_insight && c.key_insight !== c.body && (
                <div style={{ fontSize: '11px', color: 'var(--primary)', marginTop: '4px', fontStyle: 'italic' }}>
                  💡 AI insight: {c.key_insight}
                </div>
              )}
            </li>
          );
        })}
      </ul>

      <div className="flex items-end gap-2">
        <textarea
          className="textarea text-sm flex-1"
          placeholder="Add a note — reasoning, concerns, or observations for the audit trail …"
          value={draft}
          onChange={e => setDraft(e.target.value)}
          rows={2}
          onKeyDown={e => {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
              e.preventDefault();
              send();
            }
          }}
          disabled={sending}
          aria-label="Add officer note"
        />
        <Button
          variant="primary"
          icon={<Send size={13} />}
          onClick={send}
          disabled={!draft.trim() || sending}
        >
          {sending ? 'Saving…' : 'Add note'}
        </Button>
      </div>
      <div className="text-[11px] text-ink-soft mt-1.5">
        Notes are append-only and AI-classified. Cmd/Ctrl+Enter to save. Logic &amp; concerns auto-surface for re-evaluation.
      </div>
    </div>
  );
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      month: 'short', day: 'numeric',
      hour: 'numeric', minute: '2-digit',
    });
  } catch {
    return iso;
  }
}
