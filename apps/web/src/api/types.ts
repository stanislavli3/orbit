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
  source?: 'upload' | 'local_folder' | 'google_drive';
  source_name?: string | null;
  connected_source?: number | null;
  external_url?: string;
  owner?: string | null;
  last_editor?: string | null;
  source_modified_at?: string | null;
}

export type ConnectorKind = 'local_folder' | 'google_drive';

export interface ConnectedSource {
  id: number;
  project: number;
  kind: ConnectorKind;
  name: string;
  config: { path?: string; folder_id?: string };
  last_indexed_at: string | null;
  last_error: string;
  file_count: number;
  created_at: string;
}

export type ConnectorStatus = Record<ConnectorKind, { configured: boolean; detail: string }>;

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
  is_cots: boolean;
  is_cots_source: 'agent' | 'human' | 'backfill';
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
  revision: string;
  confidence: number;
  flags: string[];
  sources: Record<string, string>;
  edited: boolean;
  needs_review: boolean;
  /** SCRUM-74: prototype / entered unit price and where it came from. */
  entered_price: string | null;
  entered_price_note: string;
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

// ── Design change review (SCRUM-23 / SCRUM-55) ──────────────────────────────

export interface BomCitation {
  bom_id: number;
  reference: string;
  source_name: string;
  row_id: number | null;
  line_no: number | null;
  part_number: string;
}

export interface BomFieldChange {
  field: string;
  before: string | number;
  after: string | number;
}

export interface BomConflict {
  kind: 'part_number' | 'revision' | 'material' | 'tolerance';
  title: string;
  detail: string;
  citations: BomCitation[];
}

export interface BomNeighbours {
  method: 'placement_distance' | 'assembly_structure' | 'not_in_assembly';
  radius: number;
  parts: { part_number: string; distance: number | null; reason: string }[];
}

export interface BomComparison {
  base: { id: number; reference: string; source_name: string };
  target: { id: number; reference: string; source_name: string };
  summary: string;
  added: { part_number: string; row: BomCitation }[];
  removed: { part_number: string; row: BomCitation }[];
  changed: { part_number: string; fields: BomFieldChange[]; rows: BomCitation[] }[];
  conflicts: BomConflict[];
  recheck: Record<string, BomNeighbours>;
  assembly: { bom_id: number; reference: string; source_name: string } | null;
  galvanic?: GalvanicReport;
}

// ── Galvanic material pairs (SCRUM-77) / buyer handoff (SCRUM-69) ───────────

export interface GalvanicFlag {
  kind: 'galvanic';
  severity: 'high' | 'medium';
  environment: 'general' | 'harsh';
  parts: string[];
  materials: string[];
  anodic_index: number[];
  difference_v: number;
  threshold_v: number;
  corrodes: string;
  title: string;
  detail: string;
  mitigations: string[];
}

export interface GalvanicReport {
  method: 'placement_distance' | 'assembly_structure' | 'same_bom';
  environment: 'general' | 'harsh';
  threshold_v: number;
  flags: GalvanicFlag[];
  note: string;
  table: { material: string; anodic_index: number }[];
}

export interface HandoffLine {
  row_id: number;
  line_no: number;
  part_number: string;
  description: string;
  material: string;
  process: string;
  quantity: number;
  spec: string;
  revision: string;
  explanation: string;
  explanation_source: 'rules' | 'claude';
  cost: {
    should_cost: { low: string; expected: string; high: string; confidence: string };
    historical: { unit_cost: string; based_on: string[] } | null;
    low: string;
    high: string;
    currency: string;
  };
  supplier: { supplier: string; approval: string; certifications: string; best_quote: { unit_price: string; lead_time_days: number | null } | null } | null;
  alternates: string[];
  open_questions: string[];
}

export interface BomHandoff {
  bom: { id: number; reference: string; status: string; source_name: string; review_count: number };
  lines: HandoffLine[];
  total: { low: string; high: string; currency: string };
  open_question_count: number;
  galvanic: GalvanicReport;
  uses_sample_data: boolean;
  note: string;
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
  kind?: 'cost' | 'spend';
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
  /** Trade-offs against the other suppliers on the same shortlist (SCRUM-29). */
  pros: string[];
  cons: string[];
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
  should_cost: ShouldCost;
  /** SCRUM-73: one low / likely / high range combining history and the model. */
  cost_range: CostRange;
  /** SCRUM-74: null when no price was entered for the line. */
  price_flag: PriceFlag | null;
  /** SCRUM-61: lead-time estimate and which data it came from. */
  lead_time: LeadTimeEstimate;
}

export interface LeadTimeEstimate {
  days: number | null;
  basis: 'quote_history' | 'similar_parts' | 'no_data';
  source: string;
  evidence: { text: string; source: string }[];
  is_bottleneck: boolean;
}

export interface CriticalPath {
  row_id: number;
  part_number: string;
  days: number;
  source: string;
  summary: string;
  rows_without_data: number;
}

