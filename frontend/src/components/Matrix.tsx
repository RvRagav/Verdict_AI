// Comparative matrix — bidders × criteria. Each cell is a coloured
// chip showing AI-suggested verdict + confidence. Click → drawer
// with full evaluation detail. This is the officer's mental model.

import { useMemo } from 'react';
import type { Matrix, MatrixCell } from '../types';
import Tooltip from './Tooltip';

export default function MatrixView({
  data,
  onCellClick,
}: {
  data: Matrix;
  onCellClick: (cell: MatrixCell) => void;
}) {
  const byPair = useMemo(() => {
    const m = new Map<string, MatrixCell>();
    for (const c of data.cells) m.set(`${c.bidder_id}::${c.criterion_id}`, c);
    return m;
  }, [data]);

  if (data.bidders.length === 0 || data.criteria.length === 0) {
    return (
      <div className="empty">
        Run the evaluation to populate the matrix.
      </div>
    );
  }

  return (
    <div className="overflow-auto card p-0">
      <table className="min-w-full text-sm border-collapse">
        <thead>
          <tr className="bg-bg-sunk border-b border-line">
            <th className="text-left px-4 py-3 font-semibold text-ink sticky left-0 bg-bg-sunk z-10">
              Criterion
            </th>
            {data.bidders.map(b => (
              <th
                key={b.id}
                className="text-left px-4 py-3 font-semibold text-ink min-w-[200px]"
              >
                <div className="truncate max-w-[200px]" title={b.company_name}>
                  {b.company_name}
                </div>
                <div className="text-xs font-normal text-ink-soft mt-0.5">
                  {b.state}
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.criteria.map(c => (
            <tr key={c.id} className="border-b border-line hover:bg-bg-soft">
              <td className="px-4 py-3 align-top sticky left-0 bg-bg z-10 max-w-[440px]">
                <div className="text-sm text-ink line-clamp-2">{c.criterion_text}</div>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-xs text-ink-soft">{c.criterion_type}</span>
                  {c.is_mandatory && (
                    <span className="text-xs text-danger">mandatory</span>
                  )}
                </div>
              </td>
              {data.bidders.map(b => {
                const cell = byPair.get(`${b.id}::${c.id}`);
                return (
                  <td key={b.id} className="px-4 py-3 align-top">
                    <Cell cell={cell} onClick={() => cell && onCellClick(cell)} />
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Cell({ cell, onClick }: { cell: MatrixCell | undefined; onClick: () => void }) {
  if (!cell || !cell.verdict) {
    return (
      <button
        type="button"
        className="vc-empty rounded-md w-full px-3 py-2 text-xs text-left"
        onClick={onClick}
      >
        Not evaluated
      </button>
    );
  }
  const klass =
    cell.verdict === 'PASS'   ? 'vc-pass'
  : cell.verdict === 'FAIL'   ? 'vc-fail'
  : 'vc-review';
  const conf = Math.round((cell.confidence ?? 0) * 100);
  const routeLabel =
    cell.route === 'auto_commit'      ? 'Auto'
  : cell.route === 'mandatory_review' ? 'Mandatory review'
  : 'Officer to review';

  // AI never asserts — every label says "AI suggests …" plus the human-
  // readable verb phrase. The bold word is the verb, never the bare enum.
  const verdictWord =
    cell.verdict === 'PASS'   ? 'satisfies'
  : cell.verdict === 'FAIL'   ? 'does not satisfy'
  : 'unclear';
  const verdictGloss =
    cell.verdict === 'PASS'   ? 'AI: satisfies'
  : cell.verdict === 'FAIL'   ? 'AI: does not satisfy'
  : 'AI: review';

  return (
    <Tooltip
      label={`AI suggests this ${verdictWord} the criterion (${conf}% confident). Click for full evidence.`}
    >
      <button
        type="button"
        onClick={onClick}
        className={`${klass} rounded-md w-full px-3 py-2 text-xs text-left transition-transform hover:scale-[1.02] hover:shadow-2`}
      >
        <div className="flex items-center justify-between">
          <span className="font-semibold">{verdictGloss}</span>
          <span className="text-[11px] opacity-80">{conf}%</span>
        </div>
        <div className="text-[11px] opacity-80 mt-1">{routeLabel}</div>
      </button>
    </Tooltip>
  );
}
