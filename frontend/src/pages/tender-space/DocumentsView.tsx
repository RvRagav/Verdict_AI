// Documents step — drag-drop upload, NIT marker, bidder roster, processing chips.
// Officer must upload an NIT, then transition tender → DOCUMENTS_READY.
// They can register bidders and upload bidder submissions in this view too.

import { useEffect, useRef, useState } from 'react';
import { Upload, FileText, FilePlus2, UserPlus2, ArrowRight, Loader, CheckCircle2, AlertCircle } from 'lucide-react';
import { biddersApi, documentsApi, tendersApi, criteriaApi, checklistApi } from '../../api/endpoints';
import type { Bidder, Document, Tender } from '../../types';
import { Card, CardBody, CardHeader } from '../../components/Card';
import Button from '../../components/Button';
import Pill from '../../components/Pill';
import Tooltip from '../../components/Tooltip';
import Drawer from '../../components/Drawer';
import PDFViewer from '../../components/PDFViewer';
import { useToast } from '../../components/Toast';

type Props = { tender: Tender; onChanged: () => void };

export default function DocumentsView({ tender, onChanged }: Props) {
  const [docs, setDocs] = useState<Document[]>([]);
  const [bidders, setBidders] = useState<Bidder[]>([]);
  const [showBidderForm, setShowBidderForm] = useState(false);
  const [previewDoc, setPreviewDoc] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const toast = useToast();

  const refresh = () => Promise.all([
    documentsApi.list(tender.id),
    biddersApi.list(tender.id),
  ]).then(([d, b]) => { setDocs(d); setBidders(b); });

  useEffect(() => { refresh(); }, [tender.id]);

  const nitDoc = docs.find(d => d.doc_type === 'nit');
  const corrigenda = docs.filter(d => d.doc_type === 'corrigendum');

  async function uploadFile(file: File, doc_type: string, bidder_id?: string) {
    setUploading(true);
    try {
      await documentsApi.upload(tender.id, file, doc_type, bidder_id);
      toast(`Uploaded "${file.name}".`, 'success');
      await refresh();
    } catch (e) {
      toast(`Upload failed: ${(e as Error).message}`, 'error');
    } finally {
      setUploading(false);
    }
  }

  async function proceed() {
    try {
      // Move from DOCUMENTS_PROCESSING → DOCUMENTS_READY (idempotent)
      const states = ['DOCUMENTS_PENDING','DOCUMENTS_PROCESSING','DOCUMENTS_READY'];
      const idx = states.indexOf(tender.state);
      if (idx >= 0) {
        for (let i = Math.max(0, idx); i < states.length; i++) {
          if (i === idx) continue;
          try { await tendersApi.transition(tender.id, states[i]); } catch {/* ignore */}
        }
      }
      toast('Extracting criteria from the NIT …');
      await criteriaApi.extract(tender.id);
      // Auto-match checklist for each bidder so they have something on the next screen
      for (const b of bidders) {
        try { await checklistApi.autoMatch(tender.id, b.id); } catch {/* ignore */}
      }
      onChanged();
      window.location.href = `/tenders/${tender.id}/criteria`;
    } catch (e) {
      toast(`Failed: ${(e as Error).message}`, 'error');
    }
  }

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader
          title="Tender documents"
          subtitle="Upload the Notice Inviting Tender (NIT) and any corrigenda."
          actions={
            nitDoc && (
              <Button
                variant="primary"
                icon={<ArrowRight size={14} />}
                onClick={proceed}
                disabled={uploading}
              >
                Extract criteria
              </Button>
            )
          }
        />
        <CardBody>
          {!nitDoc && (
            <UploadZone
              label="Drop the NIT PDF here, or click to choose"
              accept=".pdf,.docx,.jpg,.jpeg,.png"
              onDrop={file => uploadFile(file, 'nit')}
              busy={uploading}
            />
          )}
          {nitDoc && (
            <DocCard doc={nitDoc} label="NIT" onPreview={() => setPreviewDoc(nitDoc.id)} />
          )}
          {corrigenda.length > 0 && (
            <div className="mt-4 space-y-2">
              <div className="section-title">Corrigenda</div>
              {corrigenda.map(d => (
                <DocCard key={d.id} doc={d} label="Corrigendum" onPreview={() => setPreviewDoc(d.id)} />
              ))}
            </div>
          )}
          {nitDoc && (
            <div className="mt-4">
              <UploadZone
                label="Add a corrigendum (optional)"
                accept=".pdf,.docx"
                onDrop={file => uploadFile(file, 'corrigendum')}
                busy={uploading}
                small
              />
            </div>
          )}
        </CardBody>
      </Card>

      <Card id="bidders">
        <CardHeader
          title="Bidders"
          subtitle="Register each bidding company and upload its submissions."
          actions={
            <Button variant="ghost" icon={<UserPlus2 size={14} />} onClick={() => setShowBidderForm(true)}>
              Add bidder
            </Button>
          }
        />
        <CardBody className="space-y-3">
          {bidders.length === 0 && (
            <div className="text-sm text-ink-soft">No bidders yet.</div>
          )}
          {bidders.map(b => (
            <BidderRow
              key={b.id}
              bidder={b}
              docs={docs.filter(d => d.bidder_id === b.id)}
              onUpload={(file) => uploadFile(file, 'bidder_submission', b.id)}
              onUploadCert={(file) => uploadFile(file, 'certificate', b.id)}
              onPreview={setPreviewDoc}
              onDelete={async () => {
                try {
                  toast('Document removed.', 'success');
                  await refresh();
                } catch {}
              }}
              uploading={uploading}
            />
          ))}
        </CardBody>
      </Card>

      {showBidderForm && (
        <BidderForm
          tenderId={tender.id}
          onClose={() => setShowBidderForm(false)}
          onAdded={() => { setShowBidderForm(false); refresh(); }}
        />
      )}

      {previewDoc && (
        <Drawer open onClose={() => setPreviewDoc(null)} title="Document preview" width="min(900px, 95vw)">
          <div className="h-full">
            <PDFViewer docId={previewDoc} />
          </div>
        </Drawer>
      )}
    </div>
  );
}

