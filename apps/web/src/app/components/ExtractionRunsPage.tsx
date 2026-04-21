import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router';
import { useApiClient } from '../../api/client';
import type { UploadedFile, ExtractionResult } from '../../api/types';
import { AlertTriangle, CheckCircle2, Loader2, AlertCircle, Plus, ChevronDown, ChevronUp, File } from 'lucide-react';
import { toast } from 'sonner';

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

// ── Confidence pip (light variant) ───────────────────────────────────────────
// TODO dark mode: use rgba(167,139,250,0.18)/#C4B5FD (high), rgba(251,191,36,0.18)/#FCD34D (med), rgba(248,113,113,0.18)/#FCA5A5 (low)
function ConfidencePip({ value }: { value: number }) {
  const [bg, text] =
    value >= 0.85
      ? ['rgba(109,40,217,0.10)', '#6D28D9']
      : value >= 0.6
      ? ['rgba(217,119,6,0.10)', '#D97706']
      : ['rgba(220,38,38,0.10)', '#DC2626'];
  return (
    <span
      className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold tabular-nums"
      style={{ background: bg, color: text }}
    >
      {value.toFixed(2)}
    </span>
  );
}

// ── Light profile card ────────────────────────────────────────────────────────
// TODO dark mode: rename back to DarkProfileCard and use:
//   card bg: linear-gradient(160deg, #0D0D1A 0%, #111126 100%)
//   part label color: #A78BFA
//   badge bg/color/border: rgba(255,255,255,0.06) / rgba(255,255,255,0.45) / rgba(255,255,255,0.10)
//   divider: rgba(255,255,255,0.07)
//   label color: rgba(255,255,255,0.35)
//   value color: rgba(255,255,255,0.85)
//   pill bg/color: rgba(255,255,255,0.08) / rgba(255,255,255,0.7)
//   empty dash: rgba(255,255,255,0.2)
//   provenance bg/border: rgba(255,255,255,0.04) / rgba(255,255,255,0.07)
//   provenance label: rgba(255,255,255,0.3)
//   source meta: rgba(255,255,255,0.45) / rgba(255,255,255,0.3) / rgba(255,255,255,0.25)
function LightProfileCard({ profile, fileName }: {
  profile: ExtractionResult['profile'];
  fileName: string;
}) {
  if (!profile) return null;

  const partLabel = profile.part_number ?? fileName.replace(/\.[^.]+$/, '');
  const hasProvenance =
    profile.provenance.sources.length > 0 || profile.provenance.warnings.length > 0;

  return (
    <div className="rounded-xl overflow-hidden bg-white border border-[#E6E6E6]">
      {/* Part number + badge */}
      <div className="flex items-center justify-between px-5 pt-5 pb-3">
        <span className="text-[15px] font-bold tracking-wider text-[#111111]">
          {partLabel}
        </span>
        <span
          className="text-[10px] font-semibold tracking-widest uppercase px-2.5 py-1 rounded-full"
          style={{ background: '#F3F4F6', color: '#6B7280', border: '1px solid #E5E7EB' }}
        >
          Extracted
        </span>
      </div>

      {/* Divider */}
      <div className="mx-5 mb-1 h-px bg-[#E6E6E6]" />

      {/* Fields */}
      <div className="px-5 py-2 space-y-0">
        {[
          { label: 'Name', value: profile.name, confidence: null },
          { label: 'Material', value: profile.material?.value, confidence: profile.material?.confidence ?? null },
          { label: 'Category', value: profile.category, confidence: null, pill: true },
          { label: 'Dimensions', value: profile.dimensions, confidence: null },
          { label: 'Revision', value: profile.revision, confidence: null },
          { label: 'Volume', value: profile.volume?.value, confidence: profile.volume?.confidence ?? null },
        ].map(({ label, value, confidence, pill }) => (
          <div
            key={label}
            className="flex items-center justify-between gap-4 py-2.5 border-b border-[#F3F4F6]"
          >
            <span className="text-[11px] font-medium w-20 flex-shrink-0 text-[#9CA3AF]">
              {label}
            </span>
            <span className="flex-1 text-[13px] font-medium text-right text-[#111111]">
              {value ? (
                pill ? (
                  <span
                    className="inline-block px-2.5 py-0.5 rounded-full text-[11px] font-semibold"
                    style={{ background: '#F3F4F6', color: '#4B5563' }}
                  >
                    {value}
                  </span>
                ) : value
              ) : (
                <span className="text-[#D1D5DB]">—</span>
              )}
            </span>
            {confidence != null && (
              <div className="flex-shrink-0">
                <ConfidencePip value={confidence} />
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Provenance */}
      {hasProvenance && (
        <div className="mx-5 mt-3 mb-5 rounded-lg px-4 py-3 bg-[#F9FAFB] border border-[#E5E7EB]">
          <p className="text-[10px] font-semibold uppercase tracking-widest mb-2 text-[#9CA3AF]">
            Provenance
          </p>
          {profile.provenance.sources.length > 0 && (
            <p className="text-[12px] mb-2 text-[#6B7280]">
              <span className="text-[#9CA3AF]">Sources: </span>
              {profile.provenance.sources.map((s, i) => (
                <span key={i}>
                  {i > 0 && <span className="text-[#D1D5DB]">, </span>}
                  <span className="text-[#2563EB]">{s}</span>
                </span>
              ))}
            </p>
          )}
          {profile.provenance.warnings.map((w, i) => (
            <div
              key={i}
              className="flex items-start gap-2 text-[12px] mt-1.5 px-3 py-2 rounded-lg"
              style={{ background: 'rgba(217,119,6,0.06)', border: '1px solid rgba(217,119,6,0.20)', color: '#D97706' }}
            >
              <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" strokeWidth={2} />
              {w}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Per-run card ──────────────────────────────────────────────────────────────
function ExtractionRunCard({ file, apiFetch, queryClient }: {
  file: UploadedFile;
  apiFetch: ReturnType<typeof useApiClient>;
  queryClient: ReturnType<typeof useQueryClient>;
}) {
  const [expanded, setExpanded] = useState(false);
  const [extracting, setExtracting] = useState(false);

  const { data: result, isLoading: resultLoading } = useQuery<ExtractionResult>({
    queryKey: ['file-result', file.id],
    queryFn: async () => {
      const res = await apiFetch(`/api/files/${file.id}/result/`);
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
    enabled: expanded && file.status === 'processed',
  });

  const handleExtract = async () => {
    setExtracting(true);
    try {
      const res = await apiFetch(`/api/files/${file.id}/extract/`, { method: 'POST' });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.error ?? `Failed (${res.status})`);
      }
      await queryClient.invalidateQueries({ queryKey: ['all-files'] });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to start extraction');
    } finally {
      setExtracting(false);
    }
  };

  // TODO dark mode — processed badge: rgba(52,211,153,0.12) / #34D399 / rgba(52,211,153,0.25) (green)
  // Light mode uses blue for the extracted/processed status instead of green
  const statusBadge = {
    processed: { label: 'Extracted', bg: 'rgba(37,99,235,0.08)', color: '#2563EB', border: 'rgba(37,99,235,0.20)' },
    processing: { label: 'Processing', bg: 'rgba(217,119,6,0.08)', color: '#D97706', border: 'rgba(217,119,6,0.20)' },
    uploaded:   { label: 'Ready',      bg: 'rgba(107,114,128,0.08)', color: '#6B7280', border: 'rgba(107,114,128,0.20)' },
    failed:     { label: 'Failed',     bg: 'rgba(220,38,38,0.08)',  color: '#DC2626', border: 'rgba(220,38,38,0.20)' },
  }[file.status] ?? { label: file.status, bg: 'rgba(107,114,128,0.08)', color: '#6B7280', border: 'rgba(107,114,128,0.20)' };

  const isSpinning = file.status === 'processing';

  // TODO dark mode — card bg: linear-gradient(160deg, #0D0D1A 0%, #111126 100%), border: rgba(255,255,255,0.08)
  return (
    <div className="rounded-xl overflow-hidden transition-all bg-white border border-[#E6E6E6]">
      {/* Card header */}
      <div className="flex items-center gap-3 px-5 py-4">
        {/* TODO dark mode — icon bg: rgba(255,255,255,0.06), icon color: rgba(255,255,255,0.35) */}
        <div className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 bg-[#F3F4F6]">
          <File className="w-[18px] h-[18px] text-[#9CA3AF]" strokeWidth={1.5} />
        </div>
        <div className="flex-1 min-w-0">
          {/* TODO dark mode — filename: rgba(255,255,255,0.85), meta: rgba(255,255,255,0.3) */}
          <p className="text-[13px] font-semibold truncate text-[#111111]">
            {file.original_name}
          </p>
          <p className="text-[11px] mt-0.5 text-[#9CA3AF]">
            {file.project_name && <span>{file.project_name} · </span>}
            {formatDate(file.created_at)} · {formatBytes(file.file_size)} ·{' '}
            <span className="uppercase font-medium">{file.file_type || '—'}</span>
          </p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {file.status === 'uploaded' ? (
            <button
              onClick={handleExtract}
              disabled={extracting}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-semibold transition-all disabled:opacity-50"
              style={{ background: 'rgba(167,139,250,0.12)', border: '1px solid rgba(167,139,250,0.30)', color: '#7C3AED' }}
            >
              {extracting
                ? <><Loader2 className="w-3 h-3 animate-spin" strokeWidth={2.5} /> Starting…</>
                : 'Run Extraction'}
            </button>
          ) : (
            <span
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-semibold tracking-wide"
              style={{ background: statusBadge.bg, color: statusBadge.color, border: `1px solid ${statusBadge.border}` }}
            >
              {isSpinning
                ? <Loader2 className="w-2.5 h-2.5 animate-spin" strokeWidth={2.5} />
                : file.status === 'processed'
                ? <CheckCircle2 className="w-2.5 h-2.5" strokeWidth={2.5} />
                : file.status === 'failed'
                ? <AlertCircle className="w-2.5 h-2.5" strokeWidth={2.5} />
                : null}
              {statusBadge.label}
            </span>
          )}
          {file.status === 'processed' && (
            // TODO dark mode — chevron color: rgba(255,255,255,0.35), hover bg: rgba(255,255,255,0.08)
            <button
              onClick={() => setExpanded((v) => !v)}
              className="w-8 h-8 flex items-center justify-center rounded-lg transition-colors text-[#9CA3AF] hover:bg-[#F3F4F6]"
              title={expanded ? 'Collapse' : 'View profile'}
            >
              {expanded
                ? <ChevronUp className="w-4 h-4" />
                : <ChevronDown className="w-4 h-4" />}
            </button>
          )}
          {file.status === 'failed' && (
            <button
              onClick={handleExtract}
              disabled={extracting}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-semibold transition-all disabled:opacity-50"
              style={{ background: 'rgba(220,38,38,0.08)', border: '1px solid rgba(220,38,38,0.20)', color: '#DC2626' }}
            >
              {extracting ? <Loader2 className="w-3 h-3 animate-spin" strokeWidth={2.5} /> : 'Retry'}
            </button>
          )}
        </div>
      </div>

      {/* Expanded: profile */}
      {expanded && file.status === 'processed' && (
        // TODO dark mode — expanded border: rgba(255,255,255,0.06)
        <div className="border-t border-[#E6E6E6]">
          {resultLoading ? (
            <div className="flex items-center justify-center py-10">
              {/* TODO dark mode — spinner: rgba(255,255,255,0.25) */}
              <Loader2 className="w-5 h-5 animate-spin text-[#9CA3AF]" />
            </div>
          ) : result?.profile && Object.keys(result.profile).length > 0 ? (
            <LightProfileCard profile={result.profile} fileName={file.original_name} />
          ) : (
            // TODO dark mode — empty text: rgba(255,255,255,0.3)
            <p className="px-5 py-6 text-[12px] text-[#9CA3AF]">
              No engineering profile available for this file.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────
export function ExtractionRunsPage() {
  const apiFetch = useApiClient();
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();

  const statusParam = searchParams.get('status') ?? 'pending';

  const { data: allFiles = [], isLoading: filesLoading } = useQuery<UploadedFile[]>({
    queryKey: ['all-files'],
    queryFn: async () => {
      const res = await apiFetch('/api/files/');
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
    refetchInterval: (query) => {
      const data = query.state.data as UploadedFile[] | undefined;
      return data?.some((f) => f.status === 'processing') ? 4000 : false;
    },
  });

  // "Pending" = files uploaded from the Vault that haven't had an extraction run yet (status: uploaded)
  const FILTERS = [
    {
      value: 'pending',
      label: 'Pending',
      count: allFiles.filter((f) => f.status === 'uploaded').length,
    },
    {
      value: 'active',
      label: 'Active',
      count: allFiles.filter((f) => f.status === 'processing').length,
    },
    {
      value: 'extracted',
      label: 'Extracted',
      count: allFiles.filter((f) => f.status === 'processed').length,
    },
    {
      value: 'failed',
      label: 'Failed',
      count: allFiles.filter((f) => f.status === 'failed').length,
    },
  ];

  const filtered = allFiles.filter((f) => {
    if (statusParam === 'pending') return f.status === 'uploaded';
    if (statusParam === 'active') return f.status === 'processing';
    if (statusParam === 'extracted') return f.status === 'processed';
    if (statusParam === 'failed') return f.status === 'failed';
    return true;
  });

  const emptyMessages: Record<string, { heading: string; sub: string }> = {
    pending: {
      heading: 'No vault files pending extraction',
      sub: 'Upload files in the Vault — they will appear here ready to run.',
    },
    active: {
      heading: 'No active runs',
      sub: 'Start an extraction run from the Pending tab.',
    },
    extracted: {
      heading: 'No extracted files yet',
      sub: 'Successfully extracted files will appear here.',
    },
    failed: {
      heading: 'No failed runs',
      sub: 'Any files that fail extraction will appear here.',
    },
  };

  const empty = emptyMessages[statusParam] ?? { heading: 'Nothing here', sub: '' };

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden" style={{ background: '#F7F7F7' }}>
      {/* Header */}
      <div className="bg-white border-b border-[#E6E6E6] px-8 py-5 flex items-center justify-between">
        <div>
          <h1 className="text-[#111111] text-lg font-semibold leading-none mb-1">Extraction Runs</h1>
          <p className="text-[#9CA3AF] text-[13px]">
            {allFiles.length} file{allFiles.length !== 1 ? 's' : ''} across all projects
          </p>
        </div>
        {/* New Run navigates to the Pending tab where vault-uploaded files await extraction */}
        <a
          href="/extraction-runs?status=pending"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors no-underline"
          style={{ background: '#111111', color: '#fff' }}
        >
          <Plus className="w-4 h-4" strokeWidth={2} />
          New Run
        </a>
      </div>

      {/* Filter chips */}
      <div className="bg-white border-b border-[#E6E6E6] px-8 py-3 flex items-center gap-2">
        {FILTERS.map((f) => {
          const active = statusParam === f.value;
          return (
            <a
              key={f.value}
              href={`/extraction-runs?status=${f.value}`}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[12px] font-medium border transition-colors no-underline"
              style={active
                ? { background: '#111111', color: '#fff', borderColor: '#111111' }
                : { background: '#fff', color: '#6B7280', borderColor: '#E6E6E6' }}
            >
              {f.label}
              <span className="text-[10px] font-bold" style={{ opacity: active ? 0.5 : 0.7 }}>
                {f.count}
              </span>
            </a>
          );
        })}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto px-8 py-8">
        {filesLoading ? (
          <div className="space-y-3">
            {/* TODO dark mode — skeleton: linear-gradient(160deg, #0D0D1A 0%, #111126 100%) at opacity 0.4 */}
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-20 rounded-xl animate-pulse bg-[#E5E7EB]" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          // TODO dark mode — empty state bg: linear-gradient(160deg, #0D0D1A 0%, #111126 100%), border: rgba(255,255,255,0.07)
          //   icon: rgba(255,255,255,0.15), heading: rgba(255,255,255,0.5), sub: rgba(255,255,255,0.25)
          <div className="flex flex-col items-center justify-center py-24 rounded-xl text-center bg-white border border-[#E6E6E6]">
            <CheckCircle2 className="w-10 h-10 mb-4 text-[#D1D5DB]" strokeWidth={1.5} />
            <p className="text-[15px] font-medium mb-2 text-[#6B7280]">{empty.heading}</p>
            <p className="text-[12px] text-[#9CA3AF]">{empty.sub}</p>
          </div>
        ) : (
          <div className="space-y-3 max-w-3xl">
            {filtered.map((file) => (
              <ExtractionRunCard key={file.id} file={file} apiFetch={apiFetch} queryClient={queryClient} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
