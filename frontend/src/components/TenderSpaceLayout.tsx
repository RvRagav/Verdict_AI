// Tender Space — dossier content shell with government-style header.
// Shows tender info + progress metrics + step indicator.

import { ReactNode } from 'react';
import StepIndicator from './StepIndicator';
import Pill from './Pill';
import type { StepKey, Tender } from '../types';

export default function TenderSpaceLayout({
  tender,
  step,
  children,
}: {
  tender: Tender;
  step: StepKey;
  children: ReactNode;
}) {
  const stepNum = Math.min(5, Math.floor(tender.progress_pct / 20) + 1);

  return (
    <div className="flex flex-col">
      {/* ─── Dossier Header (government table style) ─── */}
      <div className="card" style={{ marginBottom: '16px', borderRadius: '2px' }}>
        <table className="govt-table" style={{ marginBottom: 0 }}>
          <thead>
            <tr>
              <th colSpan={4} style={{ fontSize: '14px', padding: '12px 16px' }}>
                Tender Evaluation Dossier — {tender.tender_number}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td style={{ fontWeight: 600, width: '120px' }}>Title</td>
              <td colSpan={3} style={{ fontSize: '14px', fontWeight: 600 }}>{tender.title}</td>
            </tr>
            <tr>
              <td style={{ fontWeight: 600 }}>Department</td>
              <td>{tender.department}</td>
              <td style={{ fontWeight: 600, width: '120px' }}>Category</td>
              <td>{tender.category}</td>
            </tr>
            <tr>
              <td style={{ fontWeight: 600 }}>Estimated Cost</td>
              <td>{tender.estimated_cost ? `₹${(tender.estimated_cost / 10000000).toFixed(0)} Crore` : '—'}</td>
              <td style={{ fontWeight: 600 }}>EMD Amount</td>
              <td>{tender.emd_amount ? `₹${(tender.emd_amount / 100000).toFixed(0)} Lakh` : '—'}</td>
            </tr>
            <tr>
              <td style={{ fontWeight: 600 }}>Status</td>
              <td>
                <Pill tone={
                  tender.state === 'FINALIZED' ? 'success'
                  : tender.state === 'HITL_PENDING' ? 'warning'
                  : 'primary'
                }>
                  {tender.state.replace(/_/g, ' ')}
                </Pill>
              </td>
              <td style={{ fontWeight: 600 }}>Progress</td>
              <td>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <div style={{ flex: 1, height: '6px', background: 'var(--bg-sunk)', borderRadius: '2px', overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${tender.progress_pct}%`, background: 'var(--primary)' }} />
                  </div>
                  <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--primary)' }}>
                    Step {stepNum}/5
                  </span>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* ─── Step Indicator ─── */}
      <div style={{ marginBottom: '16px' }}>
        <StepIndicator current={step} tenderId={tender.id} />
      </div>

      {/* ─── Main step content ─── */}
      <section>{children}</section>
    </div>
  );
}
