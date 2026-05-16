// Workspace-wide audit log — proper terminal-style window.
// Sticky filter bar at top, dense rows grouped by day, expand-on-click
// for the full event_data payload + chain hashes.

import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { History, ShieldCheck, ChevronDown, ChevronRight, Search, Filter } from 'lucide-react';
import api from '../api/client';
import Pill from '../components/Pill';
import type { AuditEvent, Tender } from '../types';

type EventWithTender = AuditEvent & { tender_number?: string; title?: string };

const EVENT_GROUPS: Record<string, string> = {
  // tender lifecycle
  tender_created: 'lifecycle',
  tender_metadata_updated: 'lifecycle',
  tender_state_transition: 'lifecycle',
  tender_deleted: 'lifecycle',
  // documents
  document_received: 'document',
  document_processed: 'document',
  document_failed: 'document',
  // criteria
  criteria_extracted: 'criteria',
  criterion_edited: 'criteria',
  criterion_version_created: 'criteria',
  criteria_approved: 'criteria',
  criterion_amended: 'criteria',
  // bidders + verification
  bidder_registered: 'bidder',
  bidder_excluded: 'bidder',
  bidder_emd_recorded: 'bidder',
  bidder_debarment_checked: 'bidder',
  verification_run: 'verification',
  // evaluation
  evaluation_computed: 'evaluation',
  evaluation_decided: 'evaluation',
  second_officer_decided: 'evaluation',
  concurrence_requested: 'evaluation',
  concurrence_decided: 'evaluation',
  anomaly_flagged: 'evaluation',
  anomaly_dismissed: 'evaluation',
  evidence_citation_recorded: 'evaluation',
  officer_comment_added: 'human',
  post_review_check_answered: 'human',
  // hitl + studio
  tec_draft_generated: 'human',
  tec_section_authored: 'human',
  tec_section_revised: 'human',
  tec_report_finalised: 'human',
  studio_doc_created: 'human',
  studio_doc_message: 'human',
  studio_doc_finalised: 'human',
  // reports / vault
  report_generated: 'report',
  report_signed: 'report',
  brief_generated: 'report',
  vault_generated: 'report',
  reproduce_attempted: 'report',
  // chat / replay
  copilot_message: 'chat',
  decision_replay_captured: 'chat',
  // checklist
  checklist_extracted: 'checklist',
  checklist_response_decided: 'checklist',
  preliminary_finalised: 'checklist',
  // corrigenda
  corrigendum_received: 'corrigendum',
  corrigendum_summarised: 'corrigendum',
  corrigendum_applied: 'corrigendum',
  corrigendum_rejected: 'corrigendum',
};

const GROUP_TONES: Record<string, 'primary' | 'success' | 'danger' | 'warning' | 'soft'> = {
  lifecycle:    'primary',
  document:     'soft',
  criteria:     'soft',
  bidder:       'soft',
  verification: 'success',
  evaluation:   'warning',
  human:        'success',
  report:       'primary',
  chat:         'soft',
  checklist:    'soft',
  corrigendum:  'warning',
};

