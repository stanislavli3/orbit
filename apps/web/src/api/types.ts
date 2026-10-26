export interface Project {
  id: number;
  name: string;
  description: string;
  owner: number;
  created_at: string;
  file_count: number;
}

export interface UploadedFile {
  id: number;
  project: number;
  project_name: string | null;
  uploaded_by: number;
  original_name: string;
  description: string;
  file_type: string;
  file_size: number;
  status: 'uploaded' | 'processing' | 'processed' | 'failed';
  category: 'vault' | 'library';
  created_at: string;
}

export interface EngineeringProfile {
  part_number: string | null;
  name: string | null;
  material: { value: string | null; confidence: number } | null;
  category: string | null;
  dimensions: string | null;
  revision: string | null;
  volume: { value: string | null; confidence: number } | null;
  provenance: {
    sources: string[];
    warnings: string[];
  };
}

export interface ExtractionResult {
  schema: string | null;
  file_description: string | null;
  units_hint: string | null;
  confidence: number;
  warnings: string[];
  extracted_at: string;
  profile?: EngineeringProfile;
  // Extended fields from rich extractor
  source_file?: string;
  created_at?: string;
  authoring_system?: string;
  authors?: string[];
  file_size_bytes?: number;
  units?: { length_unit?: string; angle_unit?: string };
  products?: {
    product_names?: string[];
    product_count?: number;
    assembly_relationships?: number;
    component_references?: string[];
    revisions?: string[];
  };
  geometry?: {
    solid_bodies?: number;
    faces?: number;
    edges?: number;
    vertices?: number;
    circles?: number;
    lines?: number;
    coordinate_axes?: number;
    surface_type_breakdown?: Record<string, number>;
    [key: string]: number | Record<string, number> | undefined;
  };
  spatial?: {
    bounding_box_estimate?: { x: number; y: number; z: number };
    coordinate_point_count?: number;
  };
  appearance?: {
    colours_rgb?: { r: number; g: number; b: number }[];
    materials?: string[];
  };
}

export interface HistoryEvent {
  id: string;
  type: 'upload' | 'export' | 'chat';
  title: string;
  project: string;
  status: 'completed' | 'failed' | 'processing' | 'uploaded' | 'processed';
  created_at: string;
  detail: string;
}

export type LibraryDocType =
  | 'avl'
  | 'material-spec'
  | 'compliance'
  | 'previous-bom'
  | 'scorecard'
  | 'standard'
  | 'preferred-materials';

export interface LibraryDocument {
  id: number;
  original_name: string;
  doc_type: LibraryDocType | '';
  file_type: string;
  file_size: number;
  uploaded_at: string;
  bom_run_count: number;
}

export interface BomMatchedContact {
  id: number;
  full_name: string;
  role: string;
  email: string;
  expertise_tags: string[];
  preferred_channel: 'email' | 'slack';
}

export interface BomQuestion {
  id: string;
  type: 'single_select' | 'multi_select' | 'text';
  text: string;
  options?: string[] | null;
  default?: string;
  context_file?: string | null;
  matched_contact?: BomMatchedContact | null;
}

export interface BomQuestionsResponse {
  run_id: number;
  status: string;
  questions: BomQuestion[];
  total: number;
  has_team_contacts: boolean;
}

export interface SupplierQuote {
  id: number;
  supplier_name: string;
  unit_price: string;
  moq: number;
  lead_time_days: number;
  tooling_cost: string;
  landed_cost_usd?: string | null;
  source_url: string;
  notes: string;
  is_avl: boolean;
  is_selected: boolean;
}

export interface BomLineItem {
  id: number;
  file: number | null;
  file_name: string | null;
  part_name: string;
  part_number: string;
  material_spec: string;
  quantity: number;
  status: 'pending' | 'researching' | 'sourced' | 'needs_input';
  quotes: SupplierQuote[];
}

export interface BomResearchRun {
  id: number;
  project: number;
  status: 'gathering_inputs' | 'researching' | 'generating_report' | 'awaiting_team_input' | 'completed' | 'failed';
  inputs_json: Record<string, unknown>;
  research_log: unknown[];
  results_json: Record<string, unknown>;
  excel_s3_key: string;
  line_items: BomLineItem[];
  created_at: string;
  completed_at: string | null;
}

export interface BomExcelDownloadResponse {
  url: string;
  file_size: number | null;
  generated_at: string | null;
  filename: string;
}

export interface BomLogEntry {
  ts: string;
  type: string;
  message: string;
}

export interface BomLogResponse {
  run_id: number;
  status: BomResearchRun['status'];
  entries: BomLogEntry[];
}

export interface TeamContact {
  id: number;
  full_name: string;
  email: string;
  role: string;
  department: string;
  expertise_tags: string[];
  slack_handle: string;
  preferred_channel: 'email' | 'slack';
  notes: string;
  allow_automated: boolean;
  added_by: number;
  created_at: string;
  updated_at: string;
}

