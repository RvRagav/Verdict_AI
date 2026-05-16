// File Vault — every document attached to this tender, one screen.

import { useEffect, useState } from 'react';
import {
  FileText, FolderOpen, Loader, Eye,
} from 'lucide-react';
import { fileVaultApi } from '../../api/endpoints';
import type { Tender } from '../../types';
import { Card, CardBody, CardHeader } from '../../components/Card';
import Pill from '../../components/Pill';
import Drawer from '../../components/Drawer';
import PDFViewer from '../../components/PDFViewer';

type Props = { tender: Tender; onChanged?: () => void };

export default function FileVaultView({ tender }: Props) {
  const [data, setData] = useState<Awaited<ReturnType<typeof fileVaultApi.list>> | null>(null);
  const [loading, setLoading] = useState(true);
  const [previewDoc, setPreviewDoc] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    fileVaultApi.list(tender.id).then(setData).finally(() => setLoading(false));
  }, [tender.id]);

  if (loading || !data) {
    return (
      <div className="empty">
        <Loader size={20} className="animate-spin inline-block mr-2" />
        Loading file vault …
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader
          title={
            <span className="flex items-center gap-2 font-display">
              <FolderOpen size={16} className="text-primary" />
              File Vault
            </span>
          }
          subtitle="Every document attached to this tender. Click any file to preview."
          actions={
            <div className="flex items-center gap-2">
              <Pill tone="primary">{data.totals.docs} docs</Pill>
              <Pill tone="soft">{data.totals.pages} pages</Pill>
              <Pill tone="success">{data.totals.complete} processed</Pill>
            </div>
          }
        />
        <CardBody>
          {data.tender_files.length > 0 && (
            <div className="mb-5">
              <div className="section-title mb-2">Tender-level documents</div>
              <ul className="space-y-2">
                {data.tender_files.map(f => (
                  <FileRow key={f.id} file={f} onOpen={() => setPreviewDoc(f.id)} />
                ))}
              </ul>
            </div>
          )}

          {data.by_bidder.length > 0 ? (
            <div className="space-y-4">
              <div className="section-title mb-2">By bidder</div>
              {data.by_bidder.map(group => (
                <div key={group.bidder.id} className="border border-line rounded-md">
                  <div className="px-4 py-2.5 bg-bg-soft border-b border-line flex items-center justify-between">
                    <div>
                      <div className="font-semibold text-ink">{group.bidder.company_name}</div>
                      <div className="text-xs text-ink-soft mono">
                        {group.bidder.pan_number ?? '—'} · {group.bidder.gstin ?? '—'}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Pill tone="primary">{group.file_count} docs</Pill>
                      <Pill tone="soft">{group.page_count_total} pages</Pill>
                    </div>
                  </div>
                  <ul className="divide-y divide-line">
                    {group.files.length === 0 ? (
                      <li className="px-4 py-3 text-sm text-ink-soft">No documents uploaded yet.</li>
                    ) : group.files.map(f => (
                      <FileRow key={f.id} file={f} onOpen={() => setPreviewDoc(f.id)} compact />
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-sm text-ink-soft">No bidders registered yet.</div>
          )}
        </CardBody>
      </Card>

      {previewDoc && (
        <Drawer
          open
          onClose={() => setPreviewDoc(null)}
          title="Document preview"
          width="min(900px, 95vw)"
        >
          <div className="h-full">
            <PDFViewer docId={previewDoc} />
          </div>
        </Drawer>
      )}
    </div>
  );
}

function FileRow({
  file, onOpen, compact = false,
}: {
  file: any; onOpen: () => void; compact?: boolean;
}) {
  const stateBadge =
    file.processing_state === 'complete' ? <Pill tone="success">processed</Pill> :
    file.processing_state === 'error'    ? <Pill tone="danger">error</Pill> :
    <Pill tone="warning">{file.processing_state}</Pill>;

  return (
    <li
      className={`flex items-center justify-between gap-3 ${compact ? 'px-4 py-2' : 'p-3 border border-line rounded-md'} hover:bg-bg-soft cursor-pointer transition`}
      onClick={onOpen}
      title="Open in viewer"
    >
      <div className="flex items-center gap-3 min-w-0">
        <FileText size={14} className="text-primary flex-shrink-0" />
        <div className="min-w-0">
          <div className="text-sm font-medium text-ink truncate">{file.filename}</div>
          <div className="text-xs text-ink-soft mono truncate">
            {file.doc_type} · {file.page_count} pages · OCR {Math.round((file.avg_ocr_conf || 0) * 100)}%
            <span className="text-ink-faint"> · sha256 {file.sha256_hash?.slice(0, 12)}…</span>
          </div>
        </div>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        {stateBadge}
        <button type="button" className="btn btn-ghost btn-sm" aria-label="View">
          <Eye size={13} />
        </button>
      </div>
    </li>
  );
}