/** SCRUM-60: rules-based cost-reduction ideas for one BOM line. */
export interface CostReductionSuggestion {
  rank: number;
  kind: 'material' | 'supplier' | 'volume' | 'cots' | 'tolerance' | 'fastener_count';
  title: string;
  rationale: string;
  estimated_saving_pct: number;
  estimated_saving_per_unit: string | null;
  evidence: { text: string; source: string }[];
  assumption: string | null;
  meets_target: boolean;
}

export interface CostReductionReport {
  row_id: number;
  part_number: string;
  target_pct: number;
  baseline: { unit_cost: string | null; basis: string };
  suggestions: CostReductionSuggestion[];
  target_met: boolean;
  questions: string[];
  disclaimer: string;
}

/** Material/process/volume should-cost range from assumed reference rates (SCRUM-30). */
export interface ShouldCost {
  low: string;
  expected: string;
  high: string;
  currency: string;
  spread: number;
  material: string;
  process: string;
  quantity: number;
  basis: string[];
  confidence: 'medium' | 'medium-low' | 'low';
  is_assumed: boolean;
}

export interface CostRange {
  low: string;
  likely: string;
  high: string;
  currency: string;
  basis: 'model' | 'history + model';
  method: string;
  history_unit_cost: string | null;
  model_unit_cost: string;
  similar_parts: {
    part_number: string;
    description: string;
    similarity: number;
    unit_cost: string;
    source: string;
    model_year: number | null;
    program: string;
    is_sample: boolean;
  }[];
  rates: string[];
  uses_sample_data: boolean;
}

export interface PriceFlag {
  entered_price: string;
  note: string;
  margin: number;
  level: 'ok' | 'far_below' | 'far_above';
  pct_from_range: number;
  message: string;
}

export interface PriceFlagSummary {
  margin: number;
  priced: number;
  far_below: number;
  far_above: number;
}

export interface QuickEstimateReport {
  bom: { id: number; reference: string; status: BomStatus; error: string; source_name: string; review_count: number };
  rows: QuickEstimateRow[];
  total: { extended_cost: string; currency: string; rows_estimated: number; rows_without_estimate: number };
  inflation: number;
  year: number;
  uses_sample_data: boolean;
  critical_path: CriticalPath | null;
  price_flags: PriceFlagSummary;
  elapsed_ms?: number;
}

// ── Call sheets (SCRUM-71), part compare (SCRUM-53), handoff timing (SCRUM-75) ──

export interface CallSheet {
  supplier: { id: number; name: string; contact_email: string; certifications: string; approval: string };
  bom_reference: string;
  line_no: number;
  part_summary: string;
  specs: { label: string; value: string; source: string }[];
  volume_and_timing: {
    quantity: number;
    last_quote: string | null;
    last_lead_time_days: number | null;
    needed_by: string;
  };
  pros: string[];
  cons: string[];
  evidence: { text: string; source: string }[];
  questions: string[];
}

export interface CompareSide {
  kind: 'part' | 'bom_row';
  id: number;
  link: string;
  values: Record<string, string>;
  sources: Record<string, string>;
}

export interface PartComparison {
  left: CompareSide;
  right: CompareSide;
  rows: { key: string; label: string; left: string; right: string; same: boolean }[];
}

export type HandoffStepKey = 'cad_finished' | 'bom_shared' | 'shortlist_ready' | 'quote_received' | 'quote_accepted';

export interface HandoffInterval {
  from: HandoffStepKey;
  to: HandoffStepKey;
  label: string;
  hours: number;
}

export interface HandoffTimeline {
  bom_id: number;
  reference: string;
  steps: { key: HandoffStepKey; label: string }[];
  parts: {
    part_number: string;
    steps: Record<HandoffStepKey, string | null>;
    manual: HandoffStepKey[];
    intervals: HandoffInterval[];
    total_hours: number | null;
    slowest: HandoffInterval | null;
  }[];
  total_hours: number | null;
  slowest_step: { label: string; median_hours: number } | null;
}

export interface HandoffSummary {
  parts_timed: number;
  median_total_hours: number | null;
  median_step_hours: { label: string; median_hours: number }[];
}

// ── Design review (SCRUM-57 / SCRUM-56) ─────────────────────────────────────

export type ReviewRole = 'designer' | 'reviewer';

export interface ProjectMember {
  id: number;
  user: number;
  username: string;
  role: ReviewRole;
  created_at: string;
}

export interface MembersResponse {
  is_owner: boolean;
  my_role: ReviewRole | null;
  members: ProjectMember[];
}

export interface ChangeEvent {
  id: number;
  actor: string;
  action: 'created' | 'approved' | 'rejected' | 'interference_check';
  comment: string;
  data: Record<string, unknown>;
  created_at: string;
}

export interface InterferencePair {
  part_a: string;
  part_b: string;
  interferes: boolean;
  overlap_volume: number;
}

