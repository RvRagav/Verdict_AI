// Inline clickable source reference. Opens the PDF drawer at the cited
// page+bbox. This is the trust mechanism — every AI claim has one.

import { ExternalLink } from 'lucide-react';
import Tooltip from './Tooltip';
import type { BBox } from '../types';

export type SourceRef = {
  doc_id: string;
  page: number;
  bbox?: BBox | null;
  quote?: string | null;
  label?: string;
};

export default function SourcePill({
  source,
  onOpen,
}: {
  source: SourceRef;
  onOpen: (s: SourceRef) => void;
}) {
  const label = source.label || `page ${source.page}`;
  return (
    <Tooltip label="Open the source in the document viewer">
      <button
        type="button"
        className="source-pill"
        onClick={() => onOpen(source)}
      >
        <ExternalLink size={11} />
        {label}
      </button>
    </Tooltip>
  );
}