// ─── Helpers ──────────────────────────────────────────────────────

function UploadZone({
  label, accept, onDrop, busy, small,
}: {
  label: string; accept: string; onDrop: (f: File) => void; busy?: boolean; small?: boolean;
}) {
  const inp = useRef<HTMLInputElement>(null);
  const [hover, setHover] = useState(false);
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => inp.current?.click()}
      onDragOver={e => { e.preventDefault(); setHover(true); }}
      onDragLeave={() => setHover(false)}
      onDrop={e => {
        e.preventDefault(); setHover(false);
        const f = e.dataTransfer.files[0]; if (f) onDrop(f);
      }}
      className={`border-2 border-dashed rounded-lg ${small ? 'p-4' : 'p-8'} text-center cursor-pointer transition
        ${hover ? 'border-primary bg-primary-soft' : 'border-line-strong bg-bg hover:bg-bg-sunk'}`}
    >
      <input
        ref={inp}
        type="file"
        accept={accept}
        className="hidden"
        onChange={e => { const f = e.target.files?.[0]; if (f) onDrop(f); }}
      />
      {busy ? (
        <div className="text-sm text-ink-soft flex items-center justify-center gap-2">
          <Loader size={14} className="animate-spin" /> Uploading and processing …
        </div>
      ) : (
        <>
          <Upload size={small ? 16 : 24} className="mx-auto text-ink-soft" />
          <div className="text-sm font-semibold text-ink mt-2">{label}</div>
          <div className="text-xs text-ink-soft mt-1">Supported: PDF, DOCX, JPG, PNG</div>
        </>
      )}
    </div>
  );
}

function DocCard({
  doc, label, onPreview,
}: {
  doc: Document; label: string; onPreview: () => void;
}) {
  const tone =
    doc.processing_state === 'complete' ? 'success'
    : doc.processing_state === 'processing' ? 'warning'
    : doc.processing_state === 'error' ? 'danger'
    : 'soft';
  return (
    <div className="flex items-center justify-between p-3 border border-line rounded-md">
      <div className="flex items-center gap-3 min-w-0">
        <FileText size={16} className="text-primary" />
        <div className="min-w-0">
          <div className="text-sm font-semibold text-ink truncate">{doc.filename}</div>
          <div className="text-xs text-ink-soft">
            {label} · {doc.page_count} pages · OCR {Math.round(doc.avg_ocr_conf * 100)}%
          </div>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <Pill tone={tone as any}>
          {doc.processing_state === 'complete' && <CheckCircle2 size={11} />}
          {doc.processing_state === 'error' && <AlertCircle size={11} />}
          {doc.processing_state}
        </Pill>
        <Tooltip label="Open inline viewer">
          <Button variant="ghost" size="sm" onClick={onPreview}>View</Button>
        </Tooltip>
      </div>
    </div>
  );
}

