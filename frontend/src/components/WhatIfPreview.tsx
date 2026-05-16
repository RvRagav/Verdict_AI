// What-If Simulator — shows consequences BEFORE the officer decides.
// Appears in the EvaluationDrawer above the decision buttons.
// Calls the AI-powered what-if endpoint for intelligent reasoning.

import { useEffect, useState } from 'react';
import { AlertTriangle, ArrowRight, Brain, Shield } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import api from '../api/client';

type WhatIfResult = {
  current_verdict: string;
  simulated_verdict: string;
  verdict_change: string | null;
  bidder: {
    name: string;
    current: { pass: number; fail: number; review: number; total: number };
    simulated: { pass: number; fail: number; review: number; total: number };
    was_eligible: boolean;
    will_be_eligible: boolean;
    eligibility_change: string | null;
  };
  concurrence_required: boolean;
  shared_source_cells: any[];
  consequences: { type: string; text: string; severity: string }[];
  ai_reasoning: string | null;
};

export default function WhatIfPreview({
  evaluationId,
  action,
  newVerdict,
}: {
  evaluationId: string;
  action: 'confirm' | 'override';
  newVerdict?: string;
}) {
  const [result, setResult] = useState<WhatIfResult | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!evaluationId || !action) return;
    setLoading(true);
    api.post(`/evaluations/${evaluationId}/what-if`, {
      action,
      new_verdict: newVerdict || null,
    })
      .then(res => setResult(res.data))
      .catch(() => setResult(null))
      .finally(() => setLoading(false));
  }, [evaluationId, action, newVerdict]);

  if (loading) return <div style={{ padding: '8px', fontSize: '11px', color: 'var(--ink-soft)' }}>Analyzing consequences...</div>;
  if (!result) return null;

  const hasConsequences = result.consequences.length > 0 || result.ai_reasoning;

  if (!hasConsequences) return null;

  return (
    <div style={{
      background: '#fff8e1',
      border: '1px solid #f9a825',
      borderRadius: '4px',
      padding: '10px 12px',
      marginBottom: '12px',
      fontSize: '12px',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px', fontWeight: 700, color: '#f57f17' }}>
        <Brain size={14} /> What happens if you {action === 'override' ? `override to ${newVerdict}` : 'confirm'}?
      </div>

      {/* Score change */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px', fontSize: '11px' }}>
        <span style={{ color: 'var(--ink-muted)' }}>{result.bidder.name}:</span>
        <span>{result.bidder.current.pass}P/{result.bidder.current.fail}F/{result.bidder.current.review}R</span>
        <ArrowRight size={10} />
        <span style={{ fontWeight: 600 }}>{result.bidder.simulated.pass}P/{result.bidder.simulated.fail}F/{result.bidder.simulated.review}R</span>
      </div>

      {/* Consequences */}
      {result.consequences.filter(c => c.type !== 'ai_reasoning').map((c, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: '6px', marginBottom: '4px' }}>
          {c.severity === 'high' && <AlertTriangle size={11} style={{ color: '#c62828', flexShrink: 0, marginTop: '2px' }} />}
          {c.severity === 'medium' && <Shield size={11} style={{ color: '#f57f17', flexShrink: 0, marginTop: '2px' }} />}
          <span style={{ color: c.severity === 'high' ? '#c62828' : 'var(--ink-muted)' }}>{c.text}</span>
        </div>
      ))}

      {/* AI Reasoning */}
      {result.ai_reasoning && (
        <div style={{
          marginTop: '8px',
          padding: '8px',
          background: 'rgba(255,255,255,0.7)',
          borderRadius: '3px',
          borderLeft: '3px solid var(--primary)',
          fontSize: '11px',
          lineHeight: 1.5,
          color: 'var(--ink)',
        }}>
          <div style={{ fontWeight: 600, color: 'var(--primary)', marginBottom: '3px', fontSize: '10px', textTransform: 'uppercase' }}>
            AI Analysis
          </div>
          <div className="ai-md">
            <ReactMarkdown>{result.ai_reasoning}</ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  );
}
