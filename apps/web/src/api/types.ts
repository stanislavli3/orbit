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
