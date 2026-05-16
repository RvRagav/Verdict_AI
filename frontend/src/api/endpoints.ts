// Typed wrappers around every backend endpoint we use.

import api from './client';
import type {
  AuditEvent,
  Bidder,
  Brief,
  ChatMessage,
  ChecklistItem,
  ChecklistResponse,
  Citation,
  ConcurrenceRequest,
  Corrigendum,
  Criterion,
  CriterionVersion,
  DebarmentEntry,
  Document,
  Evaluation,
  EvaluationSummary,
  Health,
  Matrix,
  Officer,
  Page,
  PostReviewCheck,
  Replay,
  Report,
  Tender,
  Vault,
  WordObject,
} from '../types';

export const officersApi = {
  list: async (): Promise<Officer[]> => (await api.get('/officers')).data.officers,
};

export const tendersApi = {
  list: async (params: { state?: string; department?: string } = {}): Promise<Tender[]> =>
    (await api.get('/tenders', { params })).data.tenders,
  get: async (id: string): Promise<Tender> => (await api.get(`/tenders/${id}`)).data,
  create: async (payload: Partial<Tender>): Promise<Tender> =>
    (await api.post('/tenders', payload)).data,
  transition: async (id: string, target_state: string): Promise<Tender> =>
    (await api.post(`/tenders/${id}/transitions`, { target_state })).data,
  remove: async (id: string) => (await api.delete(`/tenders/${id}`)).data,
};

