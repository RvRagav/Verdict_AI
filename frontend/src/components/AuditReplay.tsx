// Audit Replay — Time-Travel to any decision point.
// Shows a timeline of officer decisions. Click any point → see the matrix state at that moment.
// "Show me what you saw when you made that decision." Click. There it is.

import { useEffect, useState } from 'react';
import { Clock } from 'lucide-react';
import api from '../api/client';
import Pill from './Pill';

type TimelineEvent = {
  event_id: number;
  event_type: string;
  actor: string;
  timestamp: string;
  summary: string;
};

type ReplayState = {
  at_event: { id: number; event_type: string; actor: string; timestamp: string };
  tender_state_at_time: string;
  matrix_at_time: {
    evaluation_id: string;
    bidder_name: string;
    criterion_text: string;
    verdict: string;
    confidence: number;
    state: string;
    officer_decision: string | null;
  }[];
  stats: {
    cells_existed: number;
    decisions_made_by_then: number;
    decisions_total_now: number;
    pass_at_time: number;
    fail_at_time: number;
    review_at_time: number;
  };
};

export default function AuditReplay({ tenderId }: { tenderId: string }) {
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [selectedEvent, setSelectedEvent] = useState<number | null>(null);
  const [replay, setReplay] = useState<ReplayState | null>(null);
  const [loading, setLoading] = useState(true);
  const [replayLoading, setReplayLoading] = useState(false);

  useEffect(() => {
    api.get(`/tenders/${tenderId}/audit/replay/timeline`)
      .then(res => setTimeline(res.data.timeline))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [tenderId]);

  async function loadReplay(eventId: number) {
    setSelectedEvent(eventId);
    setReplayLoading(true);
    try {
      const res = await api.get(`/tenders/${tenderId}/audit/replay`, { params: { at_event: eventId } });
      setReplay(res.data);
    } catch { setReplay(null); }
    finally { setReplayLoading(false); }
  }

  if (loading) return <div style={{ padding: '16px', fontSize: '12px', color: 'var(--ink-soft)' }}>Loading timeline...</div>;
  if (!timeline.length) return <div style={{ padding: '16px', fontSize: '12px', color: 'var(--ink-soft)' }}>No decision points recorded yet.</div>;

  return (
    <div className="card" style={{ padding: '16px' }}>
      <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--primary)', marginBottom: '4px' }}>
        ⏱ Audit Replay — Time Travel
      </div>
      <div style={{ fontSize: '11px', color: 'var(--ink-soft)', marginBottom: '16px' }}>
        Click any decision point to see the dossier state at that moment.
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: '16px' }}>
        {/* Timeline (left) */}
        <div style={{ maxHeight: '400px', overflow: 'auto', borderRight: '1px solid var(--line)', paddingRight: '12px' }}>
          {timeline.map((evt, i) => (
            <button
              key={evt.event_id}
              onClick={() => loadReplay(evt.event_id)}
              style={{
                display: 'flex', alignItems: 'flex-start', gap: '8px',
                width: '100%', textAlign: 'left',
                padding: '8px', marginBottom: '4px',
                background: selectedEvent === evt.event_id ? 'var(--primary-soft)' : 'transparent',
                border: selectedEvent === evt.event_id ? '1px solid var(--primary)' : '1px solid transparent',
                borderRadius: '4px', cursor: 'pointer',
                transition: 'background 0.12s',
              }}
            >
              {/* Timeline dot + line */}
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flexShrink: 0 }}>
                <div style={{
                  width: '10px', height: '10px', borderRadius: '50%',
                  background: selectedEvent === evt.event_id ? 'var(--primary)' : 'var(--line-strong)',
                  border: '2px solid var(--paper)',
                  boxShadow: selectedEvent === evt.event_id ? '0 0 0 2px var(--primary)' : 'none',
                }} />
                {i < timeline.length - 1 && (
                  <div style={{ width: '2px', height: '20px', background: 'var(--line)', marginTop: '2px' }} />
                )}
              </div>
              <div>
                <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--ink)' }}>{evt.summary}</div>
                <div style={{ fontSize: '9px', color: 'var(--ink-soft)', marginTop: '2px' }}>
                  {evt.actor} · {new Date(evt.timestamp).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                </div>
              </div>
            </button>
          ))}
        </div>

        {/* Replay view (right) */}
        <div>
          {!selectedEvent && (
            <div style={{ padding: '32px', textAlign: 'center', color: 'var(--ink-soft)', fontSize: '12px' }}>
              <Clock size={24} style={{ margin: '0 auto 8px', opacity: 0.4 }} />
              Select a decision point from the timeline to see the dossier state at that moment.
            </div>
          )}

          {replayLoading && (
            <div style={{ padding: '32px', textAlign: 'center', color: 'var(--ink-soft)', fontSize: '12px' }}>
              Reconstructing state...
            </div>
          )}

          {replay && !replayLoading && (
            <div>
              {/* Event info */}
              <div style={{ background: 'var(--bg-soft)', padding: '10px 12px', borderRadius: '4px', marginBottom: '12px' }}>
                <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--ink)' }}>
                  At event #{replay.at_event.id}: {replay.at_event.event_type.replace(/_/g, ' ')}
                </div>
                <div style={{ fontSize: '11px', color: 'var(--ink-soft)', marginTop: '2px' }}>
                  By {replay.at_event.actor} · {new Date(replay.at_event.timestamp).toLocaleString()}
                </div>
                <div style={{ fontSize: '11px', marginTop: '4px' }}>
                  Tender state: <Pill tone="primary">{replay.tender_state_at_time}</Pill>
                </div>
              </div>

              {/* Stats at that time */}
              <div style={{ display: 'flex', gap: '12px', marginBottom: '12px', fontSize: '12px' }}>
                <div style={{ padding: '8px 12px', background: 'var(--success-soft)', borderRadius: '3px' }}>
                  <div style={{ fontWeight: 700, color: 'var(--success)' }}>{replay.stats.pass_at_time}</div>
                  <div style={{ fontSize: '9px', color: 'var(--ink-soft)' }}>PASS</div>
                </div>
                <div style={{ padding: '8px 12px', background: 'var(--danger-soft)', borderRadius: '3px' }}>
                  <div style={{ fontWeight: 700, color: 'var(--danger)' }}>{replay.stats.fail_at_time}</div>
                  <div style={{ fontSize: '9px', color: 'var(--ink-soft)' }}>FAIL</div>
                </div>
                <div style={{ padding: '8px 12px', background: 'var(--warning-soft)', borderRadius: '3px' }}>
                  <div style={{ fontWeight: 700, color: '#856404' }}>{replay.stats.review_at_time}</div>
                  <div style={{ fontSize: '9px', color: 'var(--ink-soft)' }}>REVIEW</div>
                </div>
                <div style={{ padding: '8px 12px', background: 'var(--bg-soft)', borderRadius: '3px' }}>
                  <div style={{ fontWeight: 700, color: 'var(--ink)' }}>{replay.stats.decisions_made_by_then}/{replay.stats.decisions_total_now}</div>
                  <div style={{ fontSize: '9px', color: 'var(--ink-soft)' }}>Decisions</div>
                </div>
              </div>

              {/* Matrix at that time */}
              <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--ink-muted)', marginBottom: '6px', textTransform: 'uppercase' }}>
                Matrix state at this point ({replay.stats.cells_existed} cells)
              </div>
              <div style={{ maxHeight: '250px', overflow: 'auto' }}>
                <table className="govt-table" style={{ fontSize: '10px' }}>
                  <thead>
                    <tr>
                      <th>Bidder</th>
                      <th>Criterion</th>
                      <th>Verdict</th>
                      <th>Conf</th>
                      <th>Officer</th>
                    </tr>
                  </thead>
                  <tbody>
                    {replay.matrix_at_time.slice(0, 20).map(cell => (
                      <tr key={cell.evaluation_id}>
                        <td>{cell.bidder_name.slice(0, 15)}</td>
                        <td>{cell.criterion_text.slice(0, 30)}…</td>
                        <td>
                          <span style={{
                            padding: '1px 4px', borderRadius: '2px', fontSize: '9px', fontWeight: 700,
                            background: cell.verdict === 'PASS' ? 'var(--success-soft)' : cell.verdict === 'FAIL' ? 'var(--danger-soft)' : 'var(--warning-soft)',
                            color: cell.verdict === 'PASS' ? 'var(--success)' : cell.verdict === 'FAIL' ? 'var(--danger)' : '#856404',
                          }}>
                            {cell.verdict}
                          </span>
                        </td>
                        <td>{Math.round(cell.confidence * 100)}%</td>
                        <td>{cell.officer_decision || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
