import { useState, useRef, useEffect, useCallback } from 'react';
import {
  ArrowLeft, Upload, FileText, Download, Folder, MoreVertical,
  CheckCircle2, Loader2, AlertCircle, ChevronDown, ChevronUp,
  Pencil, Check, X, CloudUpload,
} from 'lucide-react';
import { Link, useParams } from 'react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useApiClient } from '../../api/client';
import type { Project, UploadedFile, ExtractionResult } from '../../api/types';

// ─── Utilities ───────────────────────────────────────────────────────────────

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

// ─── File type icon ───────────────────────────────────────────────────────────

const FILE_TYPE_CONFIG: Record<string, { bg: string; text: string; label: string; accent: string }> = {
  step: { bg: 'bg-blue-50',    text: 'text-blue-600',    label: 'STP', accent: '#93C5FD' },
  stp:  { bg: 'bg-blue-50',    text: 'text-blue-600',    label: 'STP', accent: '#93C5FD' },
  pdf:  { bg: 'bg-red-50',     text: 'text-red-500',     label: 'PDF', accent: '#FCA5A5' },
  dwg:  { bg: 'bg-amber-50',   text: 'text-amber-600',   label: 'DWG', accent: '#FCD34D' },
  dxf:  { bg: 'bg-amber-50',   text: 'text-amber-600',   label: 'DXF', accent: '#FCD34D' },
  iges: { bg: 'bg-emerald-50', text: 'text-emerald-600', label: 'IGS', accent: '#6EE7B7' },
  igs:  { bg: 'bg-emerald-50', text: 'text-emerald-600', label: 'IGS', accent: '#6EE7B7' },
};

function FileTypeIcon({ type }: { type: string }) {
  const c = FILE_TYPE_CONFIG[type?.toLowerCase()] ?? { bg: 'bg-[#F4F4F4]', text: 'text-[#6B7280]', label: type?.toUpperCase().slice(0, 3) || '—', accent: '#E6E6E6' };
  return (
    <div className={`w-9 h-9 ${c.bg} rounded-lg flex items-center justify-center flex-shrink-0`}>
      <span className={`text-[10px] font-bold tracking-wide ${c.text}`}>{c.label}</span>
    </div>
  );
}

function fileAccent(type: string): string {
  return FILE_TYPE_CONFIG[type?.toLowerCase()]?.accent ?? '#E6E6E6';
}

// ─── Status badge ─────────────────────────────────────────────────────────────

function FileStatusBadge({ status }: { status: UploadedFile['status'] }) {
  if (status === 'processed') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-emerald-50 text-emerald-700">
        <CheckCircle2 className="w-3 h-3" strokeWidth={2.5} />
        Extracted
      </span>
    );
  }
  if (status === 'failed') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-red-50 text-red-600">
        <AlertCircle className="w-3 h-3" strokeWidth={2} />
        Failed
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-[#F4F4F4] text-[#6B7280]">
      <Loader2 className="w-3 h-3 animate-spin" strokeWidth={2} />
      {status === 'processing' ? 'Processing' : 'Queued'}
    </span>
  );
}

// ─── Upload progress item ─────────────────────────────────────────────────────

interface UploadingFile {
  id: string;
  name: string;
  size: number;
  progress: number;
  status: 'uploading' | 'done' | 'error';
  error?: string;
}

