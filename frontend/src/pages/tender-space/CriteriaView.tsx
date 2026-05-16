// Criteria step — list, edit inline, approve, view source clause.

import { useEffect, useState } from 'react';
import { CheckCircle2, Pencil, Save, X, ArrowRight } from 'lucide-react';
import { criteriaApi, tendersApi, evaluationsApi, checklistApi, biddersApi } from '../../api/endpoints';
import type { Criterion, Tender } from '../../types';
import { Card, CardBody, CardHeader } from '../../components/Card';
import Button from '../../components/Button';
import Pill from '../../components/Pill';
import SourcePill from '../../components/SourcePill';
import Drawer from '../../components/Drawer';
import PDFViewer from '../../components/PDFViewer';
import { useToast } from '../../components/Toast';

type Props = { tender: Tender; onChanged: () => void };

export default function CriteriaView({ tender, onChanged }: Props) {
  const [criteria, setCriteria] = useState<Criterion[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [edit, setEdit] = useState<{ text: string; mandatory: boolean }>({ text: '', mandatory: false });
  const [sourceOpen, setSourceOpen] = useState<{ doc_id: string; page: number } | null>(null);
  const [busy, setBusy] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const toast = useToast();

  const refresh = () => criteriaApi.list(tender.id).then(setCriteria);
  useEffect(() => { refresh(); }, [tender.id]);

  async function extractCriteria() {
    setExtracting(true);
    try {
      toast('Extracting criteria from NIT (AI call — may take 30-60s)…');
      await criteriaApi.extract(tender.id);
      toast('Criteria extracted successfully!', 'success');
      await refresh();
      onChanged();
    } catch (e) {
      toast(`Extraction failed: ${(e as Error).message}`, 'error');
    } finally {
      setExtracting(false);
    }
  }

  function startEdit(c: Criterion) {
    setEditingId(c.id);
    setEdit({ text: c.criterion_text, mandatory: c.is_mandatory });
  }
  async function saveEdit() {
    if (!editingId) return;
    try {
      await criteriaApi.update(editingId, { criterion_text: edit.text, is_mandatory: edit.mandatory });
      toast('Criterion updated.', 'success');
      setEditingId(null);
      refresh();
    } catch (e) {
      toast((e as Error).message, 'error');
    }
  }

  async function approveAll() {
    setBusy(true);
    try {
      await criteriaApi.approveAll(tender.id);
      toast('All criteria approved.', 'success');
      // Move to CHECKLIST_PENDING and run auto-match for each bidder
      try { await tendersApi.transition(tender.id, 'CHECKLIST_PENDING'); } catch {/* ignore */}
      const bidders = await biddersApi.list(tender.id);
      for (const b of bidders) {
        try { await checklistApi.autoMatch(tender.id, b.id); } catch {/* ignore */}
      }
      try { await checklistApi.finalize(tender.id); } catch {/* ignore */}
      // Then run the actual evaluation
      toast('Running evaluation across bidders × criteria …');
      await evaluationsApi.run(tender.id);
      toast('Evaluation complete.', 'success');
      onChanged();
      window.location.href = `/tenders/${tender.id}/evaluation`;
    } catch (e) {
      toast((e as Error).message, 'error');
    } finally {
      setBusy(false);
    }
  }

  const total = criteria.length;
  const approved = criteria.filter(c => c.state === 'approved').length;

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader
          title="Eligibility criteria"
          subtitle={`${approved} of ${total} criteria approved · all are AI-extracted from the NIT.`}
          actions={
            <div className="flex items-center gap-2">
              <Button
                variant="primary"
                icon={extracting ? <ArrowRight size={14} className="animate-spin" /> : <ArrowRight size={14} />}
                onClick={extractCriteria}
                disabled={extracting || busy}
              >
                {extracting ? 'Extracting (AI)…' : total === 0 ? 'Extract Criteria' : 'Re-extract'}
              </Button>
              <Button
                variant="success"
                icon={<ArrowRight size={14} />}
                onClick={approveAll}
                disabled={busy || total === 0}
              >
                {busy ? 'Working…' : 'Approve all & evaluate'}
              </Button>
            </div>
          }
        />
        <CardBody className="space-y-3">
          {criteria.length === 0 && (
            <div className="empty">
              No criteria extracted yet. Go back to <strong>Documents</strong>, upload the NIT, and run extraction.
            </div>
          )}
          {criteria.map(c => (
            <div key={c.id} className="border border-line rounded-md p-4">
              {editingId === c.id ? (
                <div className="space-y-2">
                  <textarea
                    className="textarea text-sm"
                    rows={3}
                    value={edit.text}
                    onChange={e => setEdit({ ...edit, text: e.target.value })}
                  />
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={edit.mandatory}
                      onChange={e => setEdit({ ...edit, mandatory: e.target.checked })}
                    />
                    Mandatory
                  </label>
                  <div className="flex gap-2">
                    <Button variant="success" icon={<Save size={14} />} onClick={saveEdit} size="sm">Save</Button>
                    <Button variant="ghost" icon={<X size={14} />} onClick={() => setEditingId(null)} size="sm">Cancel</Button>
                  </div>
                </div>
              ) : (
                <>
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-ink leading-relaxed">{c.criterion_text}</div>
                      <div className="flex items-center gap-2 mt-2 flex-wrap">
                        <Pill tone="primary">{c.criterion_type.replace(/_/g, ' ')}</Pill>
                        {c.is_mandatory && <Pill tone="danger">mandatory</Pill>}
                        {c.gfr_rule_number && <Pill tone="soft">{c.gfr_rule_number}</Pill>}
                        {c.state === 'approved' && <Pill tone="success">approved</Pill>}
                        {c.source_doc_id && c.source_page && (
                          <SourcePill
                            source={{
                              doc_id: c.source_doc_id,
                              page: c.source_page,
                              bbox: c.source_bbox || null,
                              label: `${c.source_clause_ref || `clause`} · p.${c.source_page}`,
                            }}
                            onOpen={(s) => setSourceOpen({ doc_id: s.doc_id, page: s.page })}
                          />
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      <Button variant="ghost" size="sm" icon={<Pencil size={12} />} onClick={() => startEdit(c)}>Edit</Button>
                      {c.state !== 'approved' && (
                        <Button
                          variant="success"
                          size="sm"
                          icon={<CheckCircle2 size={12} />}
                          onClick={() => criteriaApi.approve(c.id).then(refresh)}
                        >
                          Approve
                        </Button>
                      )}
                    </div>
                  </div>
                </>
              )}
            </div>
          ))}
        </CardBody>
      </Card>

      {sourceOpen && (
        <Drawer open onClose={() => setSourceOpen(null)} title="NIT clause" width="min(900px, 95vw)">
          <div className="h-full">
            <PDFViewer docId={sourceOpen.doc_id} initialPage={sourceOpen.page} />
          </div>
        </Drawer>
      )}
    </div>
  );
}
