// Domain types — match the backend API response shapes.

export type Officer = {
  id: string;
  name: string;
  department: string;
  role: 'junior' | 'senior' | 'reviewer';
};

export type TenderState =
  | 'DRAFT'
  | 'DOCUMENTS_PENDING'
  | 'DOCUMENTS_PROCESSING'
  | 'DOCUMENTS_READY'
  | 'CRITERIA_EXTRACTING'
  | 'CRITERIA_PENDING_REVIEW'
  | 'CRITERIA_APPROVED'
  | 'CHECKLIST_PENDING'
  | 'PRELIMINARY_DONE'
  | 'EVALUATING'
  | 'EVALUATIONS_COMPUTED'
  | 'HITL_PENDING'
  | 'EVALUATION_COMPLETE'
  | 'REPORT_GENERATED'
  | 'FINALIZED';

export type StepKey = 'setup' | 'documents' | 'criteria' | 'evaluation' | 'report';

export type Tender = {
  id: string;
  tender_number: string;
  title: string;
  department: string;
  category: string;
  estimated_cost?: number | null;
  emd_amount?: number | null;
  bid_open_date?: string | null;
  bid_close_date?: string | null;
  state: TenderState;
  step: StepKey;
  progress_pct: number;
  created_at: string;
  updated_at: string;
  metadata?: Record<string, unknown> | null;
};

export type Document = {
  id: string;
  tender_id: string;
  bidder_id: string | null;
  doc_type: 'nit' | 'corrigendum' | 'bidder_submission' | 'certificate' | 'attachment';
  filename: string;
  file_path: string;
  sha256_hash: string;
  page_count: number;
  avg_ocr_conf: number;
  processing_state: 'pending' | 'processing' | 'complete' | 'error';
  uploaded_at: string;
  pages?: Page[];
};

export type Page = {
  id: string;
  page_number: number;
  image_path: string | null;
  raw_text: string | null;
  ocr_confidence: number;
  width_px?: number | null;
  height_px?: number | null;
};

export type WordObject = {
  id: string;
  text_content: string;
  x_min: number;
  y_min: number;
  x_max: number;
  y_max: number;
  confidence: number;
  source_engine: string;
};

export type Bidder = {
  id: string;
  tender_id: string;
  company_name: string;
  pan_number?: string | null;
  gstin?: string | null;
  cin?: string | null;
  udyam_number?: string | null;
  contact_email?: string | null;
  state: 'pending' | 'preliminary_passed' | 'preliminary_failed' | 'evaluated' | 'excluded';
  debarment_state: 'unchecked' | 'clear' | 'flagged' | 'confirmed_debarred';
  metadata?: { address?: string } | null;
  address?: string;
  registered_address?: string | null;
  emd_amount?: number | null;
  emd_instrument?: string | null;
  emd_instrument_no?: string | null;
  emd_validity_date?: string | null;
  emd_exempt?: number | boolean;
  emd_exempt_reason?: string | null;
  bid_validity_until?: string | null;
  created_at: string;
};

export type Criterion = {
  id: string;
  tender_id: string;
  criterion_text: string;
  criterion_type:
    | 'numeric_threshold'
    | 'categorical_presence'
    | 'temporal_recency'
    | 'qualitative_assessment'
    | 'composite';
  threshold_value?: Record<string, unknown> | null;
  is_mandatory: boolean;
  gfr_rule_number?: string | null;
  gfr_override_permitted: boolean;
  source_doc_id?: string | null;
  source_clause_ref?: string | null;
  source_page?: number | null;
  source_bbox?: BBox | null;
  state: 'extracted' | 'edited' | 'approved' | 'rejected';
  current_version?: number;
  last_amended_by?: string | null;
  last_amended_at?: string | null;
  approved_by?: string | null;
  approved_at?: string | null;
};

export type CriterionVersion = {
  id: string;
  criterion_id: string;
  version: number;
  criterion_text: string;
  criterion_type: string;
  threshold_value?: Record<string, unknown> | null;
  is_mandatory: boolean;
  gfr_rule_number?: string | null;
  source_clause_ref?: string | null;
  source_page?: number | null;
  change_source: 'extracted' | 'officer_edit' | 'corrigendum';
  corrigendum_id?: string | null;
  changed_by?: string | null;
  change_note?: string | null;
  created_at: string;
};

export type Corrigendum = {
  id: string;
  tender_id: string;
  document_id: string;
  sequence_number: number;
  title: string;
  issued_date?: string | null;
  summary?: string | null;
  state: 'pending_apply' | 'applied' | 'superseded' | 'rejected';
  applied_by?: string | null;
  applied_at?: string | null;
  created_at: string;
};

