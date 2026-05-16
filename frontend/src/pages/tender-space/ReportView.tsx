// Report step — co-authored TEC report, Defence Vault, audit verification.
//
// The hero is the co-author flow. Officer clicks "Open draft" → backend
// composes the section blueprint, AI drafts each section. Officer
// edits inline, regenerates a section, finalises to PDF. Every edit
// goes into an append-only revision trail, every paragraph carries an
// authored_by chip ('AI draft' / 'Co-authored' / 'Officer-authored').

import { useEffect, useState } from 'react';
import {
  Download, Loader, ShieldCheck, Archive, Package,
  Edit3, RefreshCw, Save, X, Sparkles, Lock, History, MessageSquare,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { reportsApi, auditApi, vaultApi, tecDraftApi } from '../../api/endpoints';
import type { Report, Tender, Vault, TecDraft, TecSection, TecSectionRevision } from '../../types';
import { Card, CardBody, CardHeader } from '../../components/Card';
import Button from '../../components/Button';
import Pill from '../../components/Pill';
import Drawer from '../../components/Drawer';
import { useToast } from '../../components/Toast';
import { prefillCopilot } from '../../lib/copilotBridge';

type Props = { tender: Tender; onChanged: () => void };

export default function ReportView({ tender, onChanged }: Props) {
  const [reports, setReports] = useState<Report[]>([]);
  const [vaults, setVaults] = useState<Vault[]>([]);
  const [verified, setVerified] = useState<{ ok: boolean; error: string | null } | null>(null);
  const [draft, setDraft] = useState<TecDraft | null>(null);
  const [sections, setSections] = useState<TecSection[]>([]);
  const [opening, setOpening] = useState(false);
  const [vaultBusy, setVaultBusy] = useState(false);
  const [finalising, setFinalising] = useState(false);
  const toast = useToast();

  const refresh = () => Promise.all([
    reportsApi.list(tender.id),
    auditApi.verify(tender.id),
    vaultApi.list(tender.id),
    tecDraftApi.get(tender.id),
  ]).then(([r, v, vlt, d]) => {
    setReports(r); setVerified(v); setVaults(vlt);
    setDraft(d.draft); setSections(d.sections);
  });

  useEffect(() => { refresh(); }, [tender.id]);

  async function openDraft() {
    setOpening(true);
    try {
      const d = await tecDraftApi.generate(tender.id, true);
      setDraft(d.draft); setSections(d.sections);
      toast(`Draft ready — ${d.sections.length} sections.`, 'success');
    } catch (e) {
      toast((e as Error).message, 'error');
    } finally {
      setOpening(false);
    }
  }

  async function finaliseDraft() {
    if (!draft) return;
    setFinalising(true);
    try {
      const result = await tecDraftApi.finalise(draft.id);
      toast('TEC report finalised. PDF + audit row written.', 'success');
      onChanged();
      await refresh();
      // open the freshly written PDF
      window.open(reportsApi.downloadUrl(result.report_id), '_blank');
    } catch (e) {
      toast((e as Error).message, 'error');
    } finally {
      setFinalising(false);
    }
  }

  async function generateVault() {
    setVaultBusy(true);
    try {
      const v = await vaultApi.generate(tender.id);
      toast(
        `Defence Vault sealed (${(v.file_size_bytes / 1024).toFixed(0)} KB · ${v.manifest.files.length} files).`,
        'success',
      );
      onChanged();
      await refresh();
      window.open(vaultApi.downloadUrl(v.id), '_blank');
    } catch (e) {
      toast((e as Error).message, 'error');
    } finally { setVaultBusy(false); }
  }

  // Authored-by counts for the draft header
  const aiCount = sections.filter(s => s.authored_by === 'ai').length;
  const coCount = sections.filter(s => s.authored_by === 'co-authored').length;
  const offCount = sections.filter(s => s.authored_by === 'officer').length;

  return (
    <div className="space-y-5">
      {/* ── Hero: co-authored TEC draft ──────────────────────────── */}
      <Card>
        <CardHeader
          title={
            <span className="flex items-center gap-2 font-display">
              <Edit3 size={16} className="text-primary" />
              Tender Evaluation Committee report — co-author
            </span>
          }
          subtitle={
            draft
              ? `${sections.length} sections · AI ${aiCount} · co-authored ${coCount} · officer ${offCount}`
              : "AI drafts each section. You edit, regenerate, accept. The PDF that's signed is the one you finalise."
          }
          actions={
            !draft ? (
              <Button variant="primary" icon={<Sparkles size={14} />} onClick={openDraft} disabled={opening}>
                {opening ? <><Loader size={14} className="animate-spin" /> Drafting…</> : 'Open draft'}
              </Button>
            ) : (
              <div className="flex items-center gap-2">
                <Button variant="ghost" size="sm" icon={<MessageSquare size={13} />}
                  onClick={() => prefillCopilot(
                    `I want to improve the TEC report. Consider my comments and evaluation context. What should I change?`
                  )}
                  title="Discuss report with Copilot"
                >
                  Copilot
                </Button>
                <Button variant="ghost" size="sm" icon={<RefreshCw size={13} />} onClick={refresh} title="Refresh">
                  Refresh
                </Button>
                <Button
                  variant="success"
                  icon={<Lock size={14} />}
                  onClick={finaliseDraft}
                  disabled={finalising || sections.length === 0}
                >
                  {finalising ? <><Loader size={14} className="animate-spin" /> Sealing…</> : 'Finalise & sign'}
                </Button>
              </div>
            )
          }
        />
        <CardBody>
          {!draft && (
            <div className="text-sm text-ink-soft">
              Your space to think with the AI, not just consume its output. Each section
              starts as an AI draft; rewrite anything that's wrong; ask for a redraft when
              the tone is off. Every edit is recorded in an append-only revision trail.
            </div>
          )}
          {draft && sections.length === 0 && (
            <div className="empty">No sections yet — try Open draft again.</div>
          )}
          {draft && sections.length > 0 && (
            <ul className="space-y-3">
              {sections.map(s => (
                <SectionCard
                  key={s.id}
                  section={s}
                  onSaved={refresh}
                />
              ))}
            </ul>
          )}
        </CardBody>
      </Card>

      {/* ── Finalised PDFs ───────────────────────────────────────── */}
      {reports.length > 0 && (
        <Card>
          <CardHeader title="Finalised PDFs" subtitle="Signed and hash-stamped." />
          <CardBody>
            <ul className="space-y-2">
              {reports.map(r => (
                <li key={r.id} className="flex items-center justify-between border border-line rounded-md p-3">
                  <div className="text-sm">
                    <div className="font-semibold text-ink">{r.file_path.split('/').pop()}</div>
                    <div className="text-xs text-ink-soft mono mt-0.5">
                      sha256 {r.sha256_hash.slice(0, 16)}… · {new Date(r.generated_at).toLocaleString()}
                    </div>
                  </div>
                  <a
                    href={reportsApi.downloadUrl(r.id)}
                    target="_blank"
                    rel="noopener"
                    className="btn btn-ghost btn-sm"
                    title="Download PDF"
                  >
                    <Download size={14} /> Download
                  </a>
                </li>
              ))}
            </ul>
          </CardBody>
        </Card>
      )}

      {/* ── Defence Vault ────────────────────────────────────────── */}
      <Card className="card-pop">
        <CardHeader
          title={
            <span className="flex items-center gap-2 font-display">
              <Archive size={16} className="text-primary" />
              Defence Vault
            </span>
          }
          subtitle="One-click sealed evidence package. Hash-signed manifest. Offline-verifiable."
          actions={
            <Button variant="success" icon={<Package size={14} />} onClick={generateVault} disabled={vaultBusy}>
              {vaultBusy ? <><Loader size={14} className="animate-spin" /> Sealing…</> : 'Generate vault'}
            </Button>
          }
        />
        <CardBody>
          {vaults.length === 0 ? (
            <div className="text-sm text-ink-soft">
              No vault yet. Generate one to send to CVC, CAG, or attach to a future inquiry.
              The vault is a self-contained ZIP — anyone with the file can verify the audit chain
              and replay every evaluation.
            </div>
          ) : (
            <ul className="space-y-2">
              {vaults.map(v => (
                <li key={v.id} className="flex items-center justify-between border border-line rounded-md p-3">
                  <div className="text-sm">
                    <div className="font-semibold text-ink">{v.file_path.split('/').pop()}</div>
                    <div className="text-xs text-ink-soft mono mt-0.5">
                      sha256 {v.sha256_hash.slice(0, 16)}… ·
                      &nbsp;{(v.file_size_bytes / 1024).toFixed(0)} KB ·
                      &nbsp;{v.manifest.files.length} files ·
                      &nbsp;{new Date(v.generated_at).toLocaleString()}
                    </div>
                  </div>
                  <a
                    href={vaultApi.downloadUrl(v.id)}
                    target="_blank"
                    rel="noopener"
                    className="btn btn-ghost btn-sm"
                  >
                    <Download size={14} /> Download
                  </a>
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>

      {/* ── Audit verification ───────────────────────────────────── */}
      <Card>
        <CardHeader
          title={
            <span className="flex items-center gap-2">
              <ShieldCheck size={16} className="text-success" />
              Audit chain verification
            </span>
          }
          subtitle="Re-walks every event, recomputes hashes, verifies linkage."
          actions={
            verified
              ? (verified.ok
                ? <Pill tone="success">Verified</Pill>
                : <Pill tone="danger">Tampered</Pill>)
              : null
          }
        />
        <CardBody>
          {verified?.error && <div className="text-sm text-danger">{verified.error}</div>}
          {verified?.ok && <div className="text-sm text-ink-soft">Every audit event is intact.</div>}
        </CardBody>
      </Card>
    </div>
  );
}

// ─── Per-section editable card ───────────────────────────────────────

function SectionCard({
  section,
  onSaved,
}: {
  section: TecSection;
  onSaved: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [body, setBody] = useState(section.body);
  const [saving, setSaving] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [revisions, setRevisions] = useState<TecSectionRevision[]>([]);
  const toast = useToast();

  useEffect(() => { setBody(section.body); }, [section.body, section.id]);

  const author = section.authored_by;
  const authorTone =
    author === 'ai' ? 'soft'
    : author === 'co-authored' ? 'success'
    : 'primary';
  const authorLabel =
    author === 'ai' ? 'AI draft'
    : author === 'co-authored' ? 'Co-authored'
    : 'Officer-authored';

  async function save() {
    if (body.trim() === (section.body || '').trim()) {
      setEditing(false);
      return;
    }
    setSaving(true);
    try {
      await tecDraftApi.reviseSection(section.id, body);
      toast('Section saved.', 'success');
      setEditing(false);
      onSaved();
    } catch (e) {
      toast((e as Error).message, 'error');
    } finally {
      setSaving(false);
    }
  }

  async function regenerate() {
    setRegenerating(true);
    try {
      await tecDraftApi.regenerateSection(section.id);
      toast('AI re-drafted this section.', 'success');
      onSaved();
    } catch (e) {
      toast((e as Error).message, 'error');
    } finally {
      setRegenerating(false);
    }
  }

  async function openHistory() {
    setHistoryOpen(true);
    try {
      const revs = await tecDraftApi.revisions(section.id);
      setRevisions(revs);
    } catch (e) {
      toast((e as Error).message, 'error');
    }
  }

  return (
    <li className="border border-line rounded-md p-3 bg-bg">
      <div className="flex items-center gap-2 mb-2">
        <div className="text-sm font-semibold text-ink">{section.section_label}</div>
        <Pill tone={authorTone}>{authorLabel}</Pill>
        <div className="ml-auto flex items-center gap-1">
          {!editing && (
            <>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => setEditing(true)}
                title="Edit this section"
              >
                <Edit3 size={12} /> Edit
              </button>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={regenerate}
                disabled={regenerating}
                title="Ask AI to re-draft"
              >
                {regenerating
                  ? <Loader size={12} className="animate-spin" />
                  : <RefreshCw size={12} />}
                Regenerate
              </button>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => prefillCopilot(
                  `Help me improve the "${section.section_label}" section. `
                )}
                title="Discuss this section with Copilot"
              >
                <MessageSquare size={12} /> Copilot
              </button>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={openHistory}
                title="Revision history"
              >
                <History size={12} /> History
              </button>
            </>
          )}
        </div>
      </div>

      {!editing ? (
        <div className="ai-md text-sm">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{section.body}</ReactMarkdown>
        </div>
      ) : (
        <div className="space-y-2">
          <textarea
            className="textarea text-sm font-mono"
            value={body}
            onChange={e => setBody(e.target.value)}
            rows={Math.max(8, body.split('\n').length + 2)}
          />
          <div className="flex items-center gap-2">
            <Button
              variant="success"
              size="sm"
              icon={<Save size={12} />}
              onClick={save}
              disabled={saving}
            >
              {saving ? 'Saving…' : 'Save'}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              icon={<X size={12} />}
              onClick={() => { setBody(section.body); setEditing(false); }}
            >
              Cancel
            </Button>
            <span className="text-xs text-ink-soft ml-auto">
              Markdown supported · revision is append-only
            </span>
          </div>
        </div>
      )}

      <Drawer
        open={historyOpen}
        onClose={() => setHistoryOpen(false)}
        title={`Revision history — ${section.section_label}`}
        width="min(720px, 90vw)"
      >
        <div className="px-5 py-4 space-y-3">
          {revisions.length === 0 && <div className="empty">Loading…</div>}
          {revisions.map(r => (
            <div key={r.id} className="border border-line rounded-md p-3">
              <div className="flex items-center gap-2 text-xs text-ink-soft">
                <Pill tone={r.change_source.startsWith('ai') ? 'soft' : 'primary'}>
                  {r.change_source.replace('_', ' ')}
                </Pill>
                <span>rev {r.revision}</span>
                <span className="ml-auto mono">{new Date(r.edited_at).toLocaleString()}</span>
              </div>
              {r.diff_summary && (
                <div className="text-xs text-ink-muted mt-1">{r.diff_summary}</div>
              )}
              <div className="text-xs text-ink mt-2 whitespace-pre-wrap line-clamp-6">
                {r.body_after}
              </div>
            </div>
          ))}
        </div>
      </Drawer>
    </li>
  );
}
