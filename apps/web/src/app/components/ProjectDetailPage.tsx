import { useState, useRef, useEffect } from 'react';
import { ArrowLeft, Upload, FileText, Download, Folder, MoreVertical, File, CheckCircle2, Loader2, AlertCircle, ChevronDown, ChevronUp, Pencil, Check, X } from 'lucide-react';
import { Link, useParams } from 'react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useApiClient } from '../../api/client';
import type { Project, UploadedFile, ExtractionResult } from '../../api/types';

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function FileStatusBadge({ status }: { status: UploadedFile['status'] }) {
  if (status === 'processed') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-[#F4F4F4] text-[#6B7280]">
        <CheckCircle2 className="w-3 h-3" strokeWidth={2} />
        Extracted
      </span>
    );
  }
  if (status === 'failed') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-[#FEF2F2] text-[#DC2626]">
        <AlertCircle className="w-3 h-3" strokeWidth={2} />
        Failed
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-[#F4F4F4] text-[#6B7280]">
      <Loader2 className="w-3 h-3 animate-spin" strokeWidth={2} />
      {status === 'processing' ? 'Processing' : 'Uploaded'}
    </span>
  );
}

function SkeletonRow() {
  return (
    <div className="grid grid-cols-12 gap-4 px-6 py-4 border-b border-[#E6E6E6] animate-pulse">
      <div className="col-span-5 flex items-center gap-3">
        <div className="w-9 h-9 bg-[#F4F4F4] rounded-lg flex-shrink-0" />
        <div className="flex-1">
          <div className="h-3 bg-[#F4F4F4] rounded w-2/3 mb-1.5" />
          <div className="h-2.5 bg-[#F4F4F4] rounded w-1/3" />
        </div>
      </div>
      <div className="col-span-2 flex items-center"><div className="h-5 bg-[#F4F4F4] rounded w-12" /></div>
      <div className="col-span-2 flex items-center"><div className="h-3 bg-[#F4F4F4] rounded w-16" /></div>
      <div className="col-span-2 flex items-center"><div className="h-5 bg-[#F4F4F4] rounded w-20" /></div>
      <div className="col-span-1" />
    </div>
  );
}

