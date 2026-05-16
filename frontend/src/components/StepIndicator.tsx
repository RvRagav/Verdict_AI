// Tender Space step indicator + utility tabs.
//   Main flow:    1. Setup → 2. Documents → 3. Criteria → 4. Evaluation → 5. Report
//   Utility tabs: ↗ File Vault · ↗ Verifiers · ↗ Audit (always available)

import { CheckCircle2, Circle, FolderOpen, ShieldCheck, History } from 'lucide-react';
import type { StepKey } from '../types';
import { useNavigate } from 'react-router-dom';

const STEPS: { key: StepKey; label: string; tooltip: string }[] = [
  { key: 'setup',      label: '1. Setup',      tooltip: 'Tender basics & scope' },
  { key: 'documents',  label: '2. Documents',  tooltip: 'NIT, corrigendum, bidder submissions' },
  { key: 'criteria',   label: '3. Criteria',   tooltip: 'AI-extracted eligibility' },
  { key: 'evaluation', label: '4. Evaluation', tooltip: 'Per-bidder verdicts with sources' },
  { key: 'report',     label: '5. Report',     tooltip: 'Signed TEC report' },
];

const UTILITY: { key: string; label: string; tooltip: string; Icon: typeof FolderOpen }[] = [
  { key: 'file-vault', label: 'File Vault', tooltip: 'Every document attached to this tender, in one screen', Icon: FolderOpen },
  { key: 'verifiers',  label: 'Verifiers',  tooltip: 'External-source checks (GST, PAN, UDIN, FRN, MCA, Debarment)', Icon: ShieldCheck },
  { key: 'audit',      label: 'Audit',      tooltip: 'Hash-linked event log', Icon: History },
];

const STEP_ORDER: Record<StepKey, number> = {
  setup: 0, documents: 1, criteria: 2, evaluation: 3, report: 4,
};

export default function StepIndicator({
  current,
  tenderId,
}: {
  current: StepKey;
  tenderId: string;
}) {
  const nav = useNavigate();
  const currentIdx = STEP_ORDER[current];
  return (
    <div className="flex items-center justify-between gap-2" role="list" aria-label="Tender progress">
      <div className="step-row">
        {STEPS.map((s, i) => {
          const status =
            i === currentIdx ? 'is-current'
            : i < currentIdx ? 'is-complete'
            : '';
          return (
            <div key={s.key} className="flex items-center">
              <button
                type="button"
                className={`step ${status}`}
                title={s.tooltip}
                onClick={() => nav(`/tenders/${tenderId}/${s.key}`)}
                role="listitem"
              >
                {i < currentIdx ? <CheckCircle2 size={14} /> : <Circle size={14} />}
                {s.label}
              </button>
              {i < STEPS.length - 1 && <span className="step-arrow mx-1">›</span>}
            </div>
          );
        })}
      </div>

      <div className="flex items-center gap-1.5 ml-4 pl-4 border-l border-dashed border-line-strong">
        {UTILITY.map(u => (
          <button
            key={u.key}
            type="button"
            className="step"
            title={u.tooltip}
            onClick={() => nav(`/tenders/${tenderId}/${u.key}`)}
          >
            <u.Icon size={13} />
            {u.label}
          </button>
        ))}
      </div>
    </div>
  );
}
