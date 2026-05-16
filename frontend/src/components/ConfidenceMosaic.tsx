// Confidence Mosaic — bar viz of the named confidence components.
// Each bar shows ONE component (OCR / Field extraction / Entity match /
// Date parsing / Semantic / Rules / LLM) so the officer instantly sees
// WHICH part is uncertain — not just an opaque "75%".

import type { ConfidenceBreakdown } from '../types';
import Tooltip from './Tooltip';

const LABELS: Record<keyof ConfidenceBreakdown, string> = {
  ocr_quality: 'OCR',
  field_extraction: 'Extraction',
  entity_match: 'Entity',
  date_parsing: 'Dates',
  semantic_match: 'Semantics',
  rules_branch: 'Rules',
  llm_branch: 'LLM',
};

const TOOLTIPS: Record<keyof ConfidenceBreakdown, string> = {
  ocr_quality: 'How clearly the source page was read by OCR.',
  field_extraction: 'How well the relevant value was located.',
  entity_match: 'Whether the document is in the bidder\'s name.',
  date_parsing: 'Whether dates parsed cleanly.',
  semantic_match: 'How closely the text answers the criterion.',
  rules_branch: 'Confidence from the rule-based extractor.',
  llm_branch: 'Confidence from the LLM extractor.',
};

function tone(v: number): 'weak' | 'mid' | 'strong' {
  if (v < 0.5) return 'weak';
  if (v < 0.8) return 'mid';
  return 'strong';
}

export default function ConfidenceMosaic({
  breakdown,
  size = 'sm',
}: {
  breakdown: ConfidenceBreakdown;
  size?: 'sm' | 'lg';
}) {
  const entries = Object.entries(breakdown).filter(([, v]) => v != null) as [keyof ConfidenceBreakdown, number][];
  if (entries.length === 0) return null;
  const barH = size === 'lg' ? 56 : 36;

  return (
    <div className="flex items-end gap-2">
      {entries.map(([k, v]) => {
        const pct = Math.round(v * 100);
        return (
          <Tooltip key={k} label={`${LABELS[k]}: ${pct}% — ${TOOLTIPS[k]}`}>
            <div className="flex flex-col items-center gap-1">
              <div className="mosaic" style={{ height: barH }}>
                <div
                  className={`mosaic-bar ${tone(v)}`}
                  style={{ height: `${Math.max(8, barH * v)}px` }}
                />
              </div>
              <div className="text-[10px] text-ink-soft uppercase tracking-wide">
                {LABELS[k]}
              </div>
              <div className="text-[10px] text-ink-faint">{pct}%</div>
            </div>
          </Tooltip>
        );
      })}
    </div>
  );
}