export default function AuditLog() {
  const [tenders, setTenders] = useState<Tender[]>([]);
  const [events, setEvents] = useState<EventWithTender[]>([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState('');
  const [tenderFilter, setTenderFilter] = useState<string>('');
  const [groupFilter, setGroupFilter] = useState<string>('');
  const [openId, setOpenId] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const ts = (await api.get('/tenders')).data.tenders as Tender[];
        if (!mounted) return;
        setTenders(ts);
        // Pull most-recent 80 per tender; merge.
        const all: EventWithTender[] = [];
        for (const t of ts) {
          try {
            const r = await api.get(`/tenders/${t.id}/audit`, {
              params: { limit: 80, order: 'desc' },
            });
            const items: AuditEvent[] = r.data.items || [];
            items.forEach(e => all.push({ ...e, tender_number: t.tender_number, title: t.title }));
          } catch { /* ignore per-tender failures */ }
        }
        all.sort((a, b) => (a.timestamp < b.timestamp ? 1 : -1));
        if (mounted) setEvents(all);
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => { mounted = false; };
  }, []);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return events.filter(e => {
      if (tenderFilter && e.tender_id !== tenderFilter) return false;
      const grp = EVENT_GROUPS[e.event_type] || 'other';
      if (groupFilter && grp !== groupFilter) return false;
      if (!needle) return true;
      const hay = `${e.event_type} ${e.actor} ${e.tender_number || ''} ${JSON.stringify(e.event_data || '')}`.toLowerCase();
      return hay.includes(needle);
    });
  }, [events, q, tenderFilter, groupFilter]);

  // Group by day
  const byDay = useMemo(() => {
    const m = new Map<string, EventWithTender[]>();
    for (const e of filtered) {
      const day = new Date(e.timestamp).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });
      if (!m.has(day)) m.set(day, []);
      m.get(day)!.push(e);
    }
    return Array.from(m.entries());
  }, [filtered]);

  const groups = Array.from(new Set(Object.values(EVENT_GROUPS))).sort();

  return (
    <div
      className="hero-gradient flex flex-col"
      style={{
        position: 'absolute',
        top: 0, bottom: 0, left: 0, right: 0,
        overflow: 'hidden',
      }}
    >
      {/* Pinned header */}
      <div className="px-6 pt-8 pb-4 flex-shrink-0">
        <div className="hero-eyebrow flex items-center gap-2 mx-auto max-w-[1200px]">
          <History size={12} /> Workspace audit log
        </div>
        <h1
          className="font-display italic font-semibold mx-auto max-w-[1200px] mt-2"
          style={{
            fontSize: 'clamp(22px, 2.4vw, 30px)',
            lineHeight: 1.15,
            letterSpacing: '-0.015em',
            fontVariationSettings: "'opsz' 144, 'SOFT' 50",
            color: 'var(--ink)',
            margin: 0,
          }}
        >
          Every action this office has taken, hash-linked.
        </h1>

        {/* Filter bar */}
        <div className="card mt-4 mx-auto max-w-[1200px]" style={{ position: 'relative', zIndex: 5 }}>
          <div className="flex flex-wrap items-center gap-2 px-3 py-2">
            <div className="flex items-center gap-2 flex-1 min-w-[260px]">
              <Search size={14} className="text-ink-soft" />
              <input
                className="input border-0 bg-transparent flex-1 py-1"
                placeholder="Search by event, actor, or payload…"
                value={q}
                onChange={e => setQ(e.target.value)}
                aria-label="Search audit log"
              />
            </div>
            <div className="flex items-center gap-2">
              <Filter size={12} className="text-ink-soft" />
              <select
                className="select py-1 text-xs"
                value={tenderFilter}
                onChange={e => setTenderFilter(e.target.value)}
                aria-label="Filter by dossier"
              >
                <option value="">All dossiers</option>
                {tenders.map(t => (
                  <option key={t.id} value={t.id}>{t.tender_number}</option>
                ))}
              </select>
              <select
                className="select py-1 text-xs"
                value={groupFilter}
                onChange={e => setGroupFilter(e.target.value)}
                aria-label="Filter by event group"
              >
                <option value="">All event types</option>
                {groups.map(g => (
                  <option key={g} value={g}>{g}</option>
                ))}
              </select>
            </div>
            <Pill tone="success">
              <ShieldCheck size={11} /> append-only
            </Pill>
          </div>
        </div>

        <div className="mx-auto max-w-[1200px] mt-2 text-[11px] text-ink-soft mono flex items-center gap-3">
          <span>{loading ? 'Loading…' : `${filtered.length} of ${events.length} events`}</span>
          <span>·</span>
          <span>{tenders.length} dossiers</span>
        </div>
      </div>

      {/* Terminal-style scrolling event window */}
      <div className="flex-1 min-h-0 mx-auto max-w-[1200px] w-full px-6 pb-6">
        <div
          className="card overflow-y-auto h-full"
          style={{ paddingTop: 0, paddingBottom: 0 }}
        >
          {filtered.length === 0 && !loading && (
            <div className="empty py-10">
              <div className="font-display italic text-lg text-ink mb-1">No matching events.</div>
              <div className="text-sm">Try clearing the filters.</div>
            </div>
          )}

          {byDay.map(([day, dayEvents]) => (
            <div key={day}>
              <div
                className="sticky top-0 px-4 py-2 text-[10px] font-bold uppercase tracking-[0.12em] text-ink-faint bg-paper border-b border-line z-[1]"
                style={{ background: 'var(--paper)' }}
              >
                {day} · {dayEvents.length} {dayEvents.length === 1 ? 'event' : 'events'}
              </div>
              {dayEvents.map(e => {
                const key = `${e.tender_id}-${e.id}`;
                const isOpen = openId === key;
                const grp = EVENT_GROUPS[e.event_type] || 'other';
                const tone = GROUP_TONES[grp] || 'soft';
                return (
                  <div key={key} className="border-b border-line last:border-0">
                    <button
                      type="button"
                      onClick={() => setOpenId(isOpen ? null : key)}
                      className="w-full grid grid-cols-[14px_92px_140px_minmax(0,1fr)_120px] items-center gap-3 px-4 py-2 text-left hover:bg-bg-soft transition-colors"
                    >
                      {isOpen
                        ? <ChevronDown size={12} className="text-ink-soft" />
                        : <ChevronRight size={12} className="text-ink-soft" />}
                      <span className="mono text-[11px] text-ink-soft">
                        {new Date(e.timestamp).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                      </span>
                      <Pill tone={tone}>{e.event_type.replace(/_/g, ' ')}</Pill>
                      <span className="text-sm text-ink truncate">
                        {summarise(e)}
                      </span>
                      <span className="mono text-[10px] text-ink-faint truncate text-right" title={e.entry_hash}>
                        {e.entry_hash.slice(0, 12)}…
                      </span>
                    </button>
                    {isOpen && (
                      <div className="px-12 pb-3 pt-1 text-xs">
                        <div className="grid grid-cols-[120px_1fr] gap-2 mb-2">
                          <span className="text-ink-soft">actor</span>
                          <span className="mono">{e.actor}</span>
                          <span className="text-ink-soft">tender</span>
                          <Link
                            to={`/tenders/${e.tender_id}/audit`}
                            className="text-primary hover:underline truncate"
                          >
                            {e.tender_number} · {e.title}
                          </Link>
                          <span className="text-ink-soft">prev hash</span>
                          <span className="mono text-[10px] text-ink-soft truncate" title={e.prev_hash}>{e.prev_hash}</span>
                          <span className="text-ink-soft">entry hash</span>
                          <span className="mono text-[10px] text-ink truncate" title={e.entry_hash}>{e.entry_hash}</span>
                        </div>
                        <pre
                          className="mono text-[11px] bg-bg-sunk rounded p-3 overflow-x-auto whitespace-pre-wrap"
                          style={{ color: 'var(--ink-muted)' }}
                        >
                          {JSON.stringify(e.event_data, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── One-line summary of an event for the table row ──────────────────

function summarise(e: EventWithTender): string {
  const d = (e.event_data || {}) as Record<string, any>;
  const t = e.event_type;
  if (t === 'officer_comment_added') {
    return `Note added on evaluation ${shortId(d.evaluation_id)}`;
  }
  if (t === 'evaluation_decided') {
    return `Verdict ${d.decision || ''} on evaluation ${shortId(d.evaluation_id)}`;
  }
  if (t === 'concurrence_requested' || t === 'concurrence_decided') {
    return `${t === 'concurrence_decided' ? 'Concurrence ' + (d.decision || '') : 'Concurrence requested'} (req ${shortId(d.request_id)})`;
  }
  if (t === 'document_received' || t === 'document_processed') {
    return `${d.filename || 'document'} (${d.doc_type || ''})`;
  }
  if (t === 'criteria_extracted') {
    return `${d.count || '?'} criteria extracted`;
  }
  if (t === 'criterion_edited' || t === 'criterion_version_created') {
    return `Criterion ${shortId(d.criterion_id)} → version ${d.version || d.new_version || '?'}`;
  }
  if (t === 'bidder_registered') {
    return `${d.company_name || 'Bidder'} registered`;
  }
  if (t === 'verification_run') {
    return `${d.bidder_count || '?'} bidders verified across ${d.verifier_count || '?'} authorities`;
  }
  if (t === 'tec_section_authored' || t === 'tec_section_revised') {
    return `Section "${d.section_key || '?'}" — ${d.change_source || d.authored_by || 'change'}`;
  }
  if (t === 'tec_report_finalised') {
    return `TEC report sealed (${d.section_count || '?'} sections, ${d.co_authored_count || 0} co-authored)`;
  }
  if (t === 'studio_doc_created' || t === 'studio_doc_finalised') {
    return `Studio: "${d.title || ''}"`;
  }
  if (t === 'studio_doc_message') {
    return `Studio message${d.body_updated ? ' (doc updated)' : ''}`;
  }
  if (t === 'report_generated' || t === 'vault_generated') {
    return `${shortHash(d.sha256_hash)} · ${d.section_count ? d.section_count + ' sections' : ''}`;
  }
  if (t === 'tender_created' || t === 'tender_state_transition') {
    return `state → ${d.target_state || d.state || '?'}`;
  }
  if (t === 'anomaly_flagged') {
    return `${d.flag_type || ''} (${d.severity || ''})`;
  }
  // fallback: first scalar field
  for (const [k, v] of Object.entries(d)) {
    if (typeof v === 'string' && v.length < 80) return `${k}: ${v}`;
  }
  return e.event_type;
}

function shortId(id?: string): string {
  if (!id) return '—';
  return id.slice(0, 8);
}
function shortHash(h?: string): string {
  if (!h) return '';
  return h.slice(0, 12) + '…';
}