export type ConcurrenceRequest = {
  id: string;
  tender_id: string;
  evaluation_id: string;
  requested_by: string;
  target_officer_id?: string | null;
  request_reason: string;
  state: 'open' | 'concurred' | 'rejected' | 'withdrawn';
  decision_note?: string | null;
  decided_at?: string | null;
  decided_by?: string | null;
  created_at: string;
  // joined fields from inbox
  tender_number?: string;
  title?: string;
  criterion_id?: string;
  bidder_id?: string;
  verdict?: Verdict;
};

export type DebarmentEntry = {
  id: string;
  pan_number?: string | null;
  gstin?: string | null;
  company_name?: string | null;
  source: 'cvc' | 'gem' | 'department' | 'court_order' | 'other';
  reason: string;
  debarred_until?: string | null;
  notice_url?: string | null;
  added_at: string;
};

export type Citation = {
  id: string;
  evaluation_id: string;
  document_id: string;
  page_id?: string | null;
  word_object_id?: string | null;
  quote?: string | null;
  role: 'extracted_value' | 'supporting_quote' | 'dissent_basis' | 'anomaly_basis';
  confidence: number;
  // joined for word/page lookups
  text_content?: string;
  x_min?: number; y_min?: number; x_max?: number; y_max?: number;
  page_number?: number;
  // for reverse lookup
  bidder_id?: string;
  criterion_id?: string;
  verdict?: Verdict;
  criterion_text?: string;
  company_name?: string;
};

export type Brief = {
  id: string;
  tender_id: string;
  brief: {
    lay_of_land: string;
    strongest_bidder?: { name: string; reason: string } | null;
    weakest_bidder?: { name: string; reason: string } | null;
    hitl_items: { label: string; evaluation_id?: string | null; why: string }[];
    premortem_risks: { severity: 'low' | 'medium' | 'high'; label: string; evidence: string }[];
  };
  pipeline_signature_hash: string;
  generated_at: string;
};

export type Vault = {
  id: string;
  tender_id: string;
  file_path: string;
  sha256_hash: string;
  file_size_bytes: number;
  manifest: {
    vault_id: string;
    tender_number: string;
    pipeline_signature_hash: string;
    generated_by: string;
    generated_at: string;
    files: { path: string; sha256: string }[];
  };
  pipeline_signature_hash: string;
  generated_by: string;
  generated_at: string;
};

export type BBox = {
  x_min: number;
  y_min: number;
  x_max: number;
  y_max: number;
};

export type ChecklistItem = {
  id: string;
  document_label: string;
  is_mandatory: boolean;
  matches_doc_type?: string | null;
};

export type ChecklistResponse = {
  id: string;
  tender_id: string;
  bidder_id: string;
  checklist_item_id: string;
  document_label?: string;
  is_mandatory?: boolean;
  state: 'present' | 'missing' | 'partial' | 'unclear';
  matched_doc_id?: string | null;
  confidence: number;
  officer_decision?: 'accepted' | 'rejected' | null;
  notes?: string | null;
};

export type Verdict = 'PASS' | 'FAIL' | 'REVIEW';
export type Route = 'auto_commit' | 'hitl_review' | 'mandatory_review';
export type EvalState =
  | 'pending_review'
  | 'pending_second_officer'
  | 'auto_committed'
  | 'resolved';

export type ConfidenceBreakdown = {
  ocr_quality?: number;
  field_extraction?: number;
  entity_match?: number;
  date_parsing?: number;
  semantic_match?: number;
  rules_branch?: number;
  llm_branch?: number;
};

export type EvaluationExplanation = {
  headline: string;
  detail: string;
  facts: string[];
  source_reference: string;
  confidence_note: string;
  next_action: string;
  dissent: string | null;
  dissent_severity: 'low' | 'medium' | 'high' | null;
};

