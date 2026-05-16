// Tender DNA — Institutional Memory panel.
// Shows precedents (past decisions on similar criteria) + AI insight.
// Appears in the EvaluationDrawer after the Confidence Mosaic.

import { useEffect, useState } from 'react';
import { Dna, Clock, User } from 'lucide-react';
import api from '../api/client';

type Precedent = {
  id: string;
  criterion_text: string;
  verdict: string;
  officer_action: string;
  officer_name: string;
  interpretation: string;
  created_at: string;
};

type PrecedentData = {
  criterion_text: string;
  department: string;
  precedents: Precedent[];
  count: number;
  ai_insight: string | null;
};

export default function TenderDNA({ evaluationId }: { evaluationId: string }) {
  const [data, setData] = useState<PrecedentData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!evaluationId) return;
    api.get(`/evaluations/${evaluationId}/precedents`)
      .then(res => setData(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [evaluationId]);

  if (loading) return null; // Don't show loading state — it's a secondary panel
  if (!data) return null;

  // Only show if there's AI insight or precedents
  if (!data.ai_insight && data.count === 0) return null;

  return (
    <div className="card" style={{ padding: '12px', borderLeft: '3px solid #6a1b9a' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
        <Dna size={14} style={{ color: '#6a1b9a' }} />
        <span style={{ fontSize: '12px', fontWeight: 700, color: '#6a1b9a', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
          Institutional Memory
        </span>
        {data.count > 0 && (
          <span style={{ fontSize: '10px', color: 'var(--ink-soft)', marginLeft: 'auto' }}>
            {data.count} precedent(s)
          </span>
        )}
      </div>

      {/* Precedents list */}
      {data.precedents.length > 0 && (
        <div style={{ marginBottom: '8px' }}>
          {data.precedents.slice(0, 3).map(p => (
            <div key={p.id} style={{
              padding: '6px 8px',
              background: 'var(--bg-soft)',
              borderRadius: '3px',
              marginBottom: '4px',
              fontSize: '11px',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <User size={10} style={{ color: 'var(--ink-soft)' }} />
                <span style={{ fontWeight: 600 }}>{p.officer_name}</span>
                <span style={{
                  padding: '1px 5px',
                  borderRadius: '2px',
                  fontSize: '9px',
                  fontWeight: 700,
                  background: p.officer_action === 'confirmed' ? 'var(--success-soft)' : 'var(--warning-soft)',
                  color: p.officer_action === 'confirmed' ? 'var(--success)' : '#856404',
                }}>
                  {p.officer_action}
                </span>
                <span style={{
                  padding: '1px 5px',
                  borderRadius: '2px',
                  fontSize: '9px',
                  fontWeight: 700,
                  background: p.verdict === 'PASS' ? 'var(--success-soft)' : p.verdict === 'FAIL' ? 'var(--danger-soft)' : 'var(--warning-soft)',
                  color: p.verdict === 'PASS' ? 'var(--success)' : p.verdict === 'FAIL' ? 'var(--danger)' : '#856404',
                }}>
                  {p.verdict}
                </span>
                <Clock size={9} style={{ color: 'var(--ink-faint)', marginLeft: 'auto' }} />
                <span style={{ fontSize: '9px', color: 'var(--ink-faint)' }}>
                  {timeAgo(p.created_at)}
                </span>
              </div>
              <div style={{ marginTop: '3px', color: 'var(--ink-muted)', fontSize: '10px' }}>
                {p.interpretation.slice(0, 100)}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* AI Insight */}
      {data.ai_insight && (
        <div style={{
          padding: '8px',
          background: '#f3e5f5',
          borderRadius: '3px',
          fontSize: '11px',
          lineHeight: 1.5,
          color: '#4a148c',
        }}>
          <span style={{ fontWeight: 600 }}>AI Insight: </span>
          {data.ai_insight}
        </div>
      )}
    </div>
  );
}

function timeAgo(iso: string): string {
  try {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    return `${days}d ago`;
  } catch {
    return '';
  }
}