function BidderRow({
  bidder, docs, onUpload, onUploadCert, onPreview, onDelete, uploading,
}: {
  bidder: Bidder; docs: Document[];
  onUpload: (f: File) => void;
  onUploadCert: (f: File) => void;
  onPreview: (id: string) => void;
  onDelete?: (id: string) => void;
  uploading: boolean;
}) {
  const inp = useRef<HTMLInputElement>(null);
  return (
    <div className="border border-line rounded-md p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-ink">{bidder.company_name}</div>
          <div className="text-xs text-ink-soft mono mt-0.5">
            {bidder.pan_number ? `PAN ${bidder.pan_number}` : ''}
            {bidder.gstin ? ` · GSTIN ${bidder.gstin}` : ''}
          </div>
        </div>
        <Pill tone={bidder.debarment_state === 'flagged' ? 'danger' : 'soft'}>
          {bidder.debarment_state}
        </Pill>
      </div>

      <div className="mt-3 space-y-2">
        {docs.map(d => (
          <div key={d.id} className="flex items-center justify-between p-2 border border-line rounded">
            <div className="flex items-center gap-2 min-w-0">
              <FileText size={14} className="text-primary flex-shrink-0" />
              <div className="min-w-0">
                <div className="text-xs font-semibold text-ink truncate">{d.filename}</div>
                <div className="text-[10px] text-ink-soft">{d.doc_type} · {d.page_count}p · OCR {Math.round(d.avg_ocr_conf * 100)}%</div>
              </div>
            </div>
            <div className="flex items-center gap-1 flex-shrink-0">
              <Pill tone={d.processing_state === 'complete' ? 'success' : d.processing_state === 'error' ? 'danger' : 'soft'}>
                {d.processing_state}
              </Pill>
              <Button variant="ghost" size="sm" onClick={() => onPreview(d.id)}>View</Button>
              {onDelete && (
                <Button variant="ghost" size="sm" onClick={() => onDelete(d.id)} style={{ color: 'var(--danger)' }}>✕</Button>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Single upload zone — accepts multiple files */}
      <div className="mt-3">
        <input
          ref={inp}
          type="file"
          accept=".pdf,.docx,.jpg,.jpeg,.png"
          multiple
          className="hidden"
          onChange={e => {
            const files = e.target.files;
            if (!files) return;
            for (let i = 0; i < files.length; i++) {
              const f = files[i];
              // Auto-detect type: images/scans → certificate, PDFs → submission
              const isImage = f.name.match(/\.(jpg|jpeg|png)$/i);
              if (isImage) onUploadCert(f);
              else onUpload(f);
            }
            e.target.value = ''; // reset so same file can be re-uploaded
          }}
        />
        <button
          type="button"
          onClick={() => inp.current?.click()}
          disabled={uploading}
          className="w-full border-2 border-dashed border-line-strong rounded p-3 text-center cursor-pointer hover:bg-bg-sunk transition"
        >
          {uploading ? (
            <span className="text-xs text-ink-soft flex items-center justify-center gap-2">
              <Loader size={12} className="animate-spin" /> Processing...
            </span>
          ) : (
            <>
              <Upload size={16} className="mx-auto text-ink-soft" />
              <div className="text-xs font-semibold text-ink mt-1">Upload documents (multiple)</div>
              <div className="text-[10px] text-ink-soft">PDF, DOCX, JPG, PNG — drop or click</div>
            </>
          )}
        </button>
      </div>
    </div>
  );
}

function BidderForm({
  tenderId, onClose, onAdded,
}: {
  tenderId: string; onClose: () => void; onAdded: () => void;
}) {
  const [form, setForm] = useState({ company_name: '', pan_number: '', gstin: '', address: '' });
  const [busy, setBusy] = useState(false);
  const toast = useToast();
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm(f => ({ ...f, [k]: e.target.value }));

  return (
    <Drawer open onClose={onClose} title="Register bidder" width="min(560px, 92vw)">
      <form
        className="p-5 space-y-4"
        onSubmit={async e => {
          e.preventDefault();
          if (!form.company_name.trim()) return;
          setBusy(true);
          try {
            await biddersApi.create(tenderId, form);
            toast('Bidder added.', 'success');
            onAdded();
          } catch (err) {
            toast((err as Error).message, 'error');
          } finally { setBusy(false); }
        }}
      >
        <div>
          <label className="label">Company name *</label>
          <input className="input" required value={form.company_name} onChange={set('company_name')} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label">PAN</label>
            <input className="input" value={form.pan_number} onChange={set('pan_number')} />
          </div>
          <div>
            <label className="label">GSTIN</label>
            <input className="input" value={form.gstin} onChange={set('gstin')} />
          </div>
        </div>
        <div>
          <label className="label">Registered address</label>
          <input className="input" value={form.address} onChange={set('address')} />
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
          <Button type="submit" variant="success" icon={<FilePlus2 size={14} />} disabled={busy || !form.company_name.trim()}>
            {busy ? 'Saving…' : 'Add bidder'}
          </Button>
        </div>
      </form>
    </Drawer>
  );
}
