import { useState, useRef, useEffect, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import { ArrowLeft, Upload, FileText, Download, Folder, MoreVertical, File, CheckCircle2, Loader2, AlertCircle, ChevronDown, ChevronUp, Pencil, Check, X, Trash, Link as LinkIcon, ListChecks, BookOpen, BarChart3, DollarSign, Shield, AlertTriangle, ArrowRight } from 'lucide-react';
import { Link, useNavigate, useParams } from 'react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useApiClient } from '../../api/client';
import type { Project, UploadedFile, ExtractionResult, BomResearchRun } from '../../api/types';
import { toast } from 'sonner';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { BomQuestionsPanel } from './BomQuestionsPanel';
import { BomLivePanel } from './BomLivePanel';
import { BomResultsPanel } from './BomResultsPanel';
import { BomEmailPanel } from './BomEmailPanel';
import { EngineeringProfileCard } from './EngineeringProfileCard';
import { computeAnalyticsSummary, formatCurrency } from './BomAnalyticsDeck';

function InlineStat({ icon: Icon, label, value, tone = 'neutral' }: {
  icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  label: string; value: React.ReactNode;
  tone?: 'neutral' | 'positive' | 'caution' | 'risk';
}) {
  const accent = tone === 'positive' ? '#7FB069' : tone === 'caution' ? '#D4A047' : tone === 'risk' ? '#E88872' : '#FAF7F2';
  return (
    <div className="flex items-center gap-1.5">
      <Icon className="w-3.5 h-3.5" style={{ color: accent }} strokeWidth={1.75} />
      <div>
        <p className="text-[9px] font-display uppercase tracking-[0.18em]" style={{ color: 'rgba(250, 247, 242, 0.55)' }}>{label}</p>
        <p className="font-display text-[14px] leading-none tabular-nums" style={{ color: accent }}>{value}</p>
      </div>
    </div>
  );
}
import type { BomEmailComposerTrigger } from './BomEmailPanel';
import type { BomQuestion, LibraryDocType } from '../../api/types';

type FileLike = UploadedFile & { optimistic?: boolean };

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function FileStatusBadge({ status, optimistic }: { status: UploadedFile['status']; optimistic?: boolean }) {
  if (optimistic) {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-[#F2EDE3] text-[#8B7F73]">
        <Loader2 className="w-3 h-3 animate-spin" strokeWidth={2} />
        Uploading…
      </span>
    );
  }
  if (status === 'processed') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-[#F2EDE3] text-[#8B7F73]">
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
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-[#F2EDE3] text-[#8B7F73]">
      <Loader2 className="w-3 h-3 animate-spin" strokeWidth={2} />
      {status === 'processing' ? 'Processing' : optimistic ? 'Uploading…' : 'Uploaded'}
    </span>
  );
}

function SkeletonRow() {
  return (
    <div className="grid grid-cols-12 gap-4 px-6 py-4 border-b border-[#E8E0D3] animate-pulse">
      <div className="col-span-5 flex items-center gap-3">
        <div className="w-9 h-9 bg-[#F2EDE3] rounded-lg flex-shrink-0" />
        <div className="flex-1">
          <div className="h-3 bg-[#F2EDE3] rounded w-2/3 mb-1.5" />
          <div className="h-2.5 bg-[#F2EDE3] rounded w-1/3" />
        </div>
      </div>
      <div className="col-span-2 flex items-center"><div className="h-5 bg-[#F2EDE3] rounded w-12" /></div>
      <div className="col-span-2 flex items-center"><div className="h-3 bg-[#F2EDE3] rounded w-16" /></div>
      <div className="col-span-2 flex items-center"><div className="h-5 bg-[#F2EDE3] rounded w-20" /></div>
      <div className="col-span-1" />
    </div>
  );
}

function ExtractionResultPanel({ fileId, fileName, apiFetch, description }: { fileId: number; fileName: string; apiFetch: ReturnType<typeof useApiClient>; description?: string }) {
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
      <div className="px-6 pb-4 pt-2 bg-[#FFFCF7] border-t border-[#E8E0D3]">
        <div className="animate-pulse space-y-2">
          <div className="h-3 bg-[#E8E0D3] rounded w-1/3" />
          <div className="h-3 bg-[#E8E0D3] rounded w-1/2" />
        </div>
      </div>
    );
  }

  if (!data) return null;

  const unit = data.units?.length_unit ?? data.units_hint;
  const bb = data.spatial?.bounding_box_estimate;

  // Parse ## sections from AI description for rich section rendering
  const hasHeaders = (description ?? '').includes('## ');
  let overviewText = '';
  let bodyMd = description ?? '';
  if (hasHeaders && description) {
    const lines = description.split('\n');
    let inOverview = false;
    let pastOverview = false;
    const bodyLines: string[] = [];
    for (const line of lines) {
      const isH2 = line.startsWith('## ');
      if (isH2 && line.toLowerCase().includes('overview')) { inOverview = true; continue; }
      if (isH2 && inOverview) { inOverview = false; pastOverview = true; bodyLines.push(line); continue; }
      if (isH2 && pastOverview) { bodyLines.push(line); continue; }
      if (inOverview && line.trim()) overviewText += (overviewText ? ' ' : '') + line.trim();
      else if (pastOverview) bodyLines.push(line);
    }
    bodyMd = bodyLines.join('\n').trim();
  }

  async function handleProfileDownload() {
    const res = await apiFetch(`/api/files/${fileId}/profile/`);
    if (!res.ok) return;
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${fileName.replace(/\.[^.]+$/, '')}_profile.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="border-t border-[#E8E0D3] bg-[#FFFCF7]">

      {/* Engineering Profile card */}
      {data.profile && Object.keys(data.profile).length > 0 && (
        <div className="mx-6 mt-5 mb-2">
          <EngineeringProfileCard
            profile={data.profile}
            fileName={fileName}
            onDownload={handleProfileDownload}
          />
        </div>
      )}

      {/* AI Description card */}
      {description && (
        <div className="mx-6 mt-5 mb-2 rounded-2xl overflow-hidden" style={{
          boxShadow: '0 0 0 1px rgba(139,92,246,0.14), 0 8px 32px rgba(109,40,217,0.08), 0 1px 3px rgba(0,0,0,0.04)'
        }}>

          {/* Aurora gradient header */}
          <div className="relative px-5 pt-5 pb-5 overflow-hidden" style={{
            background: 'linear-gradient(135deg, #0C0C1E 0%, #130F2B 45%, #0A1628 100%)'
          }}>
            {/* Violet glow blob */}
            <div className="absolute pointer-events-none" style={{
              top: '-24px', left: '8%', width: '180px', height: '180px',
              background: 'radial-gradient(circle, rgba(124,58,237,0.35), transparent 70%)',
              filter: 'blur(28px)'
            }} />
            {/* Blue glow blob */}
            <div className="absolute pointer-events-none" style={{
              top: '-12px', right: '15%', width: '120px', height: '120px',
              background: 'radial-gradient(circle, rgba(37,99,235,0.25), transparent 70%)',
              filter: 'blur(20px)'
            }} />
            {/* Dot grid texture */}
            <div className="absolute inset-0 pointer-events-none" style={{
              backgroundImage: 'radial-gradient(circle, rgba(255,255,255,0.055) 1px, transparent 1px)',
              backgroundSize: '22px 22px'
            }} />
            <div className="relative">
              {/* Badge row */}
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="relative">
                    <div className="absolute inset-0 rounded-xl opacity-50" style={{
                      background: 'linear-gradient(135deg, #8B5CF6, #6366F1)',
                      filter: 'blur(8px)'
                    }} />
                    <div className="relative w-8 h-8 rounded-xl flex items-center justify-center" style={{
                      background: 'linear-gradient(135deg, #8B5CF6 0%, #6366F1 100%)'
                    }}>
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z"/>
                      </svg>
                    </div>
                  </div>
                  <div>
                    <p className="text-[11px] font-bold text-white tracking-widest uppercase leading-none mb-1">AI Analysis</p>
                    <p className="text-[10px] font-mono leading-none" style={{color: 'rgba(255,255,255,0.32)'}}>claude-haiku-4-5</p>
                  </div>
                </div>
                <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full" style={{
                  background: 'rgba(255,255,255,0.04)',
                  border: '1px solid rgba(255,255,255,0.09)'
                }}>
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" style={{boxShadow: '0 0 5px rgba(52,211,153,0.7)'}} />
                  <span className="text-[10px] font-medium" style={{color: 'rgba(255,255,255,0.38)'}}>Generated</span>
                </div>
              </div>
              {/* Overview or full text in header */}
              {(overviewText || !hasHeaders) && (
                <div style={{borderLeft: '2px solid rgba(139,92,246,0.5)', paddingLeft: '12px'}}>
                  <p className="text-[13px] leading-relaxed m-0" style={{color: 'rgba(255,255,255,0.7)'}}>
                    {overviewText || description}
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Body sections */}
          <div className="bg-white">
            {hasHeaders && bodyMd ? (
              <ReactMarkdown
                components={{
                  h2: ({ children }) => {
                    const name = String(children || '').toLowerCase();
                    const cfg =
                      name.includes('key') || name.includes('prop')
                        ? { color: '#2563EB', bg: '#EFF6FF', text: 'Key Properties' }
                        : name.includes('geom')
                        ? { color: '#059669', bg: '#ECFDF5', text: 'Geometry & Structure' }
                        : name.includes('prov')
                        ? { color: '#B45309', bg: '#FEF3C7', text: 'Provenance' }
                        : { color: '#7C3AED', bg: '#F5F3FF', text: String(children) };
                    return (
                      <div className="flex items-center gap-2 px-5 pt-5 pb-2 border-t border-[#F3F4F6]">
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-md tracking-wide whitespace-nowrap flex-shrink-0"
                              style={{ color: cfg.color, background: cfg.bg }}>
                          {cfg.text}
                        </span>
                        <div className="flex-1 h-px bg-[#EEE6D8]" />
                      </div>
                    );
                  },
                  p: ({ children }) => (
                    <p className="px-5 py-1.5 text-[13px] text-[#4A4038] leading-relaxed m-0">{children}</p>
                  ),
                  ul: ({ children }) => (
                    <ul className="px-5 pb-3 pt-1 m-0 list-none space-y-1.5">{children}</ul>
                  ),
                  li: ({ children }) => (
                    <li className="flex items-start gap-2 text-[12px] text-[#4A4038]">
                      <span className="mt-[5px] w-1.5 h-1.5 rounded-full flex-shrink-0" style={{background: '#DDD6FE'}} />
                      <span className="leading-relaxed">{children}</span>
                    </li>
                  ),
                  strong: ({ children }) => (
                    <strong className="font-semibold text-[#111]">{children}</strong>
                  ),
                }}
              >{bodyMd}</ReactMarkdown>
            ) : null}
            <div className="h-5" />
          </div>
        </div>
      )}

      {/* Key Properties grid */}
      {(data.schema || data.authoring_system || data.confidence != null || unit || data.products?.product_count != null || data.geometry?.faces != null) && (
        <div className="px-6 pt-5 pb-4 border-b border-[#EEE6D8]">
          <p className="text-[10px] font-semibold text-[#A89D91] uppercase tracking-widest mb-3">Key Properties</p>
          <div className="grid grid-cols-3 gap-2">
            {data.schema && (
              <div className="bg-white border border-[#E8E0D3] rounded-xl px-3.5 py-3 hover:border-[#D5D5D5] transition-colors">
                <p className="text-[10px] text-[#A89D91] uppercase tracking-wider mb-1">Format</p>
                <p className="text-[12px] font-semibold text-[#2B2824] leading-snug">{data.schema}</p>
              </div>
            )}
            {data.authoring_system && (
              <div className="bg-white border border-[#E8E0D3] rounded-xl px-3.5 py-3 hover:border-[#D5D5D5] transition-colors">
                <p className="text-[10px] text-[#A89D91] uppercase tracking-wider mb-1">Authoring Tool</p>
                <p className="text-[12px] font-semibold text-[#2B2824] leading-snug">{data.authoring_system}</p>
              </div>
            )}
            {data.confidence != null && (
              <div className="bg-white border border-[#E8E0D3] rounded-xl px-3.5 py-3 hover:border-[#D5D5D5] transition-colors">
                <p className="text-[10px] text-[#A89D91] uppercase tracking-wider mb-1">Confidence</p>
                <div className="flex items-baseline gap-1.5">
                  <p className="text-[12px] font-semibold text-[#2B2824]">{Math.round(data.confidence * 100)}%</p>
                  <div className="flex-1 h-1 bg-[#EEE6D8] rounded-full overflow-hidden">
                    <div className="h-full bg-amber-400 rounded-full" style={{ width: `${Math.round(data.confidence * 100)}%` }} />
                  </div>
                </div>
              </div>
            )}
            {unit && (
              <div className="bg-white border border-[#E8E0D3] rounded-xl px-3.5 py-3 hover:border-[#D5D5D5] transition-colors">
                <p className="text-[10px] text-[#A89D91] uppercase tracking-wider mb-1">Units</p>
                <p className="text-[12px] font-semibold text-[#2B2824] leading-snug">{unit}</p>
              </div>
            )}
            {data.products?.product_count != null && (
              <div className="bg-white border border-[#E8E0D3] rounded-xl px-3.5 py-3 hover:border-[#D5D5D5] transition-colors">
                <p className="text-[10px] text-[#A89D91] uppercase tracking-wider mb-1">Products</p>
                <p className="text-[12px] font-semibold text-[#2B2824] leading-snug">{data.products.product_count}</p>
              </div>
            )}
            {data.geometry?.faces != null && (
              <div className="bg-white border border-[#E8E0D3] rounded-xl px-3.5 py-3 hover:border-[#D5D5D5] transition-colors">
                <p className="text-[10px] text-[#A89D91] uppercase tracking-wider mb-1">Faces</p>
                <p className="text-[12px] font-semibold text-[#2B2824] leading-snug tabular-nums">{data.geometry.faces.toLocaleString()}</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Bounding box */}
      {bb && (
        <div className="px-6 pt-4 pb-3 border-b border-[#EEE6D8]">
          <p className="text-[10px] font-semibold text-[#A89D91] uppercase tracking-widest mb-2.5">Bounding Box</p>
          <div className="flex items-stretch gap-2">
            {([['X', bb.x], ['Y', bb.y], ['Z', bb.z]] as [string, string | number][]).map(([axis, val]) => (
              <div key={axis} className="flex-1 bg-white border border-[#E8E0D3] rounded-xl px-3 py-2.5 text-center">
                <p className="text-[10px] text-[#A89D91] font-medium mb-0.5">{axis}</p>
                <p className="text-[12px] font-semibold text-[#2B2824] tabular-nums">{val}</p>
              </div>
            ))}
            {unit && (
              <div className="flex items-end pb-2.5 pl-1">
                <span className="text-[11px] text-[#A89D91]">{unit}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Detail grid: provenance + geometry */}
      <div className="px-6 py-4 grid grid-cols-2 gap-4 text-[12px]">
        {/* Left col: provenance + products */}
        <div className="space-y-3">
          {(data.source_file || data.created_at || data.authors?.length) && (
            <div className="bg-white border border-[#E8E0D3] rounded-xl px-4 py-3">
              <p className="text-[10px] font-semibold text-[#A89D91] uppercase tracking-widest mb-2">Provenance</p>
              <dl className="space-y-1.5">
                {data.source_file && (
                  <div className="flex gap-2">
                    <dt className="text-[#A89D91] min-w-[72px]">Source</dt>
                    <dd className="text-[#4A4038] font-medium truncate">{data.source_file}</dd>
                  </div>
                )}
                {data.created_at && (
                  <div className="flex gap-2">
                    <dt className="text-[#A89D91] min-w-[72px]">Created</dt>
                    <dd className="text-[#4A4038]">{new Date(data.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</dd>
                  </div>
                )}
                {data.authors?.length && (
                  <div className="flex gap-2">
                    <dt className="text-[#A89D91] min-w-[72px]">Tools</dt>
                    <dd className="text-[#4A4038]">{data.authors.join(', ')}</dd>
                  </div>
                )}
              </dl>
            </div>
          )}
          {data.products?.product_names?.length && (
            <div className="bg-white border border-[#E8E0D3] rounded-xl px-4 py-3">
              <p className="text-[10px] font-semibold text-[#A89D91] uppercase tracking-widest mb-2">Products</p>
              <ul className="space-y-1">
                {data.products.product_names.slice(0, 6).map((name, i) => (
                  <li key={i} className="flex items-center gap-2 text-[#4A4038]">
                    <span className="w-1 h-1 rounded-full bg-[#D1D5DB] flex-shrink-0" />
                    {name}
                  </li>
                ))}
                {data.products.product_names.length > 6 && (
                  <li className="text-[#A89D91] pl-3">+{data.products.product_names.length - 6} more</li>
                )}
              </ul>
              {data.products.assembly_relationships != null && (
                <p className="text-[#8B7F73] mt-2 pt-2 border-t border-[#EEE6D8]">
                  {data.products.assembly_relationships} assembly {data.products.assembly_relationships === 1 ? 'relationship' : 'relationships'}
                </p>
              )}
            </div>
          )}
        </div>

        {/* Right col: geometry */}
        {data.geometry && Object.keys(data.geometry).length > 0 && (
          <div className="bg-white border border-[#E8E0D3] rounded-xl px-4 py-3">
            <p className="text-[10px] font-semibold text-[#A89D91] uppercase tracking-widest mb-2">Geometry</p>
            <dl className="space-y-1.5">
              {([
                ['solid_bodies', 'Solid bodies'],
                ['faces', 'Faces'],
                ['edges', 'Edges'],
                ['vertices', 'Vertices'],
                ['circles', 'Circles'],
                ['coordinate_axes', 'Coord. axes'],
              ] as [string, string][]).map(([key, label]) =>
                data.geometry![key] != null ? (
                  <div key={key} className="flex justify-between gap-2">
                    <dt className="text-[#A89D91]">{label}</dt>
                    <dd className="text-[#4A4038] font-semibold tabular-nums">{(data.geometry![key] as number).toLocaleString()}</dd>
                  </div>
                ) : null
              )}
            </dl>
            {data.geometry.surface_type_breakdown && (
              <div className="mt-3 pt-2 border-t border-[#EEE6D8]">
                <p className="text-[10px] text-[#A89D91] uppercase tracking-wider mb-1.5">Surface types</p>
                <div className="flex flex-wrap gap-1">
                  {Object.entries(data.geometry.surface_type_breakdown).map(([type, count]) => (
                    <span key={type} className="px-2 py-0.5 bg-[#FAF7F2] border border-[#E8E0D3] rounded-md text-[10px] text-[#8B7F73]">
                      {type} <span className="font-medium text-[#4A4038]">{count}</span>
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Warnings */}
      {data.warnings?.length > 0 && (
        <div className="px-6 pb-4">
          {data.warnings.map((w, i) => (
            <p key={i} className="text-[11px] text-[#92400E] bg-amber-50 border border-amber-100 rounded px-2.5 py-1.5 mb-1">{w}</p>
          ))}
        </div>
      )}
    </div>
  );
}

function FileRow({ file, apiFetch, projectId }: { file: FileLike; apiFetch: ReturnType<typeof useApiClient>; projectId: string }) {
  const [expanded, setExpanded] = useState(false);
  const [editingDesc, setEditingDesc] = useState(false);
  const [descValue, setDescValue] = useState(file.description || '');
  const [savingDesc, setSavingDesc] = useState(false);
  const [promoteDocType, setPromoteDocType] = useState<LibraryDocType | ''>('');
  const [showPromoteModal, setShowPromoteModal] = useState(false);
  const [promoting, setPromoting] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const handleExtract = async () => {
    setExtracting(true);
    try {
      const res = await apiFetch(`/api/files/${file.id}/extract/`, { method: 'POST' });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.error ?? `Failed (${res.status})`);
      }
      await queryClient.invalidateQueries({ queryKey: ['project-files', projectId] });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to start extraction');
    } finally {
      setExtracting(false);
    }
  };

  async function handlePromote() {
    if (!promoteDocType) return;
    setPromoting(true);
    try {
      const res = await apiFetch('/api/library/documents/promote/', {
        method: 'POST',
        body: JSON.stringify({ file_id: file.id, doc_type: promoteDocType }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail ?? 'Failed to add to Library');
      }
      toast.success(`"${file.original_name}" added to Library.`);
      queryClient.invalidateQueries({ queryKey: ['library'] });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to add to Library');
    } finally {
      setPromoting(false);
      setShowPromoteModal(false);
      setPromoteDocType('');
    }
  }

  useEffect(() => {
    if (!editingDesc) setDescValue(file.description || '');
  }, [file.description, editingDesc]);
  const handleDownload = async () => {
    try {
      const res = await apiFetch(`/api/files/${file.id}/download/`);
      if (!res.ok) throw new Error(`Download failed (${res.status})`);
      const data = await res.json();
      if (data?.url) {
        window.open(data.url, '_blank', 'noopener');
      } else {
        throw new Error('No download URL returned');
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Download failed');
    }
  };

  const handleDelete = async () => {
    const confirmed = window.confirm(`Delete ${file.original_name}?`);
    if (!confirmed) return;
    try {
      const res = await apiFetch(`/api/files/${file.id}/`, { method: 'DELETE' });
      if (!res.ok && res.status !== 204) throw new Error(`Delete failed (${res.status})`);
      toast.success('File deleted');
      await queryClient.invalidateQueries({ queryKey: ['project-files', projectId] });
      await queryClient.invalidateQueries({ queryKey: ['project', projectId] });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Delete failed');
    }
  };

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
      <div className="border-b border-[#E8E0D3] last:border-b-0 hover:bg-[#FFFCF7] transition-colors group">
        <div className="grid grid-cols-12 gap-4 px-6 py-4">
          <div className="col-span-5 flex items-center gap-3">
            <div className="w-9 h-9 bg-[#F2EDE3] rounded-lg flex items-center justify-center flex-shrink-0">
              <File className="w-[18px] h-[18px] text-[#8B7F73]" strokeWidth={1.5} />
            </div>
            <div className="min-w-0">
              <p className="text-[#2B2824] text-sm mb-0.5 truncate">{file.original_name}</p>
              <p className="text-[#8B7F73] text-[12px]">Uploaded {formatDate(file.created_at)}</p>
            </div>
          </div>
          <div className="col-span-2 flex items-center">
            <span className="px-2 py-1 bg-[#F2EDE3] text-[#8B7F73] rounded text-[11px] font-medium uppercase">
              {file.file_type || '—'}
            </span>
          </div>
          <div className="col-span-2 flex items-center">
            <span className="text-[#8B7F73] text-sm">{formatBytes(file.file_size)}</span>
          </div>
          <div className="col-span-2 flex items-center">
            {file.status === 'processed' ? (
              <button
                className="text-left"
                onClick={() => navigate(`/project/${projectId}/file/${file.id}/result`)}
              >
                <FileStatusBadge status={file.status} />
              </button>
            ) : file.status === 'uploaded' && !file.optimistic ? (
              <button
                onClick={handleExtract}
                disabled={extracting}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-semibold transition-all disabled:opacity-50 bg-[#F5F3FF] text-[#7C3AED] border border-[#DDD6FE] hover:bg-[#EDE9FE]"
              >
                {extracting
                  ? <><Loader2 className="w-3 h-3 animate-spin" strokeWidth={2} /> Starting…</>
                  : 'Run Extraction'}
              </button>
            ) : (
              <FileStatusBadge status={file.status} optimistic={file.optimistic} />
            )}
          </div>
          <div className="col-span-1 flex items-center justify-end gap-1">
            <button
              onClick={() => setExpanded((v) => !v)}
              className="w-8 h-8 flex items-center justify-center hover:bg-[#E8E0D3] rounded-lg transition-colors"
              title="Expand"
            >
              {expanded
                ? <ChevronUp className="w-4 h-4 text-[#8B7F73]" />
                : <ChevronDown className="w-4 h-4 text-[#8B7F73]" />}
            </button>
            <DropdownMenu.Root>
              <DropdownMenu.Trigger asChild>
                <button className="w-8 h-8 flex items-center justify-center hover:bg-[#E8E0D3] rounded-lg transition-colors opacity-0 group-hover:opacity-100">
                  <MoreVertical className="w-4 h-4 text-[#8B7F73]" />
                </button>
              </DropdownMenu.Trigger>
              <DropdownMenu.Content
                className="min-w-[160px] bg-white border border-[#E8E0D3] rounded-lg shadow-lg p-1 text-sm text-[#2B2824]"
                align="end"
              >
                <DropdownMenu.Item
                  className="px-3 py-2 rounded hover:bg-[#F2EDE3] flex items-center gap-2 cursor-pointer"
                  onSelect={(e) => { e.preventDefault(); handleDownload(); }}
                >
                  <LinkIcon className="w-4 h-4 text-[#8B7F73]" />
                  Download
                </DropdownMenu.Item>
                <DropdownMenu.Item
                  className="px-3 py-2 rounded hover:bg-[#F2EDE3] flex items-center gap-2 cursor-pointer"
                  onSelect={(e) => { e.preventDefault(); setShowPromoteModal(true); }}
                >
                  <BookOpen className="w-4 h-4 text-[#8B7F73]" />
                  Add to Library
                </DropdownMenu.Item>
                <DropdownMenu.Item
                  className="px-3 py-2 rounded hover:bg-[#FEF2F2] text-[#DC2626] flex items-center gap-2 cursor-pointer"
                  onSelect={(e) => { e.preventDefault(); handleDelete(); }}
                >
                  <Trash className="w-4 h-4" />
                  Delete
                </DropdownMenu.Item>
              </DropdownMenu.Content>
            </DropdownMenu.Root>
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
                className="flex-1 text-[12px] text-[#2B2824] border border-[#E8E0D3] rounded-lg px-3 py-2 resize-none focus:outline-none focus:ring-1 focus:ring-[#2B2824] bg-white min-h-[72px]"
              />
              <div className="flex flex-col gap-1 pt-1">
                <button
                  onClick={saveDescription}
                  disabled={savingDesc}
                  className="w-7 h-7 flex items-center justify-center bg-[#2B2824] text-white rounded-lg hover:bg-[#3D3530] disabled:opacity-50 transition-colors"
                >
                  {savingDesc ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
                </button>
                <button
                  onClick={cancelEdit}
                  className="w-7 h-7 flex items-center justify-center hover:bg-[#E8E0D3] rounded-lg transition-colors"
                >
                  <X className="w-3.5 h-3.5 text-[#8B7F73]" />
                </button>
              </div>
            </div>
          ) : (file.status === 'processing' || file.optimistic) || (file.status === 'uploaded' && !file.description) ? (
            <span className="text-[12px] text-[#A89D91] italic flex items-center gap-1.5">
              <Loader2 className="w-3 h-3 animate-spin" strokeWidth={1.5} />
              Generating description…
            </span>
          ) : (
            <button
              onClick={() => setEditingDesc(true)}
              className="flex-1 text-left group/desc"
            >
              {descValue ? (
                <div className="text-[12px] text-[#8B7F73] group-hover/desc:text-[#4A4038] transition-colors prose prose-sm max-w-none [&>*:first-child]:mt-0 [&>*:last-child]:mb-0 [&_strong]:font-semibold [&_strong]:text-[#4A4038] [&_ul]:pl-4 [&_li]:text-[12px] [&_h2]:text-[12px] [&_h3]:text-[12px] [&_h2]:font-semibold [&_h3]:font-medium [&_h2]:text-[#4A4038] [&_h3]:text-[#8B7F73]">
                  <ReactMarkdown>{descValue}</ReactMarkdown>
                </div>
              ) : (
                <span className="text-[12px] text-[#D1D5DB] italic group-hover/desc:text-[#A89D91] transition-colors flex items-center gap-1.5">
                  <Pencil className="w-3 h-3" strokeWidth={1.5} />
                  Add description…
                </span>
              )}
            </button>
          )}
        </div>
      </div>

      {expanded && file.status === 'processed' && (
        <ExtractionResultPanel fileId={file.id} fileName={file.original_name} apiFetch={apiFetch} description={file.description} />
      )}

      {/* Add to Library promote modal */}
      {showPromoteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-sm mx-4 p-6">
            <h3 className="text-base font-semibold text-[#2B2824] mb-1">Add to Library</h3>
            <p className="text-sm text-[#8B7F73] mb-4">Select a document type for <span className="font-medium text-[#2B2824]">{file.original_name}</span></p>
            <select
              value={promoteDocType}
              onChange={(e) => setPromoteDocType(e.target.value as LibraryDocType)}
              className="w-full px-3 py-2 border border-[#E8E0D3] rounded-lg text-sm focus:outline-none focus:border-[#2B2824] bg-white mb-4"
            >
              <option value="">Select type…</option>
              {LIBRARY_DOC_TYPES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
            <div className="flex justify-end gap-2">
              <button onClick={() => { setShowPromoteModal(false); setPromoteDocType(''); }} className="px-4 py-2 text-sm border border-[#E8E0D3] rounded-lg hover:bg-[#F2EDE3]">Cancel</button>
              <button onClick={handlePromote} disabled={!promoteDocType || promoting}
                className="px-4 py-2 text-sm bg-[#2B2824] text-white rounded-lg hover:bg-[#333333] disabled:opacity-50 flex items-center gap-1.5">
                {promoting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                Add to Library
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function ExtractionRunCard({ file, apiFetch, projectId }: { file: FileLike; apiFetch: ReturnType<typeof useApiClient>; projectId: string }) {
  const [expanded, setExpanded] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const queryClient = useQueryClient();

  const handleExtract = async () => {
    setExtracting(true);
    try {
      const res = await apiFetch(`/api/files/${file.id}/extract/`, { method: 'POST' });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.error ?? `Failed (${res.status})`);
      }
      await queryClient.invalidateQueries({ queryKey: ['project-files', projectId] });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to start extraction');
    } finally {
      setExtracting(false);
    }
  };

  const statusConfig: Record<string, { label: string; className: string; icon: React.ReactNode }> = {
    processed: {
      label: 'Extracted',
      className: 'bg-[#ECFDF5] text-[#065F46] border border-emerald-100',
      icon: <CheckCircle2 className="w-3 h-3" strokeWidth={2} />,
    },
    processing: {
      label: 'Processing',
      className: 'bg-[#F2EDE3] text-[#8B7F73] border border-[#E8E0D3]',
      icon: <Loader2 className="w-3 h-3 animate-spin" strokeWidth={2} />,
    },
    failed: {
      label: 'Failed',
      className: 'bg-[#FEF2F2] text-[#DC2626] border border-red-100',
      icon: <AlertCircle className="w-3 h-3" strokeWidth={2} />,
    },
  };

  const cfg = statusConfig[file.status];

  return (
    <div className="bg-white border border-[#E8E0D3] rounded-xl overflow-hidden">
      <div className="flex items-center gap-4 px-5 py-4">
        <div className="w-9 h-9 bg-[#F2EDE3] rounded-lg flex items-center justify-center flex-shrink-0">
          <File className="w-[18px] h-[18px] text-[#8B7F73]" strokeWidth={1.5} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-[#2B2824] truncate">{file.original_name}</p>
          <p className="text-[12px] text-[#A89D91]">
            {formatDate(file.created_at)} · {formatBytes(file.file_size)} ·{' '}
            <span className="uppercase font-medium">{file.file_type || '—'}</span>
          </p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {file.status === 'uploaded' ? (
            <button
              onClick={handleExtract}
              disabled={extracting}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-semibold transition-all disabled:opacity-50 bg-[#F5F3FF] text-[#7C3AED] border border-[#DDD6FE] hover:bg-[#EDE9FE]"
            >
              {extracting
                ? <><Loader2 className="w-3 h-3 animate-spin" strokeWidth={2} /> Starting…</>
                : 'Run Extraction'}
            </button>
          ) : cfg ? (
            <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium ${cfg.className}`}>
              {cfg.icon}
              {cfg.label}
            </span>
          ) : null}
          {file.status === 'processed' && (
            <button
              onClick={() => setExpanded((v) => !v)}
              className="w-8 h-8 flex items-center justify-center hover:bg-[#E8E0D3] rounded-lg transition-colors"
              title={expanded ? 'Collapse' : 'View profile'}
            >
              {expanded
                ? <ChevronUp className="w-4 h-4 text-[#8B7F73]" />
                : <ChevronDown className="w-4 h-4 text-[#8B7F73]" />}
            </button>
          )}
          {file.status === 'failed' && (
            <button
              onClick={handleExtract}
              disabled={extracting}
              className="inline-flex items-center gap-1.5 px-2 py-1 rounded-lg text-[11px] font-medium transition-all disabled:opacity-50 hover:bg-[#FEF2F2] text-[#DC2626]"
            >
              {extracting ? <Loader2 className="w-3 h-3 animate-spin" strokeWidth={2} /> : 'Retry'}
            </button>
          )}
        </div>
      </div>
      {expanded && file.status === 'processed' && (
        <ExtractionResultPanel fileId={file.id} fileName={file.original_name} apiFetch={apiFetch} description={file.description} />
      )}
    </div>
  );
}

export function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<'vault' | 'library' | 'extraction'>('vault');
  const [extractionFilter, setExtractionFilter] = useState<'all' | 'uploaded' | 'processing' | 'processed' | 'failed'>('all');
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [optimisticFiles, setOptimisticFiles] = useState<FileLike[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const libraryInputRef = useRef<HTMLInputElement>(null);
  const [libraryUploading, setLibraryUploading] = useState(false);
  const apiFetch = useApiClient();
  const queryClient = useQueryClient();
  const [bomRunId, setBomRunId] = useState<number | null>(null);
  const [bomPanelOpen, setBomPanelOpen] = useState(false);
  const [bomStarting, setBomStarting] = useState(false);
  const [activeBomRun, setActiveBomRun] = useState<BomResearchRun | null>(null);
  const [selectedBomRunId, setSelectedBomRunId] = useState<number | null>(null);
  const [emailComposerTrigger, setEmailComposerTrigger] = useState<BomEmailComposerTrigger | null>(null);
  const prevStatuses = useRef<Record<number, UploadedFile['status']>>({});

  const { data: project, isLoading: projectLoading, isError: projectError } = useQuery<Project>({
    queryKey: ['project', id],
    queryFn: async () => {
      const res = await apiFetch(`/api/projects/${id}/`);
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
    enabled: !!id,
  });

  const {
    data: files,
    isLoading: filesLoading,
    isError: filesError,
  } = useQuery<UploadedFile[]>({
    queryKey: ['project-files', id],
    queryFn: async () => {
      const res = await apiFetch(`/api/files/project/${id}/?category=vault`);
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
    enabled: !!id,
    refetchInterval: (query) => {
      const data = query.state.data as UploadedFile[] | undefined;
      return data?.some((f) => f.status === 'processing' || f.status === 'uploaded') ? 3000 : false;
    },
  });

  const { data: projectLibraryFiles = [], isLoading: libraryLoading } = useQuery<UploadedFile[]>({
    queryKey: ['project-library-files', id],
    queryFn: async () => {
      const res = await apiFetch(`/api/files/project/${id}/?category=library`);
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
    enabled: !!id,
  });

  const { data: bomRuns = [] } = useQuery<BomResearchRun[]>({
    queryKey: ['bom-runs', id],
    queryFn: async () => {
      const res = await apiFetch(`/api/bom/runs/?project_id=${id}`);
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
    enabled: !!id,
    refetchInterval: (query) => {
      const data = query.state.data as BomResearchRun[] | undefined;
      return data?.some((run) => run.status === 'researching' || run.status === 'generating_report') ? 3000 : false;
    },
  });

  const { data: selectedBomRun } = useQuery<BomResearchRun>({
    queryKey: ['bom-run', selectedBomRunId],
    queryFn: async () => {
      const res = await apiFetch(`/api/bom/runs/${selectedBomRunId}/`);
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
    enabled: !!selectedBomRunId,
    initialData: () => bomRuns.find((run) => run.id === selectedBomRunId),
    refetchInterval: (query) => {
      const data = query.state.data as BomResearchRun | undefined;
      return data && (data.status === 'researching' || data.status === 'generating_report') ? 3000 : false;
    },
  });

  const combinedFiles = useMemo<FileLike[]>(
    () => [...optimisticFiles, ...(((files ?? []) as FileLike[]))],
    [optimisticFiles, files],
  );

  useEffect(() => {
    if (!files) return;
    const prev = prevStatuses.current;
    files.forEach((f) => {
      const prevStatus = prev[f.id];
      if (prevStatus && prevStatus !== 'processed' && f.status === 'processed') {
        toast.success('Extraction complete — view results');
      }
    });
    const next: Record<number, UploadedFile['status']> = {};
    files.forEach((f) => {
      next[f.id] = f.status;
    });
    prevStatuses.current = next;
  }, [files]);

  useEffect(() => {
    if (activeBomRun) return;
    if (selectedBomRunId && bomRuns.some((run) => run.id === selectedBomRunId)) return;
    if (bomRuns.length > 0) {
      setSelectedBomRunId(bomRuns[0].id);
    }
  }, [activeBomRun, bomRuns, selectedBomRunId]);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !id) return;
    setUploadError('');
    setUploading(true);
    const tempId = -Date.now();
    const optimistic: FileLike = {
      id: tempId,
      project: Number(id),
      project_name: project?.name ?? null,
      uploaded_by: 0,
      original_name: file.name,
      description: '',
      file_type: file.name.includes('.') ? file.name.split('.').pop() || '' : '',
      file_size: file.size,
      status: 'uploaded',
      created_at: new Date().toISOString(),
      optimistic: true,
    };
    setOptimisticFiles((prev) => [...prev, optimistic]);
    try {
      const form = new FormData();
      form.append('file', file);
      form.append('project_id', id);
      const res = await apiFetch('/api/files/upload/', { method: 'POST', body: form });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.detail ?? err?.error ?? `Upload failed (${res.status})`);
      }
      toast.success('File uploaded — extracting geometry…');
      await queryClient.invalidateQueries({ queryKey: ['project-files', id] });
      await queryClient.invalidateQueries({ queryKey: ['project', id] });
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'Upload failed');
      toast.error(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
      setOptimisticFiles((prev) => prev.filter((f) => f.id !== tempId));
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  async function handleLibraryUpload(file: File) {
    if (!id) return;
    setLibraryUploading(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('project_id', id);
      fd.append('category', 'library');
      const res = await apiFetch('/api/files/upload/', { method: 'POST', body: fd });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail ?? err.error ?? 'Upload failed');
      }
      toast.success(`"${file.name}" added to Library.`);
      await queryClient.invalidateQueries({ queryKey: ['project-library-files', id] });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setLibraryUploading(false);
    }
  }

  if (projectError) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-[#8B7F73]">Project not found or access denied.</p>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">
      {/* Hidden file input — vault (CAD files) */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".step,.stp,.pdf,.dwg,.dxf,.iges,.igs"
        className="hidden"
        onChange={handleFileChange}
      />
      {/* Hidden file input — project library documents */}
      <input
        ref={libraryInputRef}
        type="file"
        accept=".xlsx,.csv,.pdf,.docx,text/csv"
        className="hidden"
        onChange={async (e) => {
          const f = e.target.files?.[0];
          if (libraryInputRef.current) libraryInputRef.current.value = '';
          if (f) await handleLibraryUpload(f);
        }}
      />

      {/* Header */}
      <div className="border-b border-[#E8E0D3] bg-white px-8 py-5">
        <div className="flex items-center gap-3 mb-4">
          <Link
            to="/vault"
            className="w-8 h-8 flex items-center justify-center hover:bg-[#F2EDE3] rounded-lg transition-colors"
          >
            <ArrowLeft className="w-[18px] h-[18px] text-[#8B7F73]" />
          </Link>
          <div className="flex-1">
            {projectLoading ? (
              <div className="animate-pulse">
                <div className="h-5 bg-[#F2EDE3] rounded w-48 mb-1.5" />
                <div className="h-3.5 bg-[#F2EDE3] rounded w-32" />
              </div>
            ) : project ? (
              <>
                <h1 className="font-display text-[26px] leading-[1.15] text-[#2B2824] tracking-tight font-medium mb-0.5">{project.name}</h1>
                <svg aria-hidden="true" viewBox="0 0 220 12" className="mb-1.5 -ml-[2px] h-[8px] w-[120px] -rotate-[0.5deg] block" fill="none" preserveAspectRatio="none">
                  <path d="M2 7 Q 22 2, 44 6 T 88 5 Q 112 9, 136 4 T 180 6 Q 200 3, 218 7" stroke="#C66A4E" strokeWidth="1.75" strokeLinecap="round" />
                </svg>
                <p className="text-[#8B7F73] text-sm">
                  {project.file_count} files · Created {formatDate(project.created_at)}
                </p>
              </>
            ) : null}
          </div>
          <div className="flex items-center gap-2">
            {uploadError && (
              <span className="text-[12px] text-[#DC2626] max-w-xs truncate">{uploadError}</span>
            )}
            <button
              onClick={async () => {
                if (!id) return;
                setBomStarting(true);
                try {
                  const res = await apiFetch('/api/bom/runs/', {
                    method: 'POST',
                    body: JSON.stringify({ project_id: Number(id) }),
                  });
                  if (!res.ok) {
                    const err = await res.json();
                    throw new Error(err.detail ?? 'Failed to start BOM run');
                  }
                  const run: BomResearchRun = await res.json();
                  setBomRunId(run.id);
                  setSelectedBomRunId(run.id);
                  await queryClient.invalidateQueries({ queryKey: ['bom-runs', id] });
                  setBomPanelOpen(true);
                } catch (err) {
                  toast.error(err instanceof Error ? err.message : 'Failed to start BOM run');
                } finally {
                  setBomStarting(false);
                }
              }}
              disabled={bomStarting}
              className="px-4 py-2 bg-white border border-[#E8E0D3] rounded-lg hover:bg-[#FFFCF7] transition-colors text-sm text-[#2B2824] flex items-center gap-2 disabled:opacity-50"
            >
              {bomStarting
                ? <Loader2 className="w-4 h-4 animate-spin" strokeWidth={1.5} />
                : <ListChecks className="w-4 h-4" strokeWidth={1.5} />}
              {selectedBomRunId ? 'New BOM Run' : 'Generate BOM'}
            </button>
            <button
              onClick={async () => {
                if (!id) return;
                try {
                  const res = await apiFetch(`/api/projects/${id}/export/`);
                  if (!res.ok) throw new Error(`Export failed (${res.status})`);
                  const data = await res.json();
                  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  const safeName = project?.name?.replace(/[^a-z0-9-_]/gi, '_') || 'project';
                  a.href = url;
                  a.download = `orbit-export-${safeName}.json`;
                  a.click();
                  URL.revokeObjectURL(url);
                  toast.success('Export downloaded');
                } catch (err) {
                  toast.error(err instanceof Error ? err.message : 'Export failed');
                }
              }}
              className="px-4 py-2 bg-white border border-[#E8E0D3] rounded-lg hover:bg-[#FFFCF7] transition-colors text-sm text-[#2B2824]"
            >
              <Download className="w-4 h-4 inline mr-2" strokeWidth={1.5} />
              Export
            </button>
            {activeTab === 'vault' || activeTab === 'extraction' ? (
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
                className="px-4 py-2 bg-[#2B2824] text-white rounded-lg hover:bg-[#3D3530] disabled:opacity-60 transition-colors text-sm flex items-center gap-2"
              >
                {uploading
                  ? <><Loader2 className="w-4 h-4 animate-spin" strokeWidth={1.5} /> Uploading…</>
                  : <><Upload className="w-4 h-4" strokeWidth={1.5} /> Upload files</>}
              </button>
            ) : (
              <button
                onClick={() => libraryInputRef.current?.click()}
                disabled={libraryUploading}
                className="px-4 py-2 bg-[#2B2824] text-white rounded-lg hover:bg-[#3D3530] disabled:opacity-60 transition-colors text-sm flex items-center gap-2"
              >
                {libraryUploading
                  ? <><Loader2 className="w-4 h-4 animate-spin" strokeWidth={1.5} /> Uploading…</>
                  : <><Upload className="w-4 h-4" strokeWidth={1.5} /> Add to Library</>}
              </button>
            )}
          </div>
        </div>

        {/* Tabs */}
        <div className="flex items-center gap-6 border-b border-[#E8E0D3] -mb-5">
          <button
            onClick={() => setActiveTab('vault')}
            className={`pb-4 border-b-2 transition-colors ${
              activeTab === 'vault' ? 'border-[#2B2824] text-[#2B2824]' : 'border-transparent text-[#8B7F73] hover:text-[#2B2824]'
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
              activeTab === 'library' ? 'border-[#2B2824] text-[#2B2824]' : 'border-transparent text-[#8B7F73] hover:text-[#2B2824]'
            }`}
          >
            <span className="text-sm flex items-center gap-2">
              <FileText className="w-4 h-4" strokeWidth={1.5} />
              Library
            </span>
          </button>
          <button
            onClick={() => setActiveTab('extraction')}
            className={`pb-4 border-b-2 transition-colors ${
              activeTab === 'extraction' ? 'border-[#2B2824] text-[#2B2824]' : 'border-transparent text-[#8B7F73] hover:text-[#2B2824]'
            }`}
          >
            <span className="text-sm flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4" strokeWidth={1.5} />
              Extraction Runs
              {files && files.filter(f => f.status === 'processing' || f.status === 'uploaded').length > 0 && (
                <span className="inline-flex items-center justify-center w-4 h-4 bg-amber-100 text-amber-700 rounded-full text-[10px] font-bold">
                  {files.filter(f => f.status === 'processing' || f.status === 'uploaded').length}
                </span>
              )}
            </span>
          </button>
        </div>
      </div>

      {/* BOM Questions Panel */}
      {bomPanelOpen && bomRunId !== null && (
        <BomQuestionsPanel
          runId={bomRunId}
          onClose={() => setBomPanelOpen(false)}
          onDraftEmail={(question: BomQuestion) => {
            setEmailComposerTrigger({
              type: 'question',
              question,
              nonce: Date.now(),
            });
          }}
          onComplete={(run) => {
            setActiveBomRun(run);
            setSelectedBomRunId(run.id);
            queryClient.invalidateQueries({ queryKey: ['bom-runs', id] });
            setBomPanelOpen(false);
          }}
        />
      )}

      {/* BOM Live Research Panel */}
      {!bomPanelOpen && activeBomRun !== null && (
        <BomLivePanel
          runId={activeBomRun.id}
          initialRun={activeBomRun}
          onClose={() => setActiveBomRun(null)}
        />
      )}

      {/* Content */}
      <div className="flex-1 overflow-auto bg-[#FAF7F2]">
        <div className="max-w-[1400px] mx-auto px-8 py-8">
          {/* BOM Analytics CTA — prominent hero banner */}
          {(() => {
            const bannerRun = activeBomRun ?? selectedBomRun ?? bomRuns.find((r) => r.status === 'completed') ?? bomRuns[0] ?? null;
            const summary = bannerRun ? computeAnalyticsSummary(bannerRun) : null;
            const hasData = summary && summary.quoteCount > 0;
            return (
              <button
                onClick={() => navigate(`/project/${id}/analytics`)}
                className="w-full mb-6 text-left group transition-transform"
                style={{ display: 'block' }}
              >
                <div
                  className="relative overflow-hidden rounded-[14px] p-6 flex items-center gap-6 transition-all group-hover:shadow-[0_8px_24px_rgba(61,47,31,0.12)]"
                  style={{
                    background: 'linear-gradient(135deg, #2B2824 0%, #4A4038 55%, #3D3530 100%)',
                    border: '1px solid #E8D6AC',
                    boxShadow: '0 4px 18px rgba(61, 47, 31, 0.08)',
                  }}
                >
                  {/* Paper grain */}
                  <svg
                    aria-hidden="true"
                    style={{ position: 'absolute', inset: 0, pointerEvents: 'none', opacity: 0.14, mixBlendMode: 'soft-light' }}
                    width="100%" height="100%"
                  >
                    <filter id="projanal-noise">
                      <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" stitchTiles="stitch" />
                      <feColorMatrix values="0 0 0 0 1  0 0 0 0 0.93  0 0 0 0 0.82  0 0 0 0.6 0" />
                    </filter>
                    <rect width="100%" height="100%" filter="url(#projanal-noise)" />
                  </svg>
                  {/* Warm glow accent */}
                  <div className="absolute top-0 right-0 w-80 h-80 pointer-events-none" style={{ background: 'radial-gradient(circle, rgba(198,106,78,0.22), transparent 65%)', filter: 'blur(28px)' }} />

                  {/* Left: icon tile */}
                  <div
                    className="relative w-14 h-14 rounded-[10px] flex items-center justify-center flex-shrink-0 rotate-[-3deg]"
                    style={{ background: '#FAF7F2', boxShadow: '0 2px 10px rgba(0,0,0,0.25)' }}
                  >
                    <BarChart3 className="w-6 h-6" style={{ color: '#C66A4E' }} strokeWidth={1.75} />
                  </div>

                  {/* Middle: title + kpis */}
                  <div className="flex-1 min-w-0 relative">
                    <p className="text-[10px] font-display uppercase tracking-[0.22em] mb-1" style={{ color: '#D4A047' }}>
                      BOM Analytics
                    </p>
                    <h2 className="font-display text-[22px] leading-[1.15] font-medium" style={{ color: '#FAF7F2' }}>
                      Full consulting-style deck
                    </h2>
                    <p className="text-[12px] italic mt-1" style={{ color: '#C4B8A8' }}>
                      {hasData
                        ? `${formatCurrency(summary!.totalSpend)} projected · ${summary!.avlCoverage.toFixed(0)}% AVL · ${summary!.riskCount} risk${summary!.riskCount !== 1 ? 's' : ''}`
                        : bomRuns.length > 0
                          ? 'Generate or complete a BOM run to unlock the full deck'
                          : 'Executive summary · 6 exhibits · automated findings'}
                    </p>

                    {hasData && summary && (
                      <div className="flex items-center gap-5 mt-3">
                        <InlineStat icon={DollarSign} label="Spend" value={formatCurrency(summary.totalSpend)} />
                        <div className="w-px h-6" style={{ background: 'rgba(250, 247, 242, 0.15)' }} />
                        <InlineStat icon={CheckCircle2} label="Parts" value={`${summary.itemCount}`} />
                        <div className="w-px h-6" style={{ background: 'rgba(250, 247, 242, 0.15)' }} />
                        <InlineStat icon={Shield} label="AVL" value={`${summary.avlCoverage.toFixed(0)}%`} tone={summary.avlCoverage >= 80 ? 'positive' : summary.avlCoverage >= 50 ? 'caution' : 'risk'} />
                        <div className="w-px h-6" style={{ background: 'rgba(250, 247, 242, 0.15)' }} />
                        <InlineStat icon={AlertTriangle} label="Risks" value={`${summary.riskCount}`} tone={summary.riskCount === 0 ? 'positive' : 'risk'} />
                      </div>
                    )}
                  </div>

                  {/* Right: action */}
                  <div className="flex-shrink-0 flex items-center gap-2 relative">
                    <span
                      className="text-[11px] font-display uppercase tracking-[0.2em] px-4 py-2.5 rounded-[6px] flex items-center gap-2 transition-transform group-hover:translate-x-1"
                      style={{ background: '#C66A4E', color: '#FAF7F2', boxShadow: '0 2px 8px rgba(198,106,78,0.4)' }}
                    >
                      Open the deck
                      <ArrowRight className="w-3.5 h-3.5" strokeWidth={2} />
                    </span>
                  </div>
                </div>
              </button>
            );
          })()}

          <BomEmailPanel
            runId={activeBomRun?.id ?? selectedBomRunId}
            runStatus={(selectedBomRun ?? activeBomRun)?.status}
            composerTrigger={emailComposerTrigger}
            onComposerTriggerHandled={() => setEmailComposerTrigger(null)}
          />

          <BomResultsPanel
            runs={bomRuns}
            selectedRun={activeBomRun ?? selectedBomRun ?? null}
            selectedRunId={activeBomRun?.id ?? selectedBomRunId}
            onSelectRun={(runId) => setSelectedBomRunId(runId)}
          />

          {activeTab === 'extraction' && (() => {
            const FILTERS = [
              { value: 'all' as const, label: 'All' },
              { value: 'processing' as const, label: 'Processing' },
              { value: 'processed' as const, label: 'Extracted' },
              { value: 'failed' as const, label: 'Failed' },
            ];
            const filtered = combinedFiles.filter((f) => {
              if (extractionFilter === 'all') return true;
              return f.status === extractionFilter;
            });
            return (
              <div>
                {/* Filter chips */}
                <div className="flex items-center gap-2 mb-4">
                  {FILTERS.map((f) => {
                    const count = f.value === 'all'
                      ? combinedFiles.length
                      : combinedFiles.filter(x => x.status === f.value).length;
                    return (
                      <button
                        key={f.value}
                        onClick={() => setExtractionFilter(f.value)}
                        className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[12px] font-medium border transition-colors ${
                          extractionFilter === f.value
                            ? 'bg-[#2B2824] text-white border-[#2B2824]'
                            : 'bg-white text-[#8B7F73] border-[#E8E0D3] hover:border-[#A89D91]'
                        }`}
                      >
                        {f.label}
                        <span className={`text-[10px] font-bold ${extractionFilter === f.value ? 'text-white/60' : 'text-[#A89D91]'}`}>
                          {count}
                        </span>
                      </button>
                    );
                  })}
                </div>

                {/* Extraction run cards */}
                {filtered.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-16 bg-white border border-[#E8E0D3] rounded-xl text-center">
                    <CheckCircle2 className="w-8 h-8 text-[#D1D5DB] mb-3" strokeWidth={1.5} />
                    <p className="text-[#2B2824] text-sm font-medium mb-1">No extraction runs</p>
                    <p className="text-[#8B7F73] text-[12px]">Upload CAD files to start an extraction run.</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {filtered.map((file) => (
                      <ExtractionRunCard key={file.id} file={file} apiFetch={apiFetch} projectId={id!} />
                    ))}
                  </div>
                )}
              </div>
            );
          })()}

          {activeTab === 'vault' ? (
            <div className="bg-white border border-[#E8E0D3] rounded-xl overflow-hidden">
              <div className="grid grid-cols-12 gap-4 px-6 py-3 border-b border-[#E8E0D3] bg-[#FFFCF7]">
                <div className="col-span-5"><span className="text-[#8B7F73] text-[12px] font-medium uppercase tracking-wide">Name</span></div>
                <div className="col-span-2"><span className="text-[#8B7F73] text-[12px] font-medium uppercase tracking-wide">Type</span></div>
                <div className="col-span-2"><span className="text-[#8B7F73] text-[12px] font-medium uppercase tracking-wide">Size</span></div>
                <div className="col-span-2"><span className="text-[#8B7F73] text-[12px] font-medium uppercase tracking-wide">Status</span></div>
                <div className="col-span-1 flex justify-end"><span className="text-[#8B7F73] text-[12px] font-medium uppercase tracking-wide">Actions</span></div>
              </div>

              {filesLoading && Array.from({ length: 4 }).map((_, i) => <SkeletonRow key={i} />)}

              {filesError && (
                <div className="px-6 py-8 text-center">
                  <p className="text-[#8B7F73] text-sm">Failed to load files.</p>
                </div>
              )}

              {combinedFiles.length === 0 && (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <div className="w-10 h-10 bg-[#F2EDE3] rounded-lg flex items-center justify-center mb-3">
                    <File className="w-5 h-5 text-[#8B7F73]" strokeWidth={1.5} />
                  </div>
                  <p className="text-[#2B2824] text-sm font-medium mb-1">No files uploaded yet</p>
                  <p className="text-[#8B7F73] text-[12px]">Click "Upload files" to add STEP, PDF, or CAD files.</p>
                </div>
              )}

              {combinedFiles.map((file) => (
                <FileRow key={file.id} file={file} apiFetch={apiFetch} projectId={id!} />
              ))}
            </div>
          ) : libraryLoading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="w-6 h-6 animate-spin text-[#9CA3AF]" />
            </div>
          ) : projectLibraryFiles.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <div className="w-12 h-12 bg-[#F2EDE3] rounded-xl flex items-center justify-center mb-4">
                <BookOpen className="w-6 h-6 text-[#8B7F73]" strokeWidth={1.5} />
              </div>
              <p className="text-[#111111] font-medium mb-1">Library is empty</p>
              <p className="text-[#6B7280] text-sm">Click "Add to Library" to upload spreadsheets, specs, and other non-engineering docs for this project.</p>
            </div>
          ) : (
            <div className="bg-white border border-[#E6E6E6] rounded-xl overflow-hidden">
              <div className="grid grid-cols-12 gap-4 px-6 py-3 border-b border-[#E6E6E6] bg-[#FAFAFA]">
                <div className="col-span-5"><span className="text-[#6B7280] text-[12px] font-medium uppercase tracking-wide">Name</span></div>
                <div className="col-span-2"><span className="text-[#6B7280] text-[12px] font-medium uppercase tracking-wide">Type</span></div>
                <div className="col-span-2"><span className="text-[#6B7280] text-[12px] font-medium uppercase tracking-wide">Size</span></div>
                <div className="col-span-2"><span className="text-[#6B7280] text-[12px] font-medium uppercase tracking-wide">Uploaded</span></div>
                <div className="col-span-1" />
              </div>
              {projectLibraryFiles.map((doc) => (
                <div key={doc.id} className="grid grid-cols-12 gap-4 px-6 py-3 border-b border-[#F4F4F4] last:border-0 items-center group">
                  <div className="col-span-5 flex items-center gap-2 min-w-0">
                    <FileText className="w-4 h-4 text-[#A89D91] flex-shrink-0" strokeWidth={1.5} />
                    <span className="text-sm text-[#2B2824] truncate">{doc.original_name}</span>
                  </div>
                  <div className="col-span-2">
                    <span className="px-2 py-0.5 text-[11px] rounded-full border font-medium bg-[#F4F4F4] text-[#6B7280] border-[#E6E6E6] uppercase">
                      {doc.file_type || '—'}
                    </span>
                  </div>
                  <div className="col-span-2">
                    <span className="text-sm text-[#6B7280]">{formatBytes(doc.file_size)}</span>
                  </div>
                  <div className="col-span-2">
                    <span className="text-sm text-[#6B7280]">{formatDate(doc.created_at)}</span>
                  </div>
                  <div className="col-span-1 flex items-center gap-1 justify-end opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={async () => {
                        try {
                          const res = await apiFetch(`/api/files/${doc.id}/download/`);
                          if (!res.ok) throw new Error('Download failed');
                          const data = await res.json();
                          if (data?.url) window.open(data.url, '_blank', 'noopener');
                        } catch {
                          toast.error('Download failed');
                        }
                      }}
                      className="p-1.5 rounded hover:bg-[#F4F4F4] text-[#9CA3AF] hover:text-[#111111] transition-colors"
                      title="Download"
                    >
                      <Download className="w-3.5 h-3.5" strokeWidth={1.5} />
                    </button>
                    <button
                      onClick={async () => {
                        if (!confirm(`Remove "${doc.original_name}" from the library?`)) return;
                        try {
                          const res = await apiFetch(`/api/files/${doc.id}/`, { method: 'DELETE' });
                          if (!res.ok && res.status !== 204) throw new Error('Delete failed');
                          toast.success('File removed from library.');
                          queryClient.invalidateQueries({ queryKey: ['project-library-files', id] });
                        } catch {
                          toast.error('Failed to remove file.');
                        }
                      }}
                      className="p-1.5 rounded hover:bg-[#FEF2F2] text-[#9CA3AF] hover:text-red-600 transition-colors"
                      title="Remove"
                    >
                      <Trash className="w-3.5 h-3.5" strokeWidth={1.5} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

    </div>
  );
}
