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
