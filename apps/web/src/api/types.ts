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
  uploaded_by: number;
  original_name: string;
  description: string;
  file_type: string;
  file_size: number;
  status: 'uploaded' | 'processing' | 'processed' | 'failed';
  created_at: string;
}

export interface ExtractionResult {
  schema: string | null;
  file_description: string | null;
  units_hint: string | null;
  confidence: number;
  warnings: string[];
  extracted_at: string;
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
  source_url: string;
  notes: string;
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
