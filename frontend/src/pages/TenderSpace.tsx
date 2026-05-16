// TenderSpace — shell that loads the tender and routes to step views.

import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { tendersApi } from '../api/endpoints';
import type { StepKey, Tender } from '../types';
import TenderSpaceLayout from '../components/TenderSpaceLayout';
import OverviewView from './tender-space/OverviewView';
import DocumentsView from './tender-space/DocumentsView';
import CriteriaView from './tender-space/CriteriaView';
import EvaluationView from './tender-space/EvaluationView';
import ReportView from './tender-space/ReportView';
import FileVaultView from './tender-space/FileVaultView';
import VerifiersView from './tender-space/VerifiersView';
import AuditView from './tender-space/AuditView';

type ExtendedStepKey = StepKey | 'file-vault' | 'verifiers' | 'audit';

export default function TenderSpace({ step }: { step: ExtendedStepKey }) {
  const { id } = useParams<{ id: string }>();
  const [tender, setTender] = useState<Tender | null>(null);

  useEffect(() => {
    if (!id) return;
    tendersApi.get(id).then(setTender);
  }, [id]);

  if (!tender) {
    return <div className="empty">Loading tender …</div>;
  }

  const refresh = () => tendersApi.get(tender.id).then(setTender);
  // Layout uses StepKey for the indicator highlight; map utility tabs back to a safe parent step
  const layoutStep: StepKey = (
    step === 'file-vault' || step === 'verifiers' || step === 'audit'
  ) ? 'documents'  // utility tabs render under "documents" highlight visually
    : step;

  return (
    <TenderSpaceLayout tender={tender} step={layoutStep}>
      {step === 'setup'       && <OverviewView   tender={tender} onChanged={refresh} />}
      {step === 'documents'   && <DocumentsView  tender={tender} onChanged={refresh} />}
      {step === 'criteria'    && <CriteriaView   tender={tender} onChanged={refresh} />}
      {step === 'evaluation'  && <EvaluationView tender={tender} onChanged={refresh} />}
      {step === 'report'      && <ReportView     tender={tender} onChanged={refresh} />}
      {step === 'file-vault'  && <FileVaultView  tender={tender} onChanged={refresh} />}
      {step === 'verifiers'   && <VerifiersView  tender={tender} onChanged={refresh} />}
      {step === 'audit'       && <AuditView      tender={tender} onChanged={refresh} />}
    </TenderSpaceLayout>
  );
}
