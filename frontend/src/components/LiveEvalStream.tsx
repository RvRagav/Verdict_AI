// Live Evaluation Stream — shows cells appearing one-by-one in real-time.
// Uses SSE to stream results as Bedrock processes each (bidder × criterion) cell.
// The matrix fills in like a scoreboard. The judge watches the AI work.

import { useState, useRef } from 'react';
import { Play, Loader, CheckCircle2, XCircle, HelpCircle } from 'lucide-react';
import { getOfficer } from '../api/client';
import Button from './Button';

type StreamCell = {
  bidder_id: string;
  bidder_name: string;
  criterion_id: string;
  criterion_text: string;
  verdict: string;
  confidence: number;
};

type StreamState = 'idle' | 'running' | 'done' | 'error';

export default function LiveEvalStream({
  tenderId,
  onComplete,
}: {
  tenderId: string;
  onComplete?: () => void;
}) {
  const [state, setState] = useState<StreamState>('idle');
  const [cells, setCells] = useState<StreamCell[]>([]);
  const [cellsTotal, setCellsTotal] = useState(0);
  const [passCount, setPassCount] = useState(0);
  const [failCount, setFailCount] = useState(0);
  const [reviewCount, setReviewCount] = useState(0);
  const [currentBidder, setCurrentBidder] = useState('');
  const abortRef = useRef<AbortController | null>(null);

  async function startStream() {
    setState('running');
    setCells([]);
    setPassCount(0);
    setFailCount(0);
    setReviewCount(0);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const res = await fetch(`/api/v1/tenders/${tenderId}/evaluate/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Officer-ID': getOfficer(),
        },
        signal: controller.signal,
      });

      if (!res.body) throw new Error('No response body');
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const m = line.match(/^data:\s*(.*)$/);
          if (!m) continue;
          try {
            const evt = JSON.parse(m[1]);
            if (evt.type === 'started') {
              setCellsTotal(evt.cells_total);
            } else if (evt.type === 'cell_complete') {
              const cell: StreamCell = {
                bidder_id: evt.bidder_id,
                bidder_name: evt.bidder_name,
                criterion_id: evt.criterion_id,
                criterion_text: evt.criterion_text,
                verdict: evt.verdict,
                confidence: evt.confidence,
              };
              setCells(prev => [...prev, cell]);
              if (evt.verdict === 'PASS') setPassCount(p => p + 1);
              else if (evt.verdict === 'FAIL') setFailCount(p => p + 1);
              else setReviewCount(p => p + 1);
            } else if (evt.type === 'progress') {
              setCurrentBidder(evt.bidder_complete || '');
            } else if (evt.type === 'done') {
              setState('done');
              onComplete?.();
            } else if (evt.type === 'error') {
              setState('error');
            }
          } catch { /* ignore parse errors */ }
        }
      }
      if (state !== 'done') setState('done');
    } catch (e: any) {
      if (e.name !== 'AbortError') setState('error');
    }
  }

  const progress = cellsTotal > 0 ? (cells.length / cellsTotal) * 100 : 0;

  if (state === 'idle') {
    return (
      <Button variant="primary" icon={<Play size={14} />} onClick={startStream}>
        Run Live Evaluation
      </Button>
    );
  }

  // After completion, show a compact summary that can be dismissed
  if (state === 'done') {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 12px', background: 'var(--success-soft)', border: '1px solid var(--success)', borderRadius: '4px', fontSize: '12px' }}>
        <CheckCircle2 size={14} style={{ color: 'var(--success)' }} />
        <span style={{ fontWeight: 600, color: 'var(--success)' }}>Evaluation complete</span>
        <span style={{ color: 'var(--ink-muted)' }}>{cells.length} cells · {passCount}P / {failCount}F / {reviewCount}R</span>
        <button
          onClick={() => setState('idle')}
          style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--ink-soft)', fontSize: '14px' }}
          title="Dismiss"
        >
          ✕
        </button>
      </div>
    );
  }

  if (state === 'error') {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 12px', background: 'var(--danger-soft)', border: '1px solid var(--danger)', borderRadius: '4px', fontSize: '12px' }}>
        <span style={{ color: 'var(--danger)', fontWeight: 600 }}>Evaluation error</span>
        <button onClick={() => setState('idle')} style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--ink-soft)' }}>✕</button>
      </div>
    );
  }

  // Running state — show the full progress panel

  return (
    <div className="card" style={{ padding: '16px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
        <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--primary)' }}>
          {'⚡ Live Evaluation in Progress'}
        </div>
        <div style={{ fontSize: '12px', color: 'var(--ink-soft)' }}>
          {cells.length} / {cellsTotal} cells
        </div>
      </div>

      {/* Progress bar */}
      <div style={{ height: '8px', background: 'var(--bg-sunk)', borderRadius: '4px', overflow: 'hidden', marginBottom: '12px' }}>
        <div style={{
          height: '100%',
          width: `${progress}%`,
          background: 'var(--primary)',
          transition: 'width 0.3s ease',
          borderRadius: '4px',
        }} />
      </div>

      {/* Live scoreboard */}
      <div style={{ display: 'flex', gap: '16px', marginBottom: '12px', fontSize: '13px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <CheckCircle2 size={14} style={{ color: 'var(--success)' }} />
          <span style={{ fontWeight: 700, color: 'var(--success)' }}>{passCount}</span>
          <span style={{ color: 'var(--ink-soft)' }}>PASS</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <XCircle size={14} style={{ color: 'var(--danger)' }} />
          <span style={{ fontWeight: 700, color: 'var(--danger)' }}>{failCount}</span>
          <span style={{ color: 'var(--ink-soft)' }}>FAIL</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <HelpCircle size={14} style={{ color: '#856404' }} />
          <span style={{ fontWeight: 700, color: '#856404' }}>{reviewCount}</span>
          <span style={{ color: 'var(--ink-soft)' }}>REVIEW</span>
        </div>
        {state === 'running' && currentBidder && (
          <div style={{ marginLeft: 'auto', fontSize: '11px', color: 'var(--ink-soft)', display: 'flex', alignItems: 'center', gap: '4px' }}>
            <Loader size={11} className="animate-spin" /> Processing: {currentBidder}
          </div>
        )}
      </div>

      {/* Live cell feed — last 8 cells */}
      <div style={{ maxHeight: '200px', overflow: 'auto', borderTop: '1px solid var(--line)', paddingTop: '8px' }}>
        {cells.slice(-8).reverse().map((cell, i) => (
          <div key={`${cell.bidder_id}-${cell.criterion_id}`} style={{
            display: 'flex', alignItems: 'center', gap: '8px',
            padding: '4px 0', fontSize: '11px',
            opacity: i === 0 ? 1 : 0.7 + (0.3 * (1 - i / 8)),
            animation: i === 0 ? 'fadeIn 0.3s ease' : undefined,
          }}>
            <span style={{
              width: '6px', height: '6px', borderRadius: '50%', flexShrink: 0,
              background: cell.verdict === 'PASS' ? 'var(--success)' : cell.verdict === 'FAIL' ? 'var(--danger)' : 'var(--warning)',
            }} />
            <span style={{ fontWeight: 500, color: 'var(--ink)', minWidth: '120px' }}>{cell.bidder_name.slice(0, 20)}</span>
            <span style={{ color: 'var(--ink-soft)', flex: 1 }}>{cell.criterion_text.slice(0, 40)}…</span>
            <span style={{
              fontWeight: 700, fontSize: '10px',
              color: cell.verdict === 'PASS' ? 'var(--success)' : cell.verdict === 'FAIL' ? 'var(--danger)' : '#856404',
            }}>
              {cell.verdict} {Math.round(cell.confidence * 100)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