export interface InterferenceCheck {
  id: number;
  changed_part: string;
  neighbours: string[];
  source: string;
  results: InterferencePair[];
  elapsed_ms: number;
  manual_baseline_minutes: number | null;
  created_at: string;
}

export interface DesignChange {
  id: number;
  project: number;
  title: string;
  description: string;
  author: string;
  files: number[];
  parts: string[];
  state: 'pending' | 'approved' | 'rejected';
  created_at: string;
  events: ChangeEvent[];
  interference_checks: InterferenceCheck[];
}

export interface RfqDraft {
  id: number;
  bom_row: number;
  bom_reference: string;
  bom_id: number;
  status: RfqStatus;
  part_number: string;
  supplier_name: string;
  supplier_email: string;
  row_sourcing_status: '' | 'rfq_sent' | 'sourced';
  demo_mode: boolean;
  gmail_message_id: string;
  gmail_thread_id: string;
  sent_at: string | null;
  send_error: string;
  last_checked_at: string | null;
  replied_at: string | null;
  reply_text: string;
  parsed_reply: RfqParsedReply;
  needs_attention: boolean;
  attention_reason: string;
  excluded_suppliers: string[];
  next_suppliers: { supplier: string; supplier_id: number; best_quote: { unit_price: string; lead_time_days: number | null; source: string } | null }[];
  quote: number | null;
  part_context: string;
  material: string;
  blank_size: string;
  tolerance: string;
  process: string;
  quantity: number | null;
  due_date: string | null;
  notes: string;
  assumptions: string[];
  created_at: string;
  updated_at: string;
}

// ── Unverified supplier research (SCRUM-70) ─────────────────────────────────

export interface ResearchedSupplier {
  supplier: string;
  unit_price: string | null;
  lead_time_days: number | null;
  risk_notes: string[];
  sources: string[];
  origin: 'web' | 'part_history';
  verified: false;
}

export interface SupplierResearch {
  id: number;
  row_id: number;
  mode: 'web' | 'history';
  note: string;
  status: 'UNVERIFIED';
  results: ResearchedSupplier[];
  created_at: string;
}

export type RfqStatus =
  | 'draft' | 'final' | 'sent' | 'send_failed' | 'needs_review'
  | 'quoted' | 'declined' | 'info_requested' | 'escalated';

export interface RfqParsedReply {
  intent?: 'quote' | 'decline' | 'info_request' | 'unknown';
  unit_price?: string | null;
  lead_time_days?: number | null;
  moq?: number | null;
  notes?: string;
  confidence?: number;
}

// ── Standards & permit check (SCRUM-37/38) ──────────────────────────────────
export type ComplianceStatus = 'pass' | 'warning' | 'needs_info';

export interface ComplianceFinding {
  status: ComplianceStatus;
  severity: 'info' | 'low' | 'medium' | 'high';
  message: string;
  rule: { id: string; title: string; citation: string; explanation: string } | null;
}

export interface ComplianceLine {
  row_id: number;
  line_no: number;
  part_number: string;
  status: ComplianceStatus;
  findings: ComplianceFinding[];
}

export interface BomCompliance {
  bom_id: number;
  reference: string;
  corpus: { label: string; version: string };
  summary: Record<ComplianceStatus, number>;
  lines: ComplianceLine[];
}

/** SCRUM-24: one hit from /api/assistant/search/. */
export interface SearchHit {
  type: 'file' | 'bom_row' | 'part' | 'quote' | 'supplier';
  id: number;
  title: string;
  snippet: string;
  citation: string;
  link: string;
  score: number;
}

export interface SearchResponse {
  query: string;
  groups: Record<'files' | 'bom_rows' | 'parts' | 'quotes' | 'suppliers', SearchHit[]>;
  total: number;
}

/** SCRUM-25: /api/assistant/ask/ answer with numbered cited sources. */
export interface AskSource {
  n: number;
  title: string;
  snippet: string;
  citation: string;
  link: string;
}

export interface AskResponse {
  answer: string;
  mode: 'ai' | 'retrieval_only';
  focus: string;
  sources: AskSource[];
}

// SCRUM-52 — Settings -> Workspace sources
export type WorkspaceSourceKind = 'local_folder' | 'google_drive' | 'cost_import' | 'supplier_list' | 'plm' | 'other';

export interface WorkspaceSource {
  id: number;
  kind: WorkspaceSourceKind;
  name: string;
  location: string;
  config: Record<string, unknown>;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface WorkspaceSourcesOverview {
  sources: WorkspaceSource[];
  kinds: { value: WorkspaceSourceKind; label: string }[];
  cost_imports: { id: number; filename: string; imported_rows: number; created_at: string }[];
  supplier_counts: { total: number; approved: number };
}

export interface SupplierSetting {
  id: number;
  name: string;
  contact_email: string;
  certifications: string;
  is_approved: boolean;
  approval_note: string;
}