function ExtractionResultPanel({ fileId, apiFetch }: { fileId: number; apiFetch: ReturnType<typeof useApiClient> }) {
  const { data, isLoading } = useQuery<ExtractionResult>({
    queryKey: ['file-result', fileId],
    queryFn: async () => {
      const res = await apiFetch(`/api/files/${fileId}/result/`);
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
  });

  if (isLoading) {
    return (
      <div className="px-6 pb-4 pt-2 bg-[#FAFAFA] border-t border-[#E6E6E6]">
        <div className="animate-pulse space-y-2">
          <div className="h-3 bg-[#E6E6E6] rounded w-1/3" />
          <div className="h-3 bg-[#E6E6E6] rounded w-1/2" />
        </div>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="px-6 pb-4 pt-3 bg-[#FAFAFA] border-t border-[#E6E6E6]">
      <div className="grid grid-cols-3 gap-4 text-[12px]">
        {data.schema && (
          <div>
            <p className="text-[#9CA3AF] uppercase tracking-wide mb-0.5">Schema</p>
            <p className="text-[#111111] font-medium truncate">{data.schema}</p>
          </div>
        )}
        {data.units_hint && (
          <div>
            <p className="text-[#9CA3AF] uppercase tracking-wide mb-0.5">Units</p>
            <p className="text-[#111111] font-medium">{data.units_hint}</p>
          </div>
        )}
        {data.confidence != null && (
          <div>
            <p className="text-[#9CA3AF] uppercase tracking-wide mb-0.5">Confidence</p>
            <p className="text-[#111111] font-medium">{Math.round(data.confidence * 100)}%</p>
          </div>
        )}
        {data.file_description && (
          <div className="col-span-3">
            <p className="text-[#9CA3AF] uppercase tracking-wide mb-0.5">Description</p>
            <p className="text-[#111111]">{data.file_description}</p>
          </div>
        )}
        {data.warnings?.length > 0 && (
          <div className="col-span-3">
            <p className="text-[#9CA3AF] uppercase tracking-wide mb-0.5">Warnings</p>
            <ul className="space-y-0.5">
              {data.warnings.map((w, i) => (
                <li key={i} className="text-[#DC2626]">{w}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

function FileRow({ file, apiFetch }: { file: UploadedFile; apiFetch: ReturnType<typeof useApiClient> }) {
  const [expanded, setExpanded] = useState(false);
  const [editingDesc, setEditingDesc] = useState(false);
  const [descValue, setDescValue] = useState(file.description || '');
  const [savingDesc, setSavingDesc] = useState(false);

  useEffect(() => {
    if (!editingDesc) setDescValue(file.description || '');
  }, [file.description, editingDesc]);
  const queryClient = useQueryClient();

  const saveDescription = async () => {
    setSavingDesc(true);
    try {
      await apiFetch(`/api/files/${file.id}/description/`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ description: descValue }),
      });
      await queryClient.invalidateQueries({ queryKey: ['project-files'] });
    } finally {
      setSavingDesc(false);
      setEditingDesc(false);
    }
  };

  const cancelEdit = () => {
    setDescValue(file.description || '');
    setEditingDesc(false);
  };

  return (
    <>
      <div className="border-b border-[#E6E6E6] last:border-b-0 hover:bg-[#FAFAFA] transition-colors group">
        <div className="grid grid-cols-12 gap-4 px-6 py-4">
          <div className="col-span-5 flex items-center gap-3">
            <div className="w-9 h-9 bg-[#F4F4F4] rounded-lg flex items-center justify-center flex-shrink-0">
              <File className="w-[18px] h-[18px] text-[#6B7280]" strokeWidth={1.5} />
            </div>
            <div className="min-w-0">
              <p className="text-[#111111] text-sm mb-0.5 truncate">{file.original_name}</p>
              <p className="text-[#6B7280] text-[12px]">Uploaded {formatDate(file.created_at)}</p>
            </div>
          </div>
          <div className="col-span-2 flex items-center">
            <span className="px-2 py-1 bg-[#F4F4F4] text-[#6B7280] rounded text-[11px] font-medium uppercase">
              {file.file_type || '—'}
            </span>
          </div>
          <div className="col-span-2 flex items-center">
            <span className="text-[#6B7280] text-sm">{formatBytes(file.file_size)}</span>
          </div>
          <div className="col-span-2 flex items-center">
            <FileStatusBadge status={file.status} />
          </div>
          <div className="col-span-1 flex items-center justify-end gap-1">
            <button
              onClick={() => setExpanded((v) => !v)}
              className="w-8 h-8 flex items-center justify-center hover:bg-[#E6E6E6] rounded-lg transition-colors"
              title="Expand"
            >
              {expanded
                ? <ChevronUp className="w-4 h-4 text-[#6B7280]" />
                : <ChevronDown className="w-4 h-4 text-[#6B7280]" />}
            </button>
            <button className="w-8 h-8 flex items-center justify-center hover:bg-[#E6E6E6] rounded-lg transition-colors opacity-0 group-hover:opacity-100">
              <MoreVertical className="w-4 h-4 text-[#6B7280]" />
            </button>
          </div>
        </div>

        {/* Description row — always visible */}
        <div className="px-6 pb-3 flex items-start gap-2">
          <div className="w-9 flex-shrink-0" />
          {editingDesc ? (
            <div className="flex-1 flex items-start gap-2">
              <textarea
                autoFocus
                value={descValue}
                onChange={(e) => setDescValue(e.target.value)}
                placeholder="Add a description: what is this file, its characteristics, any useful context…"
                className="flex-1 text-[12px] text-[#111111] border border-[#E6E6E6] rounded-lg px-3 py-2 resize-none focus:outline-none focus:ring-1 focus:ring-[#111111] bg-white min-h-[72px]"
              />
              <div className="flex flex-col gap-1 pt-1">
                <button
                  onClick={saveDescription}
                  disabled={savingDesc}
                  className="w-7 h-7 flex items-center justify-center bg-[#111111] text-white rounded-lg hover:bg-[#2A2A2A] disabled:opacity-50 transition-colors"
                >
                  {savingDesc ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
                </button>
                <button
                  onClick={cancelEdit}
                  className="w-7 h-7 flex items-center justify-center hover:bg-[#E6E6E6] rounded-lg transition-colors"
                >
                  <X className="w-3.5 h-3.5 text-[#6B7280]" />
                </button>
              </div>
            </div>
          ) : file.status === 'processing' || file.status === 'uploaded' ? (
            <span className="text-[12px] text-[#9CA3AF] italic flex items-center gap-1.5">
              <Loader2 className="w-3 h-3 animate-spin" strokeWidth={1.5} />
              Generating description…
            </span>
          ) : (
            <button
              onClick={() => setEditingDesc(true)}
              className="flex-1 text-left group/desc"
            >
              {descValue ? (
                <span className="text-[12px] text-[#6B7280] line-clamp-2 group-hover/desc:text-[#111111] transition-colors">
                  {descValue}
                </span>
              ) : (
                <span className="text-[12px] text-[#D1D5DB] italic group-hover/desc:text-[#9CA3AF] transition-colors flex items-center gap-1.5">
                  <Pencil className="w-3 h-3" strokeWidth={1.5} />
                  Add description…
                </span>
              )}
            </button>
          )}
        </div>
      </div>

      {expanded && file.status === 'processed' && (
        <ExtractionResultPanel fileId={file.id} apiFetch={apiFetch} />
      )}
    </>
  );
}

export function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [activeTab, setActiveTab] = useState<'vault' | 'library'>('vault');
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const apiFetch = useApiClient();
  const queryClient = useQueryClient();

  const { data: project, isLoading: projectLoading, isError: projectError } = useQuery<Project>({
    queryKey: ['project', id],
    queryFn: async () => {
      const res = await apiFetch(`/api/projects/${id}/`);
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
    enabled: !!id,
  });

  const { data: files, isLoading: filesLoading, isError: filesError } = useQuery<UploadedFile[]>({
    queryKey: ['project-files', id],
    queryFn: async () => {
      const res = await apiFetch(`/api/files/project/${id}/`);
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
    enabled: !!id,
    refetchInterval: (query) => {
      const data = query.state.data as UploadedFile[] | undefined;
      return data?.some((f) => f.status === 'processing' || f.status === 'uploaded') ? 3000 : false;
    },
  });

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !id) return;
    setUploadError('');
    setUploading(true);
    try {
      const form = new FormData();
      form.append('file', file);
      form.append('project_id', id);
      const res = await apiFetch('/api/files/upload/', { method: 'POST', body: form });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.detail ?? err?.error ?? `Upload failed (${res.status})`);
      }
      await queryClient.invalidateQueries({ queryKey: ['project-files', id] });
      await queryClient.invalidateQueries({ queryKey: ['project', id] });
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  if (projectError) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-[#6B7280]">Project not found or access denied.</p>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">
      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".step,.stp,.pdf,.dwg,.dxf,.iges,.igs"
        className="hidden"
        onChange={handleFileChange}
      />

      {/* Header */}
      <div className="border-b border-[#E6E6E6] bg-white px-8 py-5">
        <div className="flex items-center gap-3 mb-4">
          <Link
            to="/vault"
            className="w-8 h-8 flex items-center justify-center hover:bg-[#F4F4F4] rounded-lg transition-colors"
          >
            <ArrowLeft className="w-[18px] h-[18px] text-[#6B7280]" />
          </Link>
          <div className="flex-1">
            {projectLoading ? (
              <div className="animate-pulse">
                <div className="h-5 bg-[#F4F4F4] rounded w-48 mb-1.5" />
                <div className="h-3.5 bg-[#F4F4F4] rounded w-32" />
              </div>
            ) : project ? (
              <>
                <h1 className="text-[#111111] mb-1">{project.name}</h1>
                <p className="text-[#6B7280] text-sm">
                  {project.file_count} files · Created {formatDate(project.created_at)}
                </p>
              </>
            ) : null}
          </div>
          <div className="flex items-center gap-2">
            {uploadError && (
              <span className="text-[12px] text-[#DC2626] max-w-xs truncate">{uploadError}</span>
            )}
            <button className="px-4 py-2 bg-white border border-[#E6E6E6] rounded-lg hover:bg-[#FAFAFA] transition-colors text-sm text-[#111111]">
              <Download className="w-4 h-4 inline mr-2" strokeWidth={1.5} />
              Export
            </button>
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="px-4 py-2 bg-[#111111] text-white rounded-lg hover:bg-[#2A2A2A] disabled:opacity-60 transition-colors text-sm flex items-center gap-2"
            >
              {uploading
                ? <><Loader2 className="w-4 h-4 animate-spin" strokeWidth={1.5} /> Uploading…</>
                : <><Upload className="w-4 h-4" strokeWidth={1.5} /> Upload files</>}
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex items-center gap-6 border-b border-[#E6E6E6] -mb-5">
          <button
            onClick={() => setActiveTab('vault')}
            className={`pb-4 border-b-2 transition-colors ${
              activeTab === 'vault' ? 'border-[#111111] text-[#111111]' : 'border-transparent text-[#6B7280] hover:text-[#111111]'
            }`}
          >
            <span className="text-sm flex items-center gap-2">
              <Folder className="w-4 h-4" strokeWidth={1.5} />
              Vault
            </span>
          </button>
          <button
            onClick={() => setActiveTab('library')}
            className={`pb-4 border-b-2 transition-colors ${
              activeTab === 'library' ? 'border-[#111111] text-[#111111]' : 'border-transparent text-[#6B7280] hover:text-[#111111]'
            }`}
          >
            <span className="text-sm flex items-center gap-2">
              <FileText className="w-4 h-4" strokeWidth={1.5} />
              Library
            </span>
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto bg-[#F7F7F7]">
        <div className="max-w-[1400px] mx-auto px-8 py-8">
          {activeTab === 'vault' ? (
            <div className="bg-white border border-[#E6E6E6] rounded-xl overflow-hidden">
              <div className="grid grid-cols-12 gap-4 px-6 py-3 border-b border-[#E6E6E6] bg-[#FAFAFA]">
                <div className="col-span-5"><span className="text-[#6B7280] text-[12px] font-medium uppercase tracking-wide">Name</span></div>
                <div className="col-span-2"><span className="text-[#6B7280] text-[12px] font-medium uppercase tracking-wide">Type</span></div>
                <div className="col-span-2"><span className="text-[#6B7280] text-[12px] font-medium uppercase tracking-wide">Size</span></div>
                <div className="col-span-2"><span className="text-[#6B7280] text-[12px] font-medium uppercase tracking-wide">Status</span></div>
                <div className="col-span-1 flex justify-end"><span className="text-[#6B7280] text-[12px] font-medium uppercase tracking-wide">Actions</span></div>
              </div>

              {filesLoading && Array.from({ length: 4 }).map((_, i) => <SkeletonRow key={i} />)}

              {filesError && (
                <div className="px-6 py-8 text-center">
                  <p className="text-[#6B7280] text-sm">Failed to load files.</p>
                </div>
              )}

              {files && files.length === 0 && (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <div className="w-10 h-10 bg-[#F4F4F4] rounded-lg flex items-center justify-center mb-3">
                    <File className="w-5 h-5 text-[#6B7280]" strokeWidth={1.5} />
                  </div>
                  <p className="text-[#111111] text-sm font-medium mb-1">No files uploaded yet</p>
                  <p className="text-[#6B7280] text-[12px]">Click "Upload files" to add STEP, PDF, or CAD files.</p>
                </div>
              )}

              {files && files.map((file) => (
                <FileRow key={file.id} file={file} apiFetch={apiFetch} />
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <div className="w-12 h-12 bg-[#F4F4F4] rounded-xl flex items-center justify-center mb-4">
                <FileText className="w-6 h-6 text-[#6B7280]" strokeWidth={1.5} />
              </div>
              <p className="text-[#111111] font-medium mb-1">Extraction profiles coming soon</p>
              <p className="text-[#6B7280] text-sm">Once files are processed, structured profiles will appear here.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