export interface GmailCredential {
  id: number;
  gmail_address: string;
  token_expires_at: string | null;
  scopes_json: string[];
  has_refresh_token: boolean;
  created_at: string;
  updated_at: string;
}

export interface GmailCredentialStatus {
  connected: boolean;
  credential: GmailCredential | null;
}

export interface GmailOAuthStartResponse {
  auth_url: string;
}

export interface TeamRequest {
  id: number;
  run: number;
  contact: TeamContact | null;
  line_item: number | null;
  recipient_email: string;
  recipient_name: string;
  question: string;
  question_key: string;
  channel: 'email' | 'slack';
  email_subject: string;
  email_body: string;
  status: 'draft' | 'approved' | 'sent' | 'answered' | 'follow_up';
  response: string;
  gmail_message_id: string;
  gmail_thread_id: string;
  gmail_reply_message_id: string;
  approved_at: string | null;
  sent_at: string | null;
  answered_at: string | null;
  follow_up_count: number;
  last_checked_at: string | null;
  is_overdue: boolean;
  created_at: string;
}

export interface TeamRequestDraftResponse {
  created_count: number;
  requests: TeamRequest[];
  skipped: Array<{ question: string; reason: string }>;
}

export interface TeamRequestApproveAllResponse {
  approved_count: number;
}

export interface TeamRequestSendAllResponse {
  sent_ids: number[];
  error_count: number;
  errors: Array<{ id: number; detail: string }>;
}

export interface TeamRequestPollResponse {
  answered_ids: number[];
  count: number;
}

export interface AssistantSourceFile {
  id: number;
  name: string;
}

export interface AssistantResponse {
  response: string;
  session_id: string;
  sources: number[];
  source_files?: AssistantSourceFile[];
  error?: string;
}

export interface ChatSessionSummary {
  session_id: string;
  title: string;
  is_starred: boolean;
  created_at: string;
}

export interface SessionMessage {
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
}

export interface SessionMessagesResponse {
  session_id: string;
  messages: SessionMessage[];
}

// ── Structured BOM (SCRUM-22) ────────────────────────────────────────────────

export type BomStatus = 'extracting' | 'needs_review' | 'approved' | 'failed';

export interface BomRow {
  id: number;
  line_no: number;
  part_number: string;
  description: string;
  material: string;
  process: string;
  quantity: number;
  spec: string;
  confidence: number;
  flags: string[];
  sources: Record<string, string>;
  edited: boolean;
  needs_review: boolean;
}

export interface Bom {
  id: number;
  reference: string;
  project: number;
  source_file: number | null;
  source_name: string;
  status: BomStatus;
  error: string;
  approved_at: string | null;
  created_at: string;
  review_count: number;
  rows: BomRow[];
}

// ── Part cost history (SCRUM-28 / SCRUM-58) ─────────────────────────────────

export interface RejectedRow {
  row: number;
  errors: string[];
  values: Record<string, string>;
}

export interface CostImportReport {
  filename: string;
  dry_run: boolean;
  total_rows: number;
  valid_rows: number;
  imported_rows: number;
  rejected: RejectedRow[];
  batch_id: number | null;
}

export interface CostImportBatch {
  id: number;
  filename: string;
  total_rows: number;
  imported_rows: number;
  rejected_rows: number;
  is_sample: boolean;
  created_at: string;
}

// ── Estimates + supplier shortlist (SCRUM-59 / thin slice) ──────────────────

export interface EstimateMatch {
  part_id: number;
  part_number: string;
  description: string;
  material: string;
  similarity: number;
  reasons: string[];
  cost: { unit_cost: string; model_year: number | null; program: string; source: string; is_sample: boolean };
  adjusted_unit_cost: string;
}

export interface ShortlistSupplier {
  supplier_id: number;
  supplier: string;
  certifications: string;
  approval: string;
  score: number;
  best_quote: { unit_price: string; lead_time_days: number | null; source: string } | null;
  evidence: { text: string; source: string }[];
}

export interface QuickEstimateRow {
  row_id: number;
  line_no: number;
  part_number: string;
  description: string;
  quantity: number;
  row: BomRow;
  matches: EstimateMatch[];
  estimate: { unit_cost: string; quantity: number; extended_cost: string; currency: string; based_on: string[] } | null;
  assumptions: string[];
  confidence: 'high' | 'medium' | 'low' | 'none';
  uses_sample_data: boolean;
  shortlist: { suppliers: ShortlistSupplier[]; non_approved_left_out: number };
}

export interface QuickEstimateReport {
  bom: { id: number; reference: string; status: BomStatus; error: string; source_name: string; review_count: number };
  rows: QuickEstimateRow[];
  total: { extended_cost: string; currency: string; rows_estimated: number; rows_without_estimate: number };
  inflation: number;
  year: number;
  uses_sample_data: boolean;
  elapsed_ms?: number;
}
