/**
 * BomLivePanel — real-time agent activity visualizer.
 *
 * Polls GET /api/bom/runs/<id>/ every 1.5 s while the run is active,
 * streams the research_log as animated entries, and shows line items
 * transitioning: pending → researching → sourced.
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import {
  X,
  Search,
  Wrench,
  DollarSign,
  AlertTriangle,
  Sparkles,
  BookOpen,
  Info,
  AlertCircle,
  CheckCircle2,
  Loader2,
  ChevronDown,
  ChevronUp,
  Package,
  BarChart3,
} from 'lucide-react';
import { useApiClient } from '../../api/client';
import type { BomResearchRun, BomLineItem } from '../../api/types';

// ── Types ─────────────────────────────────────────────────────────────────────

interface LogEntry {
  ts: string;
  type: string;
  message: string;
}

interface Props {
  runId: number;
  initialRun?: BomResearchRun;
  onClose: () => void;
}

// ── Log entry config ──────────────────────────────────────────────────────────

interface LogConfig {
  Icon: React.ComponentType<{ className?: string }>;
  dot: string;      // Tailwind bg colour for the dot
  text: string;     // Tailwind text colour for message
  label: string;
}

const LOG_CONFIG: Record<string, LogConfig> = {
  search:   { Icon: Search,        dot: 'bg-blue-400',    text: 'text-blue-100',   label: 'SEARCH'   },
  material: { Icon: Wrench,        dot: 'bg-violet-400',  text: 'text-violet-100', label: 'MATERIAL' },
  quote:    { Icon: DollarSign,    dot: 'bg-emerald-400', text: 'text-emerald-100',label: 'QUOTE'    },
  risk:     { Icon: AlertTriangle, dot: 'bg-amber-400',   text: 'text-amber-100',  label: 'RISK'     },
  summary:  { Icon: Sparkles,      dot: 'bg-indigo-400',  text: 'text-indigo-100', label: 'SUMMARY'  },
  library:  { Icon: BookOpen,      dot: 'bg-teal-400',    text: 'text-teal-100',   label: 'LIBRARY'  },
  info:     { Icon: Info,          dot: 'bg-slate-400',   text: 'text-slate-200',  label: 'INFO'     },
  warn:     { Icon: AlertTriangle, dot: 'bg-amber-400',   text: 'text-amber-200',  label: 'WARN'     },
  error:    { Icon: AlertCircle,   dot: 'bg-red-400',     text: 'text-red-200',    label: 'ERROR'    },
};

const DEFAULT_LOG_CONFIG: LogConfig = {
  Icon: Info,
  dot: 'bg-slate-400',
  text: 'text-slate-200',
  label: 'LOG',
};

// ── Status config ─────────────────────────────────────────────────────────────

function RunStatusBadge({ status }: { status: BomResearchRun['status'] }) {
  const cfg = {
    gathering_inputs:    { color: 'bg-slate-500/40 text-slate-200 border-slate-400/30', label: 'Gathering inputs',   spin: false },
    researching:         { color: 'bg-blue-500/30  text-blue-200  border-blue-400/30',  label: 'Researching…',       spin: true  },
    generating_report:   { color: 'bg-indigo-500/30 text-indigo-200 border-indigo-400/30', label: 'Generating report…', spin: true },
    awaiting_team_input: { color: 'bg-amber-500/30 text-amber-200 border-amber-400/30', label: 'Awaiting input',    spin: false },
    completed:           { color: 'bg-emerald-500/30 text-emerald-200 border-emerald-400/30', label: 'Completed',   spin: false },
    failed:              { color: 'bg-red-500/30   text-red-200   border-red-400/30',   label: 'Failed',             spin: false },
  }[status] ?? { color: 'bg-slate-500/40 text-slate-200 border-slate-400/30', label: status, spin: false };

  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold border ${cfg.color}`}>
      {cfg.spin
        ? <Loader2 className="w-3 h-3 animate-spin" />
        : status === 'completed'
          ? <span className="w-2 h-2 rounded-full bg-emerald-400" style={{ boxShadow: '0 0 6px rgba(52,211,153,0.9)' }} />
          : <span className="w-2 h-2 rounded-full bg-current opacity-70" />}
      {cfg.label}
    </span>
  );
}

// ── Line item card ────────────────────────────────────────────────────────────

function LineItemCard({ item, resultsJson }: { item: BomLineItem; resultsJson: Record<string, unknown> }) {
  const [open, setOpen] = useState(false);
  const itemKey = `item_${item.id}`;
  const result = (resultsJson[itemKey] ?? {}) as Record<string, unknown>;
  const riskFlags = (result.risk_flags ?? []) as string[];
  const summary = result.summary as string | undefined;

  const statusCfg = {
    pending:     { color: 'bg-slate-100 text-slate-500 border-slate-200',         label: 'Pending',      spin: false },
    researching: { color: 'bg-blue-50  text-blue-600  border-blue-200',            label: 'Researching',  spin: true  },
    sourced:     { color: 'bg-emerald-50 text-emerald-700 border-emerald-200',     label: 'Sourced',      spin: false },
    needs_input: { color: 'bg-amber-50 text-amber-700 border-amber-200',           label: 'Needs input',  spin: false },
  }[item.status] ?? { color: 'bg-slate-100 text-slate-500 border-slate-200', label: item.status, spin: false };

  return (
    <div className="bg-white rounded-xl border border-[#EBEBEB] overflow-hidden transition-all">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-start gap-3 p-3.5 text-left hover:bg-[#FAFAFA] transition-colors"
      >
        {/* Part icon */}
        <div className="w-8 h-8 rounded-lg bg-[#F4F4F4] flex items-center justify-center flex-shrink-0 mt-0.5">
          <Package className="w-4 h-4 text-[#6B7280]" strokeWidth={1.5} />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="text-[13px] font-medium text-[#111111] truncate">{item.part_name}</p>
            {item.part_number && (
              <span className="text-[10px] font-mono text-[#9CA3AF]">{item.part_number}</span>
            )}
          </div>
          {item.material_spec && (
            <p className="text-[11px] text-[#6B7280] mt-0.5">{item.material_spec}</p>
          )}
          <div className="flex items-center gap-2 mt-1.5 flex-wrap">
            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold border ${statusCfg.color}`}>
              {statusCfg.spin
                ? <Loader2 className="w-2.5 h-2.5 animate-spin" />
                : null}
              {statusCfg.label}
            </span>
            {item.quotes.length > 0 && (
              <span className="text-[11px] text-[#6B7280]">{item.quotes.length} quote{item.quotes.length !== 1 ? 's' : ''}</span>
            )}
            {riskFlags.length > 0 && (
              <span className="text-[10px] text-amber-600 font-medium">⚠ {riskFlags.length} risk{riskFlags.length !== 1 ? 's' : ''}</span>
            )}
          </div>
        </div>

        <div className="flex-shrink-0 text-[#9CA3AF] mt-1">
          {open ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </div>
      </button>

      {open && (
        <div className="border-t border-[#F0F0F0] px-3.5 py-3 space-y-3 bg-[#FAFAFA]">
          {/* Quotes table */}
          {item.quotes.length > 0 && (
            <div>
              <p className="text-[10px] font-semibold text-[#9CA3AF] uppercase tracking-widest mb-2">Supplier Quotes</p>
              <div className="space-y-1.5">
                {item.quotes.map((q) => (
                  <div key={q.id} className="bg-white rounded-lg border border-[#EBEBEB] px-3 py-2">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[12px] font-medium text-[#111111]">{q.supplier_name}</span>
                      <span className="text-[12px] font-semibold text-emerald-700">${Number(q.unit_price).toFixed(2)}</span>
                    </div>
                    <div className="flex items-center gap-3 mt-0.5">
                      <span className="text-[11px] text-[#9CA3AF]">MOQ {q.moq}</span>
                      <span className="text-[11px] text-[#9CA3AF]">{q.lead_time_days}d lead</span>
                      {Number(q.tooling_cost) > 0 && (
                        <span className="text-[11px] text-[#9CA3AF]">tooling ${Number(q.tooling_cost).toFixed(0)}</span>
                      )}
                    </div>
                    {q.notes && (
                      <p className="text-[11px] text-[#6B7280] mt-1 leading-snug">{q.notes}</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Risk flags */}
          {riskFlags.length > 0 && (
            <div>
              <p className="text-[10px] font-semibold text-[#9CA3AF] uppercase tracking-widest mb-1.5">Risk Flags</p>
              <div className="flex flex-wrap gap-1.5">
                {riskFlags.map((f) => (
                  <span key={f} className="px-2 py-0.5 rounded-full bg-amber-50 border border-amber-200 text-[10px] font-medium text-amber-700">
                    {f.replace(/-/g, ' ')}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* AI summary */}
          {summary && (
            <div>
              <p className="text-[10px] font-semibold text-[#9CA3AF] uppercase tracking-widest mb-1.5">AI Summary</p>
              <p className="text-[12px] text-[#374151] leading-relaxed">{summary}</p>
            </div>
          )}

          {!item.quotes.length && !summary && (
            <p className="text-[12px] text-[#9CA3AF] italic">No data yet…</p>
          )}
        </div>
      )}
    </div>
  );
}

// ── Log entry row ─────────────────────────────────────────────────────────────

function LogRow({ entry, isNew }: { entry: LogEntry; isNew: boolean }) {
  const cfg = LOG_CONFIG[entry.type] ?? DEFAULT_LOG_CONFIG;
  const { Icon, dot, text } = cfg;

  return (
    <div
      className={`flex items-start gap-2.5 py-1 transition-opacity duration-300 ${isNew ? 'animate-[fadeSlideIn_0.25s_ease_forwards]' : ''}`}
    >
      {/* Dot + vertical line guide */}
      <div className="flex flex-col items-center flex-shrink-0 mt-[3px]">
        <div className={`w-2 h-2 rounded-full flex-shrink-0 ${dot}`} />
      </div>

      {/* Timestamp */}
      <span className="text-[10px] font-mono text-slate-500 flex-shrink-0 mt-px leading-[1.6]">{entry.ts}</span>

      {/* Icon */}
      <Icon className={`w-3 h-3 flex-shrink-0 mt-0.5 ${text} opacity-70`} />

      {/* Message */}
      <span className={`text-[11px] font-mono leading-relaxed break-all ${text}`}>{entry.message}</span>
    </div>
  );
}

// ── Completion summary ────────────────────────────────────────────────────────

function CompletionBanner({ run }: { run: BomResearchRun }) {
  const allPrices = run.line_items.flatMap((item) =>
    item.quotes.map((q) => Number(q.unit_price))
  );
  const avgPrice = allPrices.length
    ? allPrices.reduce((a, b) => a + b, 0) / allPrices.length
    : null;
  const sourced = run.line_items.filter((i) => i.status === 'sourced').length;
  const needsInput = run.line_items.filter((i) => i.status === 'needs_input').length;
  const totalQuotes = run.line_items.reduce((s, i) => s + i.quotes.length, 0);

  return (
    <div className="rounded-xl overflow-hidden border border-emerald-200 bg-emerald-50 mb-4">
      <div className="px-4 py-3 flex items-center gap-3">
        <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
        <div>
          <p className="text-[13px] font-semibold text-emerald-900">Research complete</p>
          <p className="text-[11px] text-emerald-700 mt-0.5">
            {sourced} item{sourced !== 1 ? 's' : ''} sourced
            {needsInput > 0 ? `, ${needsInput} need manual input` : ''}
            {' · '}{totalQuotes} supplier quote{totalQuotes !== 1 ? 's' : ''} captured
            {avgPrice !== null ? ` · avg $${avgPrice.toFixed(2)}/unit` : ''}
          </p>
        </div>
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function BomLivePanel({ runId, initialRun, onClose }: Props) {
  const apiFetch = useApiClient();
  const [run, setRun] = useState<BomResearchRun | null>(initialRun ?? null);
  const [seenLogCount, setSeenLogCount] = useState(0);
  const [activeSection, setActiveSection] = useState<'feed' | 'items'>('feed');
  const logEndRef = useRef<HTMLDivElement>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const isActive = (s?: BomResearchRun['status']) =>
    s === 'researching' || s === 'generating_report';

  const fetchRun = useCallback(async () => {
    try {
      const res = await apiFetch(`/api/bom/runs/${runId}/`);
      if (!res.ok) return;
      const data: BomResearchRun = await res.json();
      setRun(data);
    } catch {
      // silently ignore transient errors
    }
  }, [apiFetch, runId]);

  // Start polling
  useEffect(() => {
    fetchRun();
    intervalRef.current = setInterval(fetchRun, 1500);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchRun]);

  // Stop polling when done
  useEffect(() => {
    if (run && !isActive(run.status)) {
      if (intervalRef.current) clearInterval(intervalRef.current);
    }
  }, [run]);

  // Auto-scroll feed + track "new" entries
  const logs: LogEntry[] = (run?.research_log ?? []) as LogEntry[];
  useEffect(() => {
    if (logs.length > seenLogCount) {
      setSeenLogCount(logs.length);
      // Switch to feed tab when new entries arrive during research
      if (run && isActive(run.status)) setActiveSection('feed');
    }
  }, [logs.length]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (activeSection === 'feed') {
      logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs.length, activeSection]);

  const items = run?.line_items ?? [];
  const resultsJson = (run?.results_json ?? {}) as Record<string, unknown>;

  return (
    <>
      {/* Keyframe for new log entries */}
      <style>{`
        @keyframes fadeSlideIn {
          from { opacity: 0; transform: translateY(4px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>

      <div className="fixed inset-0 z-40 flex items-stretch justify-end">
        {/* Backdrop */}
        <div className="flex-1 bg-black/20" onClick={onClose} />

        {/* Panel */}
        <div className="w-full max-w-xl bg-white flex flex-col h-full shadow-2xl">

          {/* ── Aurora header ──────────────────────────────────────────────── */}
          <div className="relative overflow-hidden flex-shrink-0" style={{
            background: 'linear-gradient(135deg, #0C0C1E 0%, #130F2B 45%, #0A1628 100%)',
            minHeight: '120px',
          }}>
            {/* Glow blobs */}
            <div className="absolute pointer-events-none" style={{
              top: '-20px', left: '5%', width: '200px', height: '200px',
              background: 'radial-gradient(circle, rgba(124,58,237,0.3), transparent 70%)',
              filter: 'blur(30px)',
            }} />
            <div className="absolute pointer-events-none" style={{
              top: '-10px', right: '10%', width: '140px', height: '140px',
              background: 'radial-gradient(circle, rgba(37,99,235,0.2), transparent 70%)',
              filter: 'blur(22px)',
            }} />
            {/* Dot grid */}
            <div className="absolute inset-0 pointer-events-none" style={{
              backgroundImage: 'radial-gradient(circle, rgba(255,255,255,0.04) 1px, transparent 1px)',
              backgroundSize: '22px 22px',
            }} />

            <div className="relative px-6 py-5 flex items-start justify-between">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1.5">
                  {/* Agent icon */}
                  <div className="relative">
                    <div className="absolute inset-0 rounded-xl opacity-60" style={{
                      background: 'linear-gradient(135deg, #8B5CF6, #6366F1)',
                      filter: 'blur(6px)',
                    }} />
                    <div className="relative w-7 h-7 rounded-xl flex items-center justify-center" style={{
                      background: 'linear-gradient(135deg, #8B5CF6 0%, #6366F1 100%)',
                    }}>
                      <BarChart3 className="w-4 h-4 text-white" strokeWidth={2} />
                    </div>
                  </div>
                  <div>
                    <p className="text-[11px] font-bold text-white tracking-widest uppercase leading-none">BOM Research Agent</p>
                    <p className="text-[10px] font-mono mt-0.5" style={{ color: 'rgba(255,255,255,0.3)' }}>
                      run #{runId} · claude-sonnet-4-6
                    </p>
                  </div>
                </div>

                {run && (
                  <div className="mt-2">
                    <RunStatusBadge status={run.status} />
                  </div>
                )}

                {/* Live stats row */}
                <div className="flex items-center gap-4 mt-3">
                  <div>
                    <p className="text-[9px] font-medium uppercase tracking-widest" style={{ color: 'rgba(255,255,255,0.3)' }}>Parts</p>
                    <p className="text-[13px] font-bold text-white tabular-nums">{items.length}</p>
                  </div>
                  <div>
                    <p className="text-[9px] font-medium uppercase tracking-widest" style={{ color: 'rgba(255,255,255,0.3)' }}>Sourced</p>
                    <p className="text-[13px] font-bold text-emerald-300 tabular-nums">
                      {items.filter((i) => i.status === 'sourced').length}
                    </p>
                  </div>
                  <div>
                    <p className="text-[9px] font-medium uppercase tracking-widest" style={{ color: 'rgba(255,255,255,0.3)' }}>Quotes</p>
                    <p className="text-[13px] font-bold text-white tabular-nums">
                      {items.reduce((s, i) => s + i.quotes.length, 0)}
                    </p>
                  </div>
                  <div>
                    <p className="text-[9px] font-medium uppercase tracking-widest" style={{ color: 'rgba(255,255,255,0.3)' }}>Log entries</p>
                    <p className="text-[13px] font-bold text-white tabular-nums">{logs.length}</p>
                  </div>
                </div>
              </div>

              <button
                onClick={onClose}
                className="flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-lg transition-colors ml-3"
                style={{ background: 'rgba(255,255,255,0.08)' }}
              >
                <X className="w-4 h-4 text-white/60" />
              </button>
            </div>

            {/* Tab bar */}
            <div className="flex border-t px-6" style={{ borderColor: 'rgba(255,255,255,0.08)' }}>
              {(['feed', 'items'] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveSection(tab)}
                  className="px-3 py-2.5 text-[11px] font-semibold uppercase tracking-wider transition-colors border-b-2"
                  style={{
                    color: activeSection === tab ? 'rgba(255,255,255,0.9)' : 'rgba(255,255,255,0.35)',
                    borderColor: activeSection === tab ? '#8B5CF6' : 'transparent',
                  }}
                >
                  {tab === 'feed' ? `Activity Feed (${logs.length})` : `Line Items (${items.length})`}
                </button>
              ))}
            </div>
          </div>

          {/* ── Body ────────────────────────────────────────────────────────── */}
          <div className="flex-1 overflow-hidden flex flex-col">

            {/* ── FEED TAB ──────────────────────────────────────────────────── */}
            {activeSection === 'feed' && (
              <div className="flex-1 overflow-y-auto" style={{
                background: '#0D0D1A',
                fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
              }}>
                <div className="px-5 py-4 space-y-0.5 min-h-full">
                  {logs.length === 0 && (
                    <div className="flex flex-col items-center justify-center py-20 text-center">
                      <Loader2 className="w-6 h-6 text-slate-500 animate-spin mb-3" />
                      <p className="text-[12px] text-slate-500">Waiting for agent to start…</p>
                    </div>
                  )}

                  {logs.map((entry, i) => (
                    <LogRow
                      key={i}
                      entry={entry}
                      isNew={i >= seenLogCount - (logs.length - seenLogCount) && i >= logs.length - 5}
                    />
                  ))}

                  {/* Blinking cursor when active */}
                  {run && isActive(run.status) && (
                    <div className="flex items-center gap-2 pt-1">
                      <span
                        className="inline-block w-2 h-3 bg-violet-400 rounded-[1px]"
                        style={{ animation: 'blink 1s step-start infinite' }}
                      />
                    </div>
                  )}

                  <div ref={logEndRef} />
                </div>
              </div>
            )}

            {/* ── ITEMS TAB ─────────────────────────────────────────────────── */}
            {activeSection === 'items' && (
              <div className="flex-1 overflow-y-auto px-5 py-5 bg-[#F7F7F7] space-y-3">
                {run?.status === 'completed' && <CompletionBanner run={run} />}

                {items.length === 0 && (
                  <div className="flex flex-col items-center justify-center py-20 text-center">
                    <Package className="w-8 h-8 text-[#D1D5DB] mb-3" />
                    <p className="text-[13px] text-[#9CA3AF]">No line items yet</p>
                  </div>
                )}

                {items.map((item) => (
                  <LineItemCard key={item.id} item={item} resultsJson={resultsJson} />
                ))}
              </div>
            )}
          </div>

          {/* ── Footer ──────────────────────────────────────────────────────── */}
          <div className="flex-shrink-0 px-5 py-3 border-t border-[#E6E6E6] bg-white flex items-center justify-between">
            <p className="text-[11px] text-[#9CA3AF]">
              {run && isActive(run.status) ? 'Live · updating every 1.5 s' : 'Polling stopped'}
            </p>
            <button
              onClick={() => setActiveSection(activeSection === 'feed' ? 'items' : 'feed')}
              className="text-[11px] text-[#6B7280] hover:text-[#111111] underline underline-offset-2 transition-colors"
            >
              Switch to {activeSection === 'feed' ? 'line items' : 'activity feed'}
            </button>
          </div>
        </div>
      </div>

      {/* Blink keyframe */}
      <style>{`@keyframes blink { 50% { opacity: 0; } }`}</style>
    </>
  );
}