export type Evaluation = {
  id: string;
  tender_id: string;
  bidder_id: string;
  criterion_id: string;
  criterion_version?: number;
  verdict: Verdict;
  confidence: number;
  confidence_breakdown?: ConfidenceBreakdown | null;
  route: Route;
  routing_reason: string;
  extracted_value?: unknown;
  source_doc_id?: string | null;
  source_page?: number | null;
  source_bbox?: BBox | null;
  rules_branch?: Record<string, unknown> | null;
  llm_branch?: Record<string, unknown> | null;
  dissent_branch?: { dissent: string; severity: 'low'|'medium'|'high'; suggested_check?: string; alternative_verdict?: Verdict } | null;
  anomalies?: Array<AnomalyFlag> | null;
  entity_match_flag: boolean;
  explanation?: EvaluationExplanation | null;
  state: EvalState;
  officer_decision?: 'confirmed' | 'overridden' | null;
  officer_id?: string | null;
  structured_reason?: string | null;
  reason_text?: string | null;
  decided_at?: string | null;
  requires_second_officer: boolean;
  concurrence_request_id?: string | null;
  pipeline_signature_hash: string;
  created_at: string;
  post_review_checks?: Array<PostReviewCheck>;
  anomalies_attached?: Array<AnomalyFlag>;
};

export type AnomalyFlag = {
  id?: string;
  flag_type: string;
  severity: 'low' | 'medium' | 'high';
  message: string;
  evidence_data?: Record<string, unknown>;
  state?: 'open' | 'reviewed' | 'dismissed' | 'confirmed';
};

export type PostReviewCheck = {
  id: string;
  check_text: string;
  check_type: string;
  answer?: 'yes' | 'no' | 'not_applicable' | null;
  answered_by?: string | null;
};

export type MatrixCell = {
  bidder_id: string;
  criterion_id: string;
  evaluation_id: string | null;
  verdict: Verdict | null;
  confidence: number | null;
  route: Route | null;
  state: EvalState | null;
};

export type Matrix = {
  bidders: Bidder[];
  criteria: Criterion[];
  cells: MatrixCell[];
};

export type ChatMessage = {
  id: string;
  tender_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  citations?: unknown;
  officer_id?: string | null;
  llm_invocation_id?: string | null;
  timestamp: string;
};

export type Replay = {
  id: string;
  evaluation_id: string;
  officer_id: string;
  timestamp: string;
  snapshot: Record<string, unknown>;
};

export type Report = {
  id: string;
  tender_id: string;
  file_path: string;
  sha256_hash: string;
  generated_by: string;
  generated_at: string;
};

export type AuditEvent = {
  id: number;
  tender_id: string;
  event_type: string;
  event_data: Record<string, unknown>;
  actor: string;
  timestamp: string;
  prev_hash: string;
  entry_hash: string;
};

export type EvaluationSummary = {
  total_cells: number;
  auto_committed: number;
  hitl_review: number;
  mandatory_review: number;
  anomalies_detected: number;
  errors: number;
};

export type Health = {
  ok: boolean;
  version: string;
  bedrock: {
    region: string;
    model_id: string;
    configured: boolean;
  };
};


// ─── Sprint M2 — HITL co-authoring + Document Studio ───────────────

export type OfficerComment = {
  id: string;
  tender_id: string;
  evaluation_id?: string | null;
  bidder_id?: string | null;
  criterion_id?: string | null;
  officer_id: string;
  officer_name?: string;
  officer_role?: string;
  body: string;
  category?: 'observation' | 'logic' | 'action_required' | 'brainstorm' | 'concern' | null;
  affects_verdict?: boolean | number | null;
  suggested_action?: 're_evaluate' | 'verify_document' | 'check_with_bidder' | 'escalate' | null;
  key_insight?: string | null;
  created_at: string;
};

export type TecSectionAuthor = 'ai' | 'co-authored' | 'officer';

export type TecSection = {
  id: string;
  draft_id: string;
  section_key: string;
  section_label: string;
  sort_order: number;
  body: string;
  authored_by: TecSectionAuthor;
  last_edited_by?: string | null;
  last_edited_at: string;
};

export type TecSectionRevision = {
  id: string;
  section_id: string;
  revision: number;
  body_before?: string | null;
  body_after: string;
  diff_summary?: string | null;
  change_source: 'ai_initial' | 'ai_suggestion' | 'officer_edit' | 'officer_revert';
  edited_by?: string | null;
  edited_at: string;
};

export type TecDraft = {
  id: string;
  tender_id: string;
  state: 'draft' | 'finalised' | 'superseded';
  generated_by: string;
  generated_at: string;
  finalised_at?: string | null;
  finalised_report_id?: string | null;
};

export type StudioDoc = {
  id: string;
  tender_id: string;
  officer_id: string;
  title: string;
  doc_kind: string;
  rendered_body: string;
  state: 'draft' | 'finalised';
  file_path?: string | null;
  sha256_hash?: string | null;
  created_at: string;
  updated_at: string;
  finalised_at?: string | null;
};

export type StudioMessage = {
  id: string;
  document_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  rendered_body?: string | null;
  llm_invocation_id?: string | null;
  timestamp: string;
};
