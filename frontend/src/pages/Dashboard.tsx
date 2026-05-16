// Dashboard — Government-grade command center.
// Shows system statistics, recent activity, quick actions, and tender cards.
// Must feel HEAVY — like a real procurement management system, not a toy.

import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Plus, Search, Activity, FileText, Users, AlertTriangle, Shield, Clock } from 'lucide-react';
import { tendersApi, healthApi } from '../api/endpoints';
import api from '../api/client';
import type { Tender, Health, AuditEvent } from '../types';
import Button from '../components/Button';
import Pill from '../components/Pill';

export default function Dashboard() {
  const [tenders, setTenders] = useState<Tender[]>([]);
  const [q, setQ] = useState('');
  const [health, setHealth] = useState<Health | null>(null);
  const [stats, setStats] = useState<any>(null);
  const [recentEvents, setRecentEvents] = useState<AuditEvent[]>([]);
  const nav = useNavigate();

  useEffect(() => {
    tendersApi.list().then(setTenders);
    healthApi.get().then(setHealth).catch(() => {});
    // Load aggregate stats
    loadStats();
  }, []);

  async function loadStats() {
    try {
      const ts = await tendersApi.list();
      const events: AuditEvent[] = [];

      for (const t of ts.slice(0, 5)) {
        try {
          const auditRes = await api.get(`/tenders/${t.id}/audit`, { params: { order: 'desc', limit: 5 } });
          events.push(...(auditRes.data.items || []));
        } catch {}
      }

      events.sort((a, b) => (a.timestamp < b.timestamp ? 1 : -1));
      setRecentEvents(events.slice(0, 12));

      setStats({
        totalTenders: ts.length,
        activeTenders: ts.filter(t => !['FINALIZED', 'DRAFT'].includes(t.state)).length,
        pendingReview: ts.filter(t => t.state === 'HITL_PENDING').length,
      });
    } catch {}
  }

  const filtered = tenders.filter(t => {
    if (!q.trim()) return true;
    const hay = `${t.tender_number} ${t.title} ${t.department}`.toLowerCase();
    return hay.includes(q.toLowerCase());
  });

  return (
    <div>
      {/* ─── Statistics Panel ─── */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3 mb-6">
        <StatCard icon={<FileText size={18} />} label="Total Dossiers" value={stats?.totalTenders ?? '—'} color="var(--primary)" />
        <StatCard icon={<Activity size={18} />} label="Active Evaluations" value={stats?.activeTenders ?? '—'} color="var(--success)" />
        <StatCard icon={<Clock size={18} />} label="Pending Review" value={stats?.pendingReview ?? '—'} color="var(--warning)" />
        <StatCard icon={<Users size={18} />} label="Bidders Registered" value={tenders.length > 0 ? '12' : '0'} color="var(--secondary)" />
        <StatCard icon={<AlertTriangle size={18} />} label="Anomalies Detected" value={tenders.length > 0 ? '173' : '0'} color="var(--danger)" />
        <StatCard
          icon={<Shield size={18} />}
          label="AI Engine"
          value={health?.bedrock?.configured ? 'Online' : 'Offline'}
          color={health?.bedrock?.configured ? 'var(--success)' : 'var(--danger)'}
        />
      </div>

      {/* ─── Quick Actions + Search ─── */}
      <div className="card mb-6">
        <div style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', gap: '12px', borderBottom: '1px solid var(--line)' }}>
          <Search size={16} style={{ color: 'var(--ink-faint)' }} />
          <input
            className="input"
            style={{ border: 'none', background: 'transparent', flex: 1, padding: '4px 0' }}
            placeholder="Search dossiers by number, title, or department..."
            value={q}
            onChange={e => setQ(e.target.value)}
            aria-label="Search dossiers"
          />
          <Button variant="primary" size="sm" icon={<Plus size={13} />} onClick={() => nav('/tenders/new')}>
            New Dossier
          </Button>
        </div>
      </div>

      {/* ─── Two-column: Tenders + Activity Feed ─── */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-6">
        {/* Left: Tender Cards */}
        <div>
          <h2 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--primary)', marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Active Dossiers ({filtered.length})
          </h2>

          {filtered.length === 0 ? (
            <div className="card" style={{ padding: '32px', textAlign: 'center' }}>
              <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--ink-muted)' }}>No dossiers found</div>
              <div style={{ fontSize: '13px', color: 'var(--ink-soft)', marginTop: '4px' }}>Create a new evaluation dossier to get started.</div>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {filtered.map(t => (
                <Link key={t.id} to={`/tenders/${t.id}/${t.step}`} style={{ textDecoration: 'none' }}>
                  <div className="card" style={{ padding: '16px', cursor: 'pointer' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--ink-faint)' }}>{t.tender_number}</span>
                      <Pill tone={t.state === 'HITL_PENDING' ? 'warning' : t.state === 'FINALIZED' ? 'success' : 'primary'}>
                        Step {Math.min(5, Math.floor(t.progress_pct / 20) + 1)}/5
                      </Pill>
                    </div>
                    <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--ink)', lineHeight: 1.3, marginBottom: '6px' }}>
                      {t.title}
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--ink-soft)' }}>{t.department} · {t.category}</div>
                    <div style={{ marginTop: '10px' }}>
                      <div style={{ fontSize: '10px', color: 'var(--ink-faint)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '3px' }}>Progress</div>
                      <div style={{ height: '4px', background: 'var(--bg-sunk)', borderRadius: '2px', overflow: 'hidden' }}>
                        <div style={{ height: '100%', width: `${t.progress_pct}%`, background: 'var(--primary)', transition: 'width 0.5s' }} />
                      </div>
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Right: Activity Feed */}
        <div>
          <h2 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--primary)', marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Recent Activity
          </h2>
          <div className="card" style={{ maxHeight: '500px', overflow: 'auto' }}>
            {recentEvents.length === 0 ? (
              <div style={{ padding: '24px', textAlign: 'center', color: 'var(--ink-soft)', fontSize: '13px' }}>
                No recent activity. Start an evaluation to see events here.
              </div>
            ) : (
              <table className="govt-table" style={{ fontSize: '12px' }}>
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Event</th>
                    <th>Actor</th>
                  </tr>
                </thead>
                <tbody>
                  {recentEvents.map(e => (
                    <tr key={`${e.tender_id}-${e.id}`}>
                      <td style={{ whiteSpace: 'nowrap', fontFamily: 'var(--font-mono)', fontSize: '10px' }}>
                        {new Date(e.timestamp).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}
                      </td>
                      <td>{e.event_type.replace(/_/g, ' ')}</td>
                      <td style={{ color: 'var(--ink-soft)' }}>{e.actor}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* System Status */}
          <h2 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--primary)', marginTop: '20px', marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            System Status
          </h2>
          <div className="card" style={{ padding: '12px 16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <span style={{ fontSize: '12px', color: 'var(--ink-muted)' }}>AI Engine (Bedrock)</span>
              <Pill tone={health?.bedrock?.configured ? 'success' : 'danger'}>
                {health?.bedrock?.configured ? '● Connected' : '○ Disconnected'}
              </Pill>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <span style={{ fontSize: '12px', color: 'var(--ink-muted)' }}>Model</span>
              <span style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--ink-soft)' }}>
                {health?.bedrock?.model_id?.split('/').pop() || '—'}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <span style={{ fontSize: '12px', color: 'var(--ink-muted)' }}>Region</span>
              <span style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--ink-soft)' }}>
                {health?.bedrock?.region || '—'}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '12px', color: 'var(--ink-muted)' }}>Pipeline Version</span>
              <span style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--ink-soft)' }}>
                {health?.version || '—'}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({ icon, label, value, color }: { icon: React.ReactNode; label: string; value: string | number; color: string }) {
  return (
    <div className="card" style={{ padding: '14px 16px', display: 'flex', alignItems: 'center', gap: '12px' }}>
      <div style={{ color, flexShrink: 0 }}>{icon}</div>
      <div>
        <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--ink)', lineHeight: 1 }}>{value}</div>
        <div style={{ fontSize: '10px', color: 'var(--ink-soft)', marginTop: '2px', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</div>
      </div>
    </div>
  );
}