export const documentsApi = {
  list: async (
    tenderId: string,
    params: { bidder_id?: string; doc_type?: string } = {},
  ): Promise<Document[]> =>
    (await api.get(`/tenders/${tenderId}/documents`, { params })).data.documents,
  get: async (id: string): Promise<Document> =>
    (await api.get(`/documents/${id}`)).data,
  upload: async (
    tenderId: string,
    file: File,
    docType: string,
    bidderId?: string,
  ): Promise<Document> => {
    const fd = new FormData();
    fd.append('file', file);
    fd.append('doc_type', docType);
    if (bidderId) fd.append('bidder_id', bidderId);
    return (
      await api.post(`/tenders/${tenderId}/documents`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
    ).data;
  },
  page: async (docId: string, pageNum: number): Promise<Page & { word_objects: WordObject[] }> =>
    (await api.get(`/documents/${docId}/pages/${pageNum}`)).data,
  fileUrl: (docId: string) => `${api.defaults.baseURL}/documents/${docId}/file`,
  pageImageUrl: (docId: string, pageNum: number) =>
    `${api.defaults.baseURL}/documents/${docId}/pages/${pageNum}/image`,
};

export const biddersApi = {
  list: async (tenderId: string): Promise<Bidder[]> =>
    (await api.get(`/tenders/${tenderId}/bidders`)).data.bidders,
  create: async (
    tenderId: string,
    payload: Partial<Bidder> & {
      emd_amount?: number | null;
      emd_instrument?: string | null;
      emd_instrument_no?: string | null;
      emd_validity_date?: string | null;
      emd_exempt?: boolean;
      emd_exempt_reason?: string | null;
      bid_validity_until?: string | null;
    },
  ): Promise<Bidder> =>
    (await api.post(`/tenders/${tenderId}/bidders`, payload)).data,
  checkDebarment: async (tenderId: string, bidderId: string): Promise<Bidder> =>
    (await api.post(`/tenders/${tenderId}/bidders/${bidderId}/debarment-check`)).data,
};

export const criteriaApi = {
  list: async (tenderId: string): Promise<Criterion[]> =>
    (await api.get(`/tenders/${tenderId}/criteria`)).data.criteria,
  extract: async (tenderId: string) =>
    (await api.post(`/tenders/${tenderId}/criteria/extract`)).data,
  update: async (
    id: string,
    payload: Partial<Pick<Criterion, 'criterion_text' | 'is_mandatory' | 'gfr_rule_number' | 'threshold_value'>>,
  ): Promise<Criterion> => (await api.patch(`/criteria/${id}`, payload)).data,
  approve: async (id: string): Promise<Criterion> =>
    (await api.post(`/criteria/${id}/approve`)).data,
  reject: async (id: string): Promise<Criterion> =>
    (await api.post(`/criteria/${id}/reject`)).data,
  approveAll: async (tenderId: string) =>
    (await api.post(`/tenders/${tenderId}/criteria/approve-all`)).data,
};

export const checklistApi = {
  list: async (tenderId: string): Promise<ChecklistItem[]> =>
    (await api.get(`/tenders/${tenderId}/checklist`)).data.items,
  autoMatch: async (tenderId: string, bidderId: string) =>
    (await api.post(`/tenders/${tenderId}/checklist/auto-match`, null, {
      params: { bidder_id: bidderId },
    })).data,
  responses: async (tenderId: string, bidderId?: string): Promise<ChecklistResponse[]> =>
    (await api.get(`/tenders/${tenderId}/checklist/responses`, {
      params: bidderId ? { bidder_id: bidderId } : {},
    })).data.responses,
  decide: async (responseId: string, decision: 'accepted' | 'rejected', notes?: string) =>
    (await api.post(`/checklist-responses/${responseId}/decide`, { decision, notes })).data,
  finalize: async (tenderId: string) =>
    (await api.post(`/tenders/${tenderId}/checklist/finalize`)).data,
};

export const evaluationsApi = {
  run: async (tenderId: string): Promise<EvaluationSummary> =>
    (await api.post(`/tenders/${tenderId}/evaluate`)).data,
  list: async (
    tenderId: string,
    params: { bidder_id?: string; criterion_id?: string; state?: string; route?: string } = {},
  ): Promise<Evaluation[]> =>
    (await api.get(`/tenders/${tenderId}/evaluations`, { params })).data.evaluations,
  matrix: async (tenderId: string): Promise<Matrix> =>
    (await api.get(`/tenders/${tenderId}/matrix`)).data,
  get: async (id: string): Promise<Evaluation> =>
    (await api.get(`/evaluations/${id}`)).data,
  decide: async (
    id: string,
    payload: { decision: 'confirmed' | 'overridden'; structured_reason?: string; reason_text?: string; new_verdict?: 'PASS'|'FAIL'|'REVIEW' },
  ): Promise<Evaluation> => (await api.post(`/evaluations/${id}/decide`, payload)).data,
  secondOfficer: async (id: string, decision: 'approve' | 'reject'): Promise<Evaluation> =>
    (await api.post(`/evaluations/${id}/second-officer`, { decision })).data,
  captureReplay: async (id: string): Promise<Replay> =>
    (await api.post(`/evaluations/${id}/replay/capture`)).data,
  listReplays: async (id: string): Promise<Replay[]> =>
    (await api.get(`/evaluations/${id}/replays`)).data.replays,
  reproduce: async (id: string) =>
    (await api.post(`/evaluations/${id}/reproduce`)).data,
  answerCheck: async (checkId: string, answer: 'yes' | 'no' | 'not_applicable'): Promise<PostReviewCheck> =>
    (await api.post(`/evaluations/post-review-checks/${checkId}/answer`, { answer })).data,
};

export const anomaliesApi = {
  list: async (tenderId: string, state?: string, bidderId?: string) =>
    (await api.get(`/tenders/${tenderId}/anomalies`, {
      params: { state, bidder_id: bidderId },
    })).data.anomalies,
  decide: async (id: string, decision: 'reviewed' | 'dismissed' | 'confirmed') =>
    (await api.post(`/anomalies/${id}/decide`, { decision })).data,
};

export const chatApi = {
  list: async (tenderId: string): Promise<ChatMessage[]> =>
    (await api.get(`/tenders/${tenderId}/chat/messages`)).data.messages,
  // Streams SSE; consumer parses event-stream lines.
  streamUrl: (tenderId: string) => `${api.defaults.baseURL}/tenders/${tenderId}/chat/stream`,
};

export const reportsApi = {
  generate: async (tenderId: string): Promise<Report> =>
    (await api.post(`/tenders/${tenderId}/reports`)).data,
  list: async (tenderId: string): Promise<Report[]> =>
    (await api.get(`/tenders/${tenderId}/reports`)).data.reports,
  downloadUrl: (id: string) => `${api.defaults.baseURL}/reports/${id}/download`,
};

export const auditApi = {
  trail: async (tenderId: string, cursor?: number): Promise<{ items: AuditEvent[]; next_cursor: number | null }> =>
    (await api.get(`/tenders/${tenderId}/audit`, { params: { cursor } })).data,
  verify: async (tenderId: string): Promise<{ ok: boolean; error: string | null }> =>
    (await api.get(`/tenders/${tenderId}/audit/verify`)).data,
};

export const healthApi = {
  get: async (): Promise<Health> => (await api.get('/healthz')).data,
};


// ─── Sprint A — new APIs ─────────────────────────────────────────


export const briefApi = {
  get: async (tenderId: string): Promise<Brief> =>
    (await api.get(`/tenders/${tenderId}/brief`)).data,
  regenerate: async (tenderId: string): Promise<Brief> =>
    (await api.post(`/tenders/${tenderId}/brief/regenerate`)).data,
};

export const vaultApi = {
  generate: async (tenderId: string): Promise<Vault> =>
    (await api.post(`/tenders/${tenderId}/vaults`)).data,
  list: async (tenderId: string): Promise<Vault[]> =>
    (await api.get(`/tenders/${tenderId}/vaults`)).data.vaults,
  get: async (id: string): Promise<Vault> =>
    (await api.get(`/vaults/${id}`)).data,
  downloadUrl: (id: string) => `${api.defaults.baseURL}/vaults/${id}/download`,
};

export const concurrenceApi = {
  inbox: async (state: string = 'open'): Promise<ConcurrenceRequest[]> =>
    (await api.get('/concurrence/inbox', { params: { state } })).data.requests,
  reviewContext: async (requestId: string) =>
    (await api.get(`/concurrence/${requestId}/review-context`)).data,
  decide: async (id: string, payload: { decision: 'concurred'|'rejected'; decision_note: string }): Promise<ConcurrenceRequest> =>
    (await api.post(`/concurrence/${id}/decide`, payload)).data,
  withdraw: async (id: string): Promise<ConcurrenceRequest> =>
    (await api.post(`/concurrence/${id}/withdraw`)).data,
};

export const corrigendaApi = {
  list: async (tenderId: string): Promise<Corrigendum[]> =>
    (await api.get(`/tenders/${tenderId}/corrigenda`)).data.corrigenda,
  register: async (tenderId: string, payload: { document_id: string; title: string; issued_date?: string }): Promise<Corrigendum> =>
    (await api.post(`/tenders/${tenderId}/corrigenda`, payload)).data,
  get: async (id: string): Promise<Corrigendum> =>
    (await api.get(`/corrigenda/${id}`)).data,
  applyAmendment: async (id: string, payload: {
    criterion_id: string;
    new_text: string;
    new_threshold?: Record<string, unknown> | null;
    new_is_mandatory?: boolean | null;
    new_gfr_rule_number?: string | null;
  }) => (await api.post(`/corrigenda/${id}/amendments`, payload)).data,
  markApplied: async (id: string) => (await api.post(`/corrigenda/${id}/applied`)).data,
};

export const debarmentApi = {
  list: async (source?: string): Promise<DebarmentEntry[]> =>
    (await api.get('/debarment/entries', { params: source ? { source } : {} })).data.entries,
  add: async (entry: Partial<DebarmentEntry>): Promise<{ id: string; duplicate: boolean }> =>
    (await api.post('/debarment/entries', entry)).data,
  check: async (payload: { pan_number?: string; gstin?: string; company_name?: string }) =>
    (await api.post('/debarment/check', payload)).data,
};

export const citationsApi = {
  forEvaluation: async (evaluationId: string): Promise<Citation[]> =>
    (await api.get(`/evaluations/${evaluationId}/citations`)).data.citations,
  forWord: async (wordId: string): Promise<Citation[]> =>
    (await api.get(`/words/${wordId}/citations`)).data.citations,
  forPage: async (pageId: string): Promise<Citation[]> =>
    (await api.get(`/pages/${pageId}/citations`)).data.citations,
};

export const verificationsApi = {
  run: async (tenderId: string) =>
    (await api.post(`/tenders/${tenderId}/verifications/run`)).data,
  runOne: async (tenderId: string, bidderId: string) =>
    (await api.post(`/tenders/${tenderId}/verifications/run/${bidderId}`)).data,
  list: async (tenderId: string) =>
    (await api.get(`/tenders/${tenderId}/verifications`)).data.verifications,
  matrix: async (tenderId: string): Promise<{
    bidders: { id: string; company_name: string }[];
    verifiers: string[];
    cells: Array<{
      bidder_id: string;
      company_name: string;
      verifier_name: string;
      result: any | null;
    }>;
  }> => (await api.get(`/tenders/${tenderId}/verifications/matrix`)).data,
};


export const fileVaultApi = {
  list: async (tenderId: string): Promise<{
    tender_files: any[];
    by_bidder: Array<{
      bidder: any;
      file_count: number;
      page_count_total: number;
      files: any[];
    }>;
    totals: { docs: number; pages: number; complete: number };
  }> => (await api.get(`/tenders/${tenderId}/file-vault`)).data,
};


export const criterionVersionsApi = {
  list: async (criterionId: string): Promise<CriterionVersion[]> =>
    (await api.get(`/criteria/${criterionId}/versions`)).data.versions,
};


// ─── Sprint M2 — HITL co-authoring + Document Studio ───────────────

export const commentsApi = {
  forEvaluation: async (evaluationId: string) =>
    (await api.get(`/evaluations/${evaluationId}/comments`)).data.comments,
  addForEvaluation: async (evaluationId: string, body: string) =>
    (await api.post(`/evaluations/${evaluationId}/comments`, { body })).data,
  forTender: async (tenderId: string) =>
    (await api.get(`/tenders/${tenderId}/comments`)).data.comments,
};

export const tecDraftApi = {
  // Read current draft (if any) without creating one.
  get: async (tenderId: string): Promise<{ draft: any | null; sections: any[] }> =>
    (await api.get(`/tenders/${tenderId}/tec-draft`)).data,
  // Create a draft if none, then populate sections (LLM-backed).
  generate: async (tenderId: string, useLlm = true): Promise<{ draft: any; sections: any[] }> =>
    (await api.post(`/tenders/${tenderId}/tec-draft`, null, {
      params: { use_llm: useLlm },
    })).data,
  reviseSection: async (sectionId: string, body: string, diffSummary?: string) =>
    (await api.post(`/tec-sections/${sectionId}/revise`, {
      body, diff_summary: diffSummary || null,
    })).data,
  regenerateSection: async (sectionId: string) =>
    (await api.post(`/tec-sections/${sectionId}/regenerate`)).data,
  revisions: async (sectionId: string) =>
    (await api.get(`/tec-sections/${sectionId}/revisions`)).data.revisions,
  finalise: async (draftId: string) =>
    (await api.post(`/tec-drafts/${draftId}/finalise`)).data,
};

export const studioApi = {
  list: async (tenderId: string) =>
    (await api.get(`/tenders/${tenderId}/studio/docs`)).data.docs,
  create: async (tenderId: string, payload: { title: string; doc_kind?: string }) =>
    (await api.post(`/tenders/${tenderId}/studio/docs`, payload)).data,
  get: async (docId: string) =>
    (await api.get(`/studio/docs/${docId}`)).data,
  messages: async (docId: string) =>
    (await api.get(`/studio/docs/${docId}/messages`)).data.messages,
  streamUrl: (docId: string) => `${api.defaults.baseURL}/studio/docs/${docId}/stream`,
  finalise: async (docId: string) =>
    (await api.post(`/studio/docs/${docId}/finalise`)).data,
  downloadUrl: (docId: string) => `${api.defaults.baseURL}/studio/docs/${docId}/download`,
};
