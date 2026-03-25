import { useState } from 'react';
import { ArrowLeft, Upload, FileText, Download, Folder, MoreVertical, File, CheckCircle2, Loader2, AlertCircle } from 'lucide-react';
import { Link, useParams } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { useApiClient } from '../../api/client';
import type { Project, UploadedFile } from '../../api/types';

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
      Processing
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

export function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [activeTab, setActiveTab] = useState<'vault' | 'library'>('vault');
  const apiFetch = useApiClient();

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
  });

  if (projectError) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-[#6B7280]">Project not found or access denied.</p>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">
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
            <button className="px-4 py-2 bg-white border border-[#E6E6E6] rounded-lg hover:bg-[#FAFAFA] transition-colors text-sm text-[#111111]">
              <Download className="w-4 h-4 inline mr-2" strokeWidth={1.5} />
              Export
            </button>
            <button className="px-4 py-2 bg-[#111111] text-white rounded-lg hover:bg-[#2A2A2A] transition-colors text-sm">
              <Upload className="w-4 h-4 inline mr-2" strokeWidth={1.5} />
              Upload files
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
              {/* Table Header */}
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
                  <p className="text-[#6B7280] text-[12px]">Use the Upload files button to add engineering files.</p>
                </div>
              )}

              {files && files.map((file) => (
                <div
                  key={file.id}
                  className="grid grid-cols-12 gap-4 px-6 py-4 border-b border-[#E6E6E6] last:border-b-0 hover:bg-[#FAFAFA] transition-colors group cursor-pointer"
                >
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
                  <div className="col-span-1 flex items-center justify-end">
                    <button className="w-8 h-8 flex items-center justify-center hover:bg-[#E6E6E6] rounded-lg transition-colors opacity-0 group-hover:opacity-100">
                      <MoreVertical className="w-4 h-4 text-[#6B7280]" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            /* Library — extraction profiles not yet implemented */
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
