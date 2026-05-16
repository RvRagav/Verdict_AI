// PDF / image viewer with bbox highlight overlay.
//
// Inputs:
//   docId       — backend document id
//   pageNumber  — 1-based page to open
//   highlight   — optional normalised bbox (or list) to draw in pencil border
//
// We render the rasterised page image (the backend already saves one
// per page). Per-word bboxes are loaded on demand for the highlight
// halo. This avoids react-pdf's PDF.js worker setup and works the same
// for both PDFs and JPG scans (the backend normalises everything to
// per-page PNGs).

import { useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight, FileText, Loader } from 'lucide-react';
import { documentsApi } from '../api/endpoints';
import type { BBox, Document, WordObject } from '../types';

type Props = {
  docId: string;
  initialPage?: number;
  highlight?: BBox | null;
  highlightText?: string | null;
};

export default function PDFViewer({
  docId,
  initialPage = 1,
  highlight = null,
  highlightText = null,
}: Props) {
  const [doc, setDoc] = useState<Document | null>(null);
  const [page, setPage] = useState(initialPage);
  const [words, setWords] = useState<WordObject[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);
    documentsApi.get(docId).then(d => {
      if (!active) return;
      setDoc(d);
      setLoading(false);
    });
    return () => { active = false; };
  }, [docId]);

  useEffect(() => {
    let active = true;
    documentsApi.page(docId, page).then(p => {
      if (!active) return;
      setWords(p.word_objects || []);
    });
    return () => { active = false; };
  }, [docId, page]);

  if (loading || !doc) {
    return (
      <div className="empty">
        <Loader size={20} className="animate-spin inline-block mr-2" />
        Loading document …
      </div>
    );
  }

  const totalPages = doc.page_count || 1;
  const imgUrl = documentsApi.pageImageUrl(docId, page);
  const matchedWords = highlightText
    ? words.filter(w =>
        (w.text_content || '').toLowerCase().includes(
          highlightText.toLowerCase().split(/\s+/)[0] || '',
        ),
      )
    : [];

  return (
    <div className="bg-bg-sunk h-full flex flex-col">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-line bg-bg flex-shrink-0">
        <div className="flex items-center gap-2 text-sm">
          <FileText size={14} className="text-ink-soft" />
          <span className="font-medium text-ink truncate max-w-[260px]">{doc.filename}</span>
          <span className="text-ink-faint">·</span>
          <span className="text-ink-soft">page {page} of {totalPages}</span>
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page <= 1}
            title="Previous page"
            aria-label="Previous page"
          >
            <ChevronLeft size={14} />
          </button>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
            title="Next page"
            aria-label="Next page"
          >
            <ChevronRight size={14} />
          </button>
        </div>
      </div>

      {/* Page canvas — fills remaining height */}
      <div className="flex-1 min-h-0 overflow-auto p-4 flex justify-center items-start">
        <div className="relative inline-block max-w-full">
          <img
            src={imgUrl}
            alt={`${doc.filename} page ${page}`}
            className="max-w-full block bg-white shadow-2 rounded-md"
            style={{ maxHeight: 'calc(100vh - 180px)' }}
          />
          {/* Bbox highlight overlay (single bbox) */}
          {highlight && (
            <div
              className="absolute border-2 border-warning rounded-sm pointer-events-none"
              style={{
                left: `${highlight.x_min * 100}%`,
                top: `${highlight.y_min * 100}%`,
                width: `${(highlight.x_max - highlight.x_min) * 100}%`,
                height: `${(highlight.y_max - highlight.y_min) * 100}%`,
                background: 'rgba(183, 121, 31, 0.18)',
                boxShadow: '0 0 0 4px rgba(183, 121, 31, 0.12)',
              }}
              aria-label="Highlighted source region"
            />
          )}
          {/* Highlight by quote — multi-word fallback */}
          {!highlight && matchedWords.slice(0, 30).map((w, i) => (
            <div
              key={i}
              className="absolute pointer-events-none"
              style={{
                left: `${w.x_min * 100}%`,
                top: `${w.y_min * 100}%`,
                width: `${(w.x_max - w.x_min) * 100}%`,
                height: `${(w.y_max - w.y_min) * 100}%`,
                background: 'rgba(31, 79, 182, 0.18)',
                outline: '1px solid var(--primary)',
                borderRadius: 2,
              }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