function UploadProgressItem({ file }: { file: UploadingFile }) {
  const ext = file.name.split('.').pop() ?? '';
  return (
    <div className="flex items-center gap-3 px-6 py-3.5 border-b border-[#F0F0F0] last:border-b-0 bg-[#FAFAFA]">
      <FileTypeIcon type={ext} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-[13px] text-[#111111] font-medium truncate pr-4">{file.name}</span>
          <span className="text-[11px] text-[#6B7280] flex-shrink-0 tabular-nums">
            {file.status === 'error' ? (
              <span className="text-red-500">Failed</span>
            ) : file.status === 'done' ? (
              <span className="text-emerald-600 flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3" strokeWidth={2.5} /> Uploaded
              </span>
            ) : (
              `${file.progress}%`
            )}
          </span>
        </div>
        <div className="h-[3px] bg-[#E6E6E6] rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-200 ease-out ${
              file.status === 'error' ? 'bg-red-400' :
              file.status === 'done'  ? 'bg-emerald-500' : 'bg-[#111111]'
            }`}
            style={{ width: `${file.progress}%` }}
          />
        </div>
        {file.error && (
          <p className="text-[11px] text-red-500 mt-1">{file.error}</p>
        )}
      </div>
    </div>
  );
}

// ─── Skeleton row ─────────────────────────────────────────────────────────────

function SkeletonRow() {
  return (
    <div className="px-6 py-4 border-b border-[#F0F0F0] animate-pulse">
      <div className="flex items-center gap-3 mb-3">
        <div className="w-9 h-9 bg-[#F4F4F4] rounded-lg flex-shrink-0" />
        <div className="flex-1">
          <div className="h-3 bg-[#F4F4F4] rounded w-2/5 mb-1.5" />
          <div className="h-2.5 bg-[#F4F4F4] rounded w-1/4" />
        </div>
        <div className="h-6 bg-[#F4F4F4] rounded-full w-20" />
        <div className="h-3 bg-[#F4F4F4] rounded w-12" />
      </div>
      <div className="ml-12 h-2.5 bg-[#F4F4F4] rounded w-3/4" />
    </div>
  );
}

// ─── Confidence meter ─────────────────────────────────────────────────────────

function ConfidenceMeter({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color = pct >= 80 ? 'bg-emerald-500' : pct >= 50 ? 'bg-amber-400' : 'bg-red-400';
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-[#E6E6E6] rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[12px] font-medium text-[#111111] tabular-nums w-8 text-right">{pct}%</span>
    </div>
  );
}

// ─── Extraction result panel ──────────────────────────────────────────────────

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
      <div className="mx-6 mb-4 mt-1 rounded-xl border border-[#E6E6E6] p-4 bg-[#FAFAFA] animate-pulse space-y-2">
        <div className="h-2.5 bg-[#E6E6E6] rounded w-1/3" />
        <div className="h-2.5 bg-[#E6E6E6] rounded w-1/2" />
      </div>
    );
  }
  if (!data) return null;

  const pct = data.confidence != null ? Math.round(data.confidence * 100) : null;
  const confColor = pct == null ? '' : pct >= 80 ? 'bg-emerald-50 text-emerald-700' : pct >= 50 ? 'bg-amber-50 text-amber-700' : 'bg-red-50 text-red-600';

  return (
    <div className="mx-5 mb-4 mt-1 rounded-xl border border-[#E6E6E6] bg-white overflow-hidden shadow-sm">
      {/* Panel header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-[#F0F0F0] bg-[#FAFAFA]">
        <p className="text-[10px] font-semibold text-[#9CA3AF] uppercase tracking-widest">Extraction result</p>
        {pct != null && (
          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold ${confColor}`}>
            <CheckCircle2 className="w-2.5 h-2.5" strokeWidth={2.5} />
            {pct}% confidence
          </span>
        )}
      </div>

      <div className="p-4 space-y-3">
        {/* Schema + Units row */}
        {(data.schema || data.units_hint) && (
          <div className="grid grid-cols-2 gap-4">
            {data.schema && (
              <div>
                <p className="text-[10px] font-semibold text-[#C4C4C4] uppercase tracking-widest mb-1">Schema</p>
                <p className="text-[12px] text-[#111111] font-medium truncate">{data.schema}</p>
              </div>
            )}
            {data.units_hint && (
              <div>
                <p className="text-[10px] font-semibold text-[#C4C4C4] uppercase tracking-widest mb-1">Units</p>
                <p className="text-[12px] text-[#111111] font-medium">{data.units_hint}</p>
              </div>
            )}
          </div>
        )}

        {/* Confidence bar */}
        {pct != null && (
          <div>
            <ConfidenceMeter value={data.confidence} />
          </div>
        )}

        {/* Description */}
        {data.file_description && (
          <div className="pt-1 border-t border-[#F7F7F7]">
            <p className="text-[10px] font-semibold text-[#C4C4C4] uppercase tracking-widest mb-1.5">File description</p>
            <p className="text-[12px] text-[#374151] leading-relaxed">{data.file_description}</p>
          </div>
        )}

        {/* Warnings */}
        {data.warnings?.length > 0 && (
          <div className="pt-1 border-t border-[#F7F7F7] space-y-1">
            {data.warnings.map((w, i) => (
              <p key={i} className="text-[11px] text-amber-600 flex items-start gap-1.5">
                <AlertCircle className="w-3 h-3 mt-0.5 flex-shrink-0" strokeWidth={2} />
                {w}
              </p>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── File row ─────────────────────────────────────────────────────────────────

function FileRow({ file, apiFetch }: { file: UploadedFile; apiFetch: ReturnType<typeof useApiClient> }) {
  const [expanded, setExpanded] = useState(false);
  const [editingDesc, setEditingDesc] = useState(false);
  const [descValue, setDescValue] = useState(file.description || '');
  const [savingDesc, setSavingDesc] = useState(false);
  const queryClient = useQueryClient();
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!editingDesc) setDescValue(file.description || '');
  }, [file.description, editingDesc]);

  useEffect(() => {
    if (editingDesc && textareaRef.current) {
      textareaRef.current.focus();
      textareaRef.current.selectionStart = textareaRef.current.value.length;
    }
  }, [editingDesc]);

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

  const isProcessing = file.status === 'processing' || file.status === 'uploaded';

  const accent = fileAccent(file.file_type);

  return (
    <div
      className="border-b border-[#F0F0F0] last:border-b-0 group transition-all hover:bg-[#FAFAFA]/70 relative"
      style={{ borderLeft: `3px solid ${expanded ? accent : 'transparent'}`, transition: 'border-left-color 0.15s ease' }}
    >
      {/* Main row */}
      <div className="flex items-center gap-3 px-5 py-3.5">
        <FileTypeIcon type={file.file_type} />

        {/* Name + date */}
        <div className="flex-1 min-w-0">
          <p className="text-[13px] font-medium text-[#111111] truncate leading-tight">{file.original_name}</p>
          <p className="text-[11px] text-[#9CA3AF] mt-0.5">{formatDate(file.created_at)} · {formatBytes(file.file_size)}</p>
        </div>

        {/* Status */}
        <FileStatusBadge status={file.status} />

        {/* Actions */}
        <div className="flex items-center gap-1 ml-2">
          <button
            onClick={() => setExpanded(v => !v)}
            className="w-7 h-7 flex items-center justify-center hover:bg-[#E6E6E6] rounded-lg transition-colors text-[#9CA3AF] hover:text-[#111111]"
            title={expanded ? 'Collapse' : 'Expand'}
          >
            {expanded
              ? <ChevronUp className="w-3.5 h-3.5" strokeWidth={2} />
              : <ChevronDown className="w-3.5 h-3.5" strokeWidth={2} />}
          </button>
          <button className="w-7 h-7 flex items-center justify-center hover:bg-[#E6E6E6] rounded-lg transition-colors opacity-0 group-hover:opacity-100 text-[#9CA3AF] hover:text-[#111111]">
            <MoreVertical className="w-3.5 h-3.5" strokeWidth={2} />
          </button>
        </div>
      </div>

      {/* Description */}
      <div className="px-5 pb-3.5 flex items-start gap-3">
        <div className="w-9 flex-shrink-0" />
        {isProcessing ? (
          <span className="text-[12px] text-[#9CA3AF] flex items-center gap-1.5 italic">
            <Loader2 className="w-3 h-3 animate-spin" strokeWidth={2} />
            Generating description…
          </span>
        ) : editingDesc ? (
          <div className="flex-1 flex items-start gap-2">
            <textarea
              ref={textareaRef}
              value={descValue}
              onChange={e => setDescValue(e.target.value)}
              onKeyDown={e => { if (e.key === 'Escape') { setEditingDesc(false); setDescValue(file.description || ''); } }}
              placeholder="Describe this file — what it contains, material, tolerances, context…"
              rows={2}
              className="flex-1 text-[12px] text-[#111111] border border-[#E6E6E6] rounded-lg px-3 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-[#111111]/10 focus:border-[#111111] bg-white transition-all placeholder:text-[#C4C4C4] leading-relaxed"
            />
            <div className="flex flex-col gap-1 pt-0.5">
              <button
                onClick={saveDescription}
                disabled={savingDesc}
                className="w-7 h-7 flex items-center justify-center bg-[#111111] text-white rounded-lg hover:bg-[#2A2A2A] disabled:opacity-50 transition-colors"
              >
                {savingDesc ? <Loader2 className="w-3 h-3 animate-spin" /> : <Check className="w-3 h-3" strokeWidth={2.5} />}
              </button>
              <button
                onClick={() => { setEditingDesc(false); setDescValue(file.description || ''); }}
                className="w-7 h-7 flex items-center justify-center hover:bg-[#E6E6E6] rounded-lg transition-colors"
              >
                <X className="w-3 h-3 text-[#6B7280]" strokeWidth={2} />
              </button>
            </div>
          </div>
        ) : (
          <button
            onClick={() => { setExpanded(false); setEditingDesc(true); }}
            className="flex-1 text-left group/desc"
          >
            {descValue ? (
              <span className="text-[12px] text-[#6B7280] line-clamp-2 group-hover/desc:text-[#374151] transition-colors leading-relaxed">
                {descValue}
              </span>
            ) : (
              <span className="text-[12px] text-[#C4C4C4] italic flex items-center gap-1.5 group-hover/desc:text-[#9CA3AF] transition-colors">
                <Pencil className="w-3 h-3" strokeWidth={1.5} />
                Add a description…
              </span>
            )}
          </button>
        )}
      </div>

      {/* Extraction panel */}
      {expanded && file.status === 'processed' && (
        <ExtractionResultPanel fileId={file.id} apiFetch={apiFetch} />
      )}
    </div>
  );
}

// ─── Drag overlay ─────────────────────────────────────────────────────────────

function DragOverlay() {
  return (
    <div className="absolute inset-0 z-50 flex items-center justify-center bg-white/90 backdrop-blur-[2px]">
      <div className="flex flex-col items-center gap-5 pointer-events-none">
        <div className="relative flex items-center justify-center">
          {/* Pulse rings */}
          <div className="absolute w-28 h-28 rounded-3xl border-2 border-[#111111]/10 animate-ping" style={{ animationDuration: '1.5s' }} />
          <div className="absolute w-24 h-24 rounded-2xl border-2 border-[#111111]/15 animate-ping" style={{ animationDuration: '1.5s', animationDelay: '0.3s' }} />
          <div className="w-20 h-20 rounded-2xl border-2 border-dashed border-[#111111] bg-white flex items-center justify-center shadow-lg">
            <CloudUpload className="w-9 h-9 text-[#111111]" strokeWidth={1.5} />
          </div>
        </div>
        <div className="text-center">
          <p className="text-[#111111] font-semibold text-[15px]">Drop to upload</p>
          <p className="text-[#9CA3AF] text-[13px] mt-1">STEP · PDF · DWG · DXF · IGES</p>
        </div>
      </div>
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [activeTab, setActiveTab] = useState<'vault' | 'library'>('vault');
  const [uploadingFiles, setUploadingFiles] = useState<UploadingFile[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dragCounterRef = useRef(0);
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
      return data?.some(f => f.status === 'processing' || f.status === 'uploaded') ? 3000 : false;
    },
  });

  // ── Upload with real progress via XHR ──────────────────────────────────────
  const uploadFile = useCallback(async (file: File) => {
    if (!id) return;
    const uid = crypto.randomUUID();
    setUploadingFiles(prev => [...prev, { id: uid, name: file.name, size: file.size, progress: 0, status: 'uploading' }]);

    const form = new FormData();
    form.append('file', file);
    form.append('project_id', id);

    // Get auth token from Clerk
    const token = await (window as { __clerk_client?: { session?: { getToken?: () => Promise<string> } } }).__clerk_client?.session?.getToken?.() ?? '';

    await new Promise<void>((resolve) => {
      const xhr = new XMLHttpRequest();
      const apiUrl = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';
      xhr.open('POST', `${apiUrl}/api/files/upload/`);
      if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);

      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
          const pct = Math.round((e.loaded / e.total) * 95);
          setUploadingFiles(prev => prev.map(f => f.id === uid ? { ...f, progress: pct } : f));
        }
      };

      xhr.onload = async () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          setUploadingFiles(prev => prev.map(f => f.id === uid ? { ...f, progress: 100, status: 'done' } : f));
          await queryClient.invalidateQueries({ queryKey: ['project-files', id] });
          await queryClient.invalidateQueries({ queryKey: ['project', id] });
          setTimeout(() => {
            setUploadingFiles(prev => prev.filter(f => f.id !== uid));
          }, 2500);
        } else {
          let msg = `Upload failed (${xhr.status})`;
          try { msg = JSON.parse(xhr.responseText)?.error ?? msg; } catch (_e) { void _e; }
          setUploadingFiles(prev => prev.map(f => f.id === uid ? { ...f, status: 'error', error: msg } : f));
          setTimeout(() => setUploadingFiles(prev => prev.filter(f => f.id !== uid)), 5000);
        }
        resolve();
      };

      xhr.onerror = () => {
        setUploadingFiles(prev => prev.map(f => f.id === uid ? { ...f, status: 'error', error: 'Network error' } : f));
        setTimeout(() => setUploadingFiles(prev => prev.filter(f => f.id !== uid)), 5000);
        resolve();
      };

      xhr.send(form);
    });
  }, [id, queryClient]);

  const handleFiles = useCallback((fileList: FileList | null) => {
    if (!fileList) return;
    const allowed = new Set(['step', 'stp', 'pdf', 'dwg', 'dxf', 'iges', 'igs']);
    Array.from(fileList).forEach(file => {
      const ext = file.name.split('.').pop()?.toLowerCase() ?? '';
      if (allowed.has(ext)) uploadFile(file);
    });
  }, [uploadFile]);

  // ── Drag and drop ──────────────────────────────────────────────────────────
  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    dragCounterRef.current++;
    if (e.dataTransfer.items.length > 0) setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    dragCounterRef.current--;
    if (dragCounterRef.current === 0) setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    dragCounterRef.current = 0;
    setIsDragging(false);
    handleFiles(e.dataTransfer.files);
  }, [handleFiles]);

  if (projectError) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-[#6B7280]">Project not found or access denied.</p>
      </div>
    );
  }

  const processingCount = files?.filter(f => f.status === 'processing' || f.status === 'uploaded').length ?? 0;

  return (
    <div
      className="flex-1 flex flex-col h-full overflow-hidden relative"
      onDragEnter={handleDragEnter}
      onDragOver={e => e.preventDefault()}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {isDragging && <DragOverlay />}

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".step,.stp,.pdf,.dwg,.dxf,.iges,.igs"
        multiple
        className="hidden"
        onChange={e => { handleFiles(e.target.files); e.target.value = ''; }}
      />

      {/* Header */}
      <div className="border-b border-[#E6E6E6] bg-white px-8 py-5 flex-shrink-0">
        <div className="flex items-center gap-3 mb-4">
          <Link
            to="/vault"
            className="w-8 h-8 flex items-center justify-center hover:bg-[#F4F4F4] rounded-lg transition-colors"
          >
            <ArrowLeft className="w-[18px] h-[18px] text-[#6B7280]" strokeWidth={1.5} />
          </Link>
          <div className="flex-1 min-w-0">
            {projectLoading ? (
              <div className="animate-pulse">
                <div className="h-5 bg-[#F4F4F4] rounded w-48 mb-1.5" />
                <div className="h-3.5 bg-[#F4F4F4] rounded w-32" />
              </div>
            ) : project ? (
              <>
                <h1 className="text-[#111111] mb-0.5 truncate">{project.name}</h1>
                <p className="text-[#9CA3AF] text-[13px]">
                  {project.file_count} {project.file_count === 1 ? 'file' : 'files'}
                  {processingCount > 0 && (
                    <span className="ml-2 inline-flex items-center gap-1 text-amber-500">
                      <Loader2 className="w-3 h-3 animate-spin" strokeWidth={2} />
                      {processingCount} processing
                    </span>
                  )}
                  · Created {formatDate(project.created_at)}
                </p>
              </>
            ) : null}
          </div>
          <div className="flex items-center gap-2">
            <button className="px-3.5 py-2 bg-white border border-[#E6E6E6] rounded-lg hover:bg-[#FAFAFA] transition-colors text-[13px] text-[#6B7280] hover:text-[#111111] flex items-center gap-2">
              <Download className="w-3.5 h-3.5" strokeWidth={1.5} />
              Export
            </button>
            <button
              onClick={() => fileInputRef.current?.click()}
              className="px-3.5 py-2 bg-[#111111] text-white rounded-lg hover:bg-[#1A1A1A] active:bg-[#2A2A2A] transition-colors text-[13px] font-medium flex items-center gap-2 shadow-sm"
            >
              <Upload className="w-3.5 h-3.5" strokeWidth={1.5} />
              Upload files
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex items-center gap-1 -mb-5">
          {(['vault', 'library'] as const).map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`flex items-center gap-2 px-1 pb-4 text-[13px] border-b-2 transition-colors capitalize ${
                activeTab === tab
                  ? 'border-[#111111] text-[#111111] font-medium'
                  : 'border-transparent text-[#9CA3AF] hover:text-[#6B7280]'
              }`}
            >
              {tab === 'vault' ? <Folder className="w-3.5 h-3.5" strokeWidth={1.5} /> : <FileText className="w-3.5 h-3.5" strokeWidth={1.5} />}
              {tab}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto bg-[#F7F7F7]">
        <div className="max-w-5xl mx-auto px-8 py-6">
          {activeTab === 'vault' ? (
            <div className="bg-white border border-[#E6E6E6] rounded-xl overflow-hidden shadow-sm">

              {/* Upload progress section */}
              {uploadingFiles.length > 0 && (
                <div className="border-b border-[#E6E6E6]">
                  <div className="px-6 py-2.5 bg-[#F7F7F7] border-b border-[#F0F0F0]">
                    <p className="text-[11px] font-semibold text-[#6B7280] uppercase tracking-widest">
                      Uploading {uploadingFiles.length} {uploadingFiles.length === 1 ? 'file' : 'files'}
                    </p>
                  </div>
                  {uploadingFiles.map(f => <UploadProgressItem key={f.id} file={f} />)}
                </div>
              )}

              {/* Table header */}
              <div className="grid grid-cols-[1fr_auto_auto] gap-4 px-6 py-2.5 border-b border-[#F0F0F0] bg-[#FAFAFA]">
                <span className="text-[11px] font-semibold text-[#9CA3AF] uppercase tracking-widest">File</span>
                <span className="text-[11px] font-semibold text-[#9CA3AF] uppercase tracking-widest">Status</span>
                <span className="text-[11px] font-semibold text-[#9CA3AF] uppercase tracking-widest w-16" />
              </div>

              {/* Rows */}
              {filesLoading && Array.from({ length: 3 }).map((_, i) => <SkeletonRow key={i} />)}

              {filesError && (
                <div className="px-6 py-10 text-center">
                  <p className="text-[#6B7280] text-sm">Failed to load files.</p>
                </div>
              )}

              {files && files.length === 0 && uploadingFiles.length === 0 && (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <div
                    onClick={() => fileInputRef.current?.click()}
                    className="w-16 h-16 border-2 border-dashed border-[#E6E6E6] rounded-2xl flex items-center justify-center mb-4 cursor-pointer hover:border-[#111111] hover:bg-[#FAFAFA] transition-colors group"
                  >
                    <CloudUpload className="w-7 h-7 text-[#D1D5DB] group-hover:text-[#6B7280] transition-colors" strokeWidth={1.5} />
                  </div>
                  <p className="text-[#111111] text-[13px] font-medium mb-1">No files yet</p>
                  <p className="text-[#9CA3AF] text-[12px]">Drag files here or click Upload files above</p>
                  <p className="text-[#C4C4C4] text-[11px] mt-1">STEP · STP · PDF · DWG · DXF · IGES</p>
                </div>
              )}

              {files && files.map(file => (
                <FileRow key={file.id} file={file} apiFetch={apiFetch} />
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <div className="w-12 h-12 bg-[#F4F4F4] rounded-xl flex items-center justify-center mb-4">
                <FileText className="w-6 h-6 text-[#D1D5DB]" strokeWidth={1.5} />
              </div>
              <p className="text-[#111111] text-[13px] font-medium mb-1">Extraction profiles</p>
              <p className="text-[#9CA3AF] text-[12px]">Structured profiles appear here once files are processed.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
