/**
 * BomLivePanel — real-time agent activity visualizer.
 *
 * "Old paper notebook" aesthetic: warm parchment, sepia ink, ruled paper,
 * stamp-style status badge, Fraunces title, typewriter log entries.
 *
 * Polls GET /api/bom/runs/<id>/log/?since=<ts> every 3 s while active,
 * accumulates entries incrementally, and stops when status is
 * "completed" or "failed". Also polls run detail every 3 s.
 */

import { useEffect, useRef, useState } from 'react';
import {
  X,
  Search,
  Wrench,
  DollarSign,
  AlertTriangle,
  Sparkles,
  BookOpen,
  Mail,
  Info,
  AlertCircle,
  CheckCircle2,
  Loader2,
  ChevronDown,
  ChevronUp,
  Package,
  Feather,
  Minimize2,
  Maximize2,
} from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { useApiClient } from '../../api/client';
import type { BomResearchRun, BomLineItem, BomLogEntry, BomLogResponse } from '../../api/types';

// ── Paper palette ─────────────────────────────────────────────────────────────

const PAPER = {
  base:       '#F3E7CE', // warm aged paper
  highlight:  '#F8F0DC', // lighter patch
  fold:       '#E8D6AC', // darker shadow at edges
  rule:       'rgba(61, 47, 31, 0.10)', // ruled-paper horizontal lines
  margin:     '#B63F2A', // red ink margin rule
  ink:        '#3D2F1F', // primary sepia ink
  inkSoft:    '#6B5A3F', // secondary ink
  inkFaded:   '#9E8F76', // tertiary ink
  stamp:      '#B63F2A', // red stamp
  sage:       '#5E7E52', // completed
  honey:      '#C28A3C', // highlight
  terracotta: '#C66A4E',
};

// ── Types ─────────────────────────────────────────────────────────────────────

interface Props {
  runId: number;
  initialRun?: BomResearchRun;
  onClose: () => void;
}

// ── Log entry config (sepia on cream) ────────────────────────────────────────

interface LogConfig {
  Icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  swatch: string;  // pigment color for the dot + icon
  label: string;
}

const LOG_CONFIG: Record<string, LogConfig> = {
  search:   { Icon: Search,        swatch: '#5B6FA3', label: 'SEARCH'   }, // ink blue
  material: { Icon: Wrench,        swatch: '#7B5E9B', label: 'MATERIAL' }, // violet ink
  quote:    { Icon: DollarSign,    swatch: '#5E7E52', label: 'QUOTE'    }, // sage green
  risk:     { Icon: AlertTriangle, swatch: '#C28A3C', label: 'RISK'     }, // honey amber
  summary:  { Icon: Sparkles,      swatch: '#8B6E3C', label: 'SUMMARY'  }, // gold ink
  library:  { Icon: BookOpen,      swatch: '#4D7472', label: 'LIBRARY'  }, // teal ink
  email:    { Icon: Mail,          swatch: '#6B5A3F', label: 'EMAIL'    }, // sepia
  info:     { Icon: Info,          swatch: '#6B5A3F', label: 'INFO'     }, // sepia
  warn:     { Icon: AlertTriangle, swatch: '#B67A2B', label: 'WARN'     }, // amber ink
  error:    { Icon: AlertCircle,   swatch: '#B63F2A', label: 'ERROR'    }, // red stamp
};

const DEFAULT_LOG_CONFIG: LogConfig = {
  Icon: Info, swatch: '#6B5A3F', label: 'LOG',
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function isActive(s: BomResearchRun['status']): boolean {
  return s === 'researching' || s === 'generating_report';
}

function isDone(s: BomResearchRun['status'] | undefined): boolean {
  return s === 'completed' || s === 'failed';
}

// ── Paper texture (SVG noise) ─────────────────────────────────────────────────

function PaperNoise({ opacity = 0.08 }: { opacity?: number }) {
  // SVG fractal-noise — gives a subtle fiber / grain feel to the paper.
  const svg = `
    <svg xmlns='http://www.w3.org/2000/svg' width='180' height='180' viewBox='0 0 180 180'>
      <filter id='n'>
        <feTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2' stitchTiles='stitch'/>
        <feColorMatrix values='0 0 0 0 0.24   0 0 0 0 0.18   0 0 0 0 0.12   0 0 0 0.55 0'/>
      </filter>
      <rect width='100%' height='100%' filter='url(%23n)' opacity='${opacity}'/>
    </svg>`;
  const encoded = encodeURIComponent(svg).replace(/#/g, '%23');
  return (
    <div
      aria-hidden="true"
      className="absolute inset-0 pointer-events-none"
      style={{ backgroundImage: `url("data:image/svg+xml,${encoded}")`, mixBlendMode: 'multiply' }}
    />
  );
}

function RuledLines() {
  // Horizontal ruled-paper lines, 28px apart.
  return (
    <div
      aria-hidden="true"
      className="absolute inset-0 pointer-events-none"
      style={{
        backgroundImage: `linear-gradient(to bottom, transparent 27px, ${PAPER.rule} 27px, ${PAPER.rule} 28px)`,
        backgroundSize: '100% 28px',
      }}
    />
  );
}

// Hand-drawn squiggle underline (same style as PageTitle)
function Squiggle({ color = PAPER.stamp, width = 150 }: { color?: string; width?: number }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 220 12"
      className="-rotate-[0.6deg] block"
      style={{ width, height: 9 }}
      fill="none"
      preserveAspectRatio="none"
    >
      <path
        d="M2 7 Q 22 2, 44 6 T 88 5 Q 112 9, 136 4 T 180 6 Q 200 3, 218 7"
        stroke={color}
        strokeWidth="1.75"
        strokeLinecap="round"
      />
    </svg>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function RunStatusStamp({ status }: { status: BomResearchRun['status'] }) {
  const cfgMap: Record<string, { color: string; label: string; spin: boolean; rotate: number }> = {
    gathering_inputs:    { color: PAPER.inkSoft,    label: 'Gathering inputs',    spin: false, rotate: -2 },
    researching:         { color: '#5B6FA3',        label: 'Researching',         spin: true,  rotate: -1.5 },
    generating_report:   { color: '#7B5E9B',        label: 'Generating report',   spin: true,  rotate: -2 },
    awaiting_team_input: { color: PAPER.honey,      label: 'Awaiting input',      spin: false, rotate: -1 },
    completed:           { color: PAPER.sage,       label: 'Completed',           spin: false, rotate: -2.5 },
    failed:              { color: PAPER.stamp,      label: 'Failed',              spin: false, rotate: -2 },
  };
  const cfg = cfgMap[status] ?? cfgMap['gathering_inputs'];
  return (
    <span
      className="inline-flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-display font-medium tracking-wider uppercase"
      style={{
        color: cfg.color,
        border: `1.5px solid ${cfg.color}`,
        borderRadius: '4px',
        transform: `rotate(${cfg.rotate}deg)`,
        boxShadow: `inset 0 0 0 1px ${PAPER.base}`,
        letterSpacing: '0.12em',
        background: 'transparent',
      }}
    >
      {cfg.spin
        ? <Loader2 className="w-3 h-3 animate-spin" style={{ color: cfg.color }} />
        : <span className="inline-block w-1.5 h-1.5 rounded-full" style={{ background: cfg.color }} />}
      {cfg.label}
    </span>
  );
}

function LineItemCard({ item, resultsJson }: { item: BomLineItem; resultsJson: Record<string, unknown> }) {
  const [open, setOpen] = useState(false);
  const result = (resultsJson[`item_${item.id}`] ?? {}) as Record<string, unknown>;
  const riskFlags = (result.risk_flags ?? []) as string[];
  const summary = result.summary as string | undefined;

  const statusCfg: Record<string, { color: string; label: string; spin: boolean }> = {
    pending:     { color: PAPER.inkFaded, label: 'Pending',     spin: false },
    researching: { color: '#5B6FA3',      label: 'Researching', spin: true  },
    sourced:     { color: PAPER.sage,     label: 'Sourced',     spin: false },
    needs_input: { color: PAPER.honey,    label: 'Needs input', spin: false },
  };
  const sc = statusCfg[item.status] ?? statusCfg['pending'];

  return (
    <div
      className="overflow-hidden rounded-[10px]"
      style={{
        background: PAPER.highlight,
        border: `1px solid ${PAPER.fold}`,
        boxShadow: '0 1px 0 rgba(61, 47, 31, 0.04), 0 2px 8px rgba(61, 47, 31, 0.06)',
      }}
    >
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-start gap-3 p-3.5 text-left transition-colors"
        style={{ background: 'transparent' }}
      >
        <div
          className="w-8 h-8 rounded-[6px] flex items-center justify-center flex-shrink-0 mt-0.5 rotate-[-2deg]"
          style={{ background: PAPER.base, border: `1px solid ${PAPER.fold}` }}
        >
          <Package className="w-4 h-4" strokeWidth={1.5} style={{ color: PAPER.inkSoft }} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="font-display text-[15px] font-medium truncate leading-tight" style={{ color: PAPER.ink }}>{item.part_name}</p>
            {item.part_number && (
              <span className="text-[10px] font-mono" style={{ color: PAPER.inkFaded }}>№ {item.part_number}</span>
            )}
          </div>
          {item.material_spec && (
            <p className="text-[11px] mt-0.5 italic" style={{ color: PAPER.inkSoft }}>{item.material_spec}</p>
          )}
          <div className="flex items-center gap-2 mt-1.5 flex-wrap">
            <span
              className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-display font-medium uppercase tracking-wider"
              style={{ color: sc.color, border: `1px solid ${sc.color}`, borderRadius: '3px', letterSpacing: '0.1em' }}
            >
              {sc.spin && <Loader2 className="w-2.5 h-2.5 animate-spin" />}
              {sc.label}
            </span>
            {item.quotes.length > 0 && (
              <span className="text-[11px] italic" style={{ color: PAPER.inkSoft }}>
                {item.quotes.length} quote{item.quotes.length !== 1 ? 's' : ''}
              </span>
            )}
            {riskFlags.length > 0 && (
              <span className="text-[10px] font-medium" style={{ color: PAPER.honey }}>
                ⚠ {riskFlags.length} risk{riskFlags.length !== 1 ? 's' : ''}
              </span>
            )}
          </div>
        </div>
        <div className="flex-shrink-0 mt-1" style={{ color: PAPER.inkFaded }}>
          {open ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </div>
      </button>

      {open && (
        <div className="border-t px-3.5 py-3 space-y-3" style={{ borderColor: PAPER.fold, background: PAPER.base }}>
          {item.quotes.length > 0 && (
            <div>
              <p className="font-display text-[11px] uppercase tracking-widest mb-2" style={{ color: PAPER.stamp, letterSpacing: '0.18em' }}>
                Supplier Quotes
              </p>
              <div className="space-y-1.5">
                {item.quotes.map((q) => (
                  <div
                    key={q.id}
                    className="rounded-[6px] px-3 py-2"
                    style={{ background: PAPER.highlight, border: `1px solid ${PAPER.fold}` }}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-display text-[13px] font-medium" style={{ color: PAPER.ink }}>{q.supplier_name}</span>
                      <span className="font-mono text-[13px] font-semibold" style={{ color: PAPER.sage }}>${Number(q.unit_price).toFixed(2)}</span>
                    </div>
                    <div className="flex items-center gap-3 mt-0.5 text-[11px] italic" style={{ color: PAPER.inkSoft }}>
                      <span>MOQ {q.moq}</span>
                      <span>·</span>
                      <span>{q.lead_time_days}d lead</span>
                      {Number(q.tooling_cost) > 0 && (
                        <>
                          <span>·</span>
                          <span>tooling ${Number(q.tooling_cost).toFixed(0)}</span>
                        </>
                      )}
                    </div>
                    {q.notes && <p className="text-[11px] mt-1 leading-snug italic" style={{ color: PAPER.inkSoft }}>{q.notes}</p>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {riskFlags.length > 0 && (
            <div>
              <p className="font-display text-[11px] uppercase tracking-widest mb-1.5" style={{ color: PAPER.stamp, letterSpacing: '0.18em' }}>
                Risk Flags
              </p>
              <div className="flex flex-wrap gap-1.5">
                {riskFlags.map((f) => (
                  <span
                    key={f}
                    className="px-2 py-0.5 text-[10px] font-medium"
                    style={{
                      color: PAPER.honey,
                      border: `1px solid ${PAPER.honey}`,
                      borderRadius: '3px',
                      background: 'rgba(194, 138, 60, 0.08)',
                    }}
                  >
                    {f.replace(/-/g, ' ')}
                  </span>
                ))}
              </div>
            </div>
          )}

          {summary && (
            <div>
              <p className="font-display text-[11px] uppercase tracking-widest mb-1.5" style={{ color: PAPER.stamp, letterSpacing: '0.18em' }}>
                Summary
              </p>
              <p className="text-[12px] leading-relaxed" style={{ color: PAPER.ink }}>{summary}</p>
            </div>
          )}

          {!item.quotes.length && !summary && (
            <p className="text-[12px] italic" style={{ color: PAPER.inkFaded }}>No notes yet…</p>
          )}
        </div>
      )}
    </div>
  );
}

function LogRow({ entry }: { entry: BomLogEntry }) {
  const cfg = LOG_CONFIG[entry.type] ?? DEFAULT_LOG_CONFIG;
  const { Icon, swatch, label } = cfg;
  return (
    <div
      className="flex items-start gap-3 py-[5px] pl-4 pr-3 animate-[fadeSlideIn_0.25s_ease_forwards]"
      style={{ position: 'relative' }}
    >
      <span
        className="flex-shrink-0 mt-[2px] text-[9px] font-mono tabular-nums uppercase tracking-wider"
        style={{ color: PAPER.inkFaded, letterSpacing: '0.08em', width: 58 }}
      >
        {entry.ts}
      </span>
      <Icon className="w-3 h-3 flex-shrink-0 mt-[3px]" style={{ color: swatch }} />
      <span
        className="flex-shrink-0 text-[9px] font-display font-medium uppercase tracking-wider mt-[2px]"
        style={{ color: swatch, width: 60, letterSpacing: '0.14em' }}
      >
        {label}
      </span>
      <span
        className="flex-1 min-w-0 text-[12px] leading-[1.55] break-words"
        style={{ color: PAPER.ink, fontFamily: "'JetBrains Mono', ui-monospace, monospace" }}
      >
        {entry.message}
      </span>
    </div>
  );
}

function CompletionBanner({ run }: { run: BomResearchRun }) {
  const allPrices = run.line_items.flatMap((i) => i.quotes.map((q) => Number(q.unit_price)));
  const avgPrice = allPrices.length ? allPrices.reduce((a, b) => a + b, 0) / allPrices.length : null;
  const sourced = run.line_items.filter((i) => i.status === 'sourced').length;
  const needsInput = run.line_items.filter((i) => i.status === 'needs_input').length;
  const totalQuotes = run.line_items.reduce((s, i) => s + i.quotes.length, 0);
  return (
    <div
      className="mb-4 rounded-[10px] relative overflow-hidden"
      style={{
        background: 'rgba(94, 126, 82, 0.08)',
        border: `1.5px solid ${PAPER.sage}`,
      }}
    >
      <div className="px-4 py-3 flex items-start gap-3">
        <CheckCircle2 className="w-5 h-5 flex-shrink-0 mt-0.5" style={{ color: PAPER.sage }} />
        <div>
          <p className="font-display text-[14px] font-medium" style={{ color: PAPER.ink }}>Research complete</p>
          <p className="text-[11px] italic mt-0.5" style={{ color: PAPER.inkSoft }}>
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
  const [activeSection, setActiveSection] = useState<'feed' | 'items'>('feed');
  const [collapsed, setCollapsed] = useState(false);
  const logEndRef = useRef<HTMLDivElement>(null);
  // Track the ts of the last received entry so we only fetch new ones
  const sinceRef = useRef<string>('');
  const logEntriesRef = useRef<BomLogEntry[]>([]);

  // ── Log polling (incremental, 3 s) ──────────────────────────────────────────
  const { data: logData } = useQuery<BomLogResponse & { entries: BomLogEntry[] }>({
    queryKey: ['bom-log', runId],
    queryFn: async () => {
      const since = sinceRef.current ? `?since=${sinceRef.current}` : '';
      const res = await apiFetch(`/api/bom/runs/${runId}/log/${since}`);
      if (!res.ok) throw new Error(`${res.status}`);
      const payload = (await res.json()) as BomLogResponse;
      if (payload.entries.length > 0) {
        logEntriesRef.current = [...logEntriesRef.current, ...payload.entries];
        sinceRef.current = payload.entries[payload.entries.length - 1].ts;
      }
      return { ...payload, entries: logEntriesRef.current };
    },
    refetchInterval: (query) => {
      const status = (query.state.data as BomLogResponse | undefined)?.status ?? initialRun?.status;
      return isDone(status) ? false : 3000;
    },
  });

  // ── Run detail polling (line items + results, 3 s) ───────────────────────────
  const { data: run } = useQuery<BomResearchRun>({
    queryKey: ['bom-run', runId],
    queryFn: async () => {
      const res = await apiFetch(`/api/bom/runs/${runId}/`);
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
    initialData: initialRun,
    refetchInterval: (query) => {
      const status = (query.state.data as BomResearchRun | undefined)?.status ?? logData?.status ?? initialRun?.status;
      return isDone(status) ? false : 3000;
    },
  });

  const items = run?.line_items ?? [];
  const resultsJson = (run?.results_json ?? {}) as Record<string, unknown>;
  const runStatus = run?.status ?? logData?.status ?? initialRun?.status;
  const logEntries = logData?.entries ?? [];

  // Auto-scroll feed when new entries arrive
  useEffect(() => {
    if (!collapsed) {
      logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logEntries.length, collapsed]);

  // ── Collapsed view ──────────────────────────────────────────────────────────
  if (collapsed) {
    return (
      <div className="fixed bottom-4 right-4 z-50">
        <div
          className="flex items-center gap-3 px-4 py-3 cursor-pointer relative overflow-hidden"
          style={{
            background: PAPER.base,
            border: `1.5px solid ${PAPER.fold}`,
            borderRadius: '10px',
            minWidth: '280px',
            boxShadow: '0 6px 22px rgba(61, 47, 31, 0.18), 0 1px 0 rgba(255,255,255,0.4) inset',
            transform: 'rotate(-0.5deg)',
          }}
          onClick={() => setCollapsed(false)}
        >
          <PaperNoise opacity={0.1} />
          <div
            className="relative w-7 h-7 rounded-[6px] flex items-center justify-center flex-shrink-0 rotate-[-4deg]"
            style={{ background: PAPER.ink }}
          >
            <Feather className="w-3.5 h-3.5" strokeWidth={1.5} style={{ color: PAPER.base }} />
          </div>
          <div className="flex-1 min-w-0 relative">
            <p className="font-display text-[14px] font-medium truncate leading-tight" style={{ color: PAPER.ink }}>
              BOM Notebook
            </p>
            {runStatus && (
              <div className="mt-1">
                <RunStatusStamp status={runStatus} />
              </div>
            )}
          </div>
          <div className="flex items-center gap-1 flex-shrink-0 relative">
            <button
              onClick={(e) => { e.stopPropagation(); setCollapsed(false); }}
              className="w-7 h-7 flex items-center justify-center rounded-[5px] hover:bg-black/5 transition-colors"
              title="Expand"
            >
              <Maximize2 className="w-3.5 h-3.5" style={{ color: PAPER.inkSoft }} />
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); onClose(); }}
              className="w-7 h-7 flex items-center justify-center rounded-[5px] hover:bg-black/5 transition-colors"
              title="Close"
            >
              <X className="w-3.5 h-3.5" style={{ color: PAPER.inkSoft }} />
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ── Expanded view ───────────────────────────────────────────────────────────
  const parts = items.length;
  const sourced = items.filter((i) => i.status === 'sourced').length;
  const quoteCount = items.reduce((s, i) => s + i.quotes.length, 0);

  return (
    <>
      <style>{`
        @keyframes fadeSlideIn { from { opacity:0; transform:translateY(3px); } to { opacity:1; transform:translateY(0); } }
        @keyframes blink { 50% { opacity:0; } }
        @keyframes inkDraw { from { stroke-dashoffset: 220; } to { stroke-dashoffset: 0; } }
      `}</style>

      <div className="fixed inset-0 z-40 flex items-stretch justify-end">
        <div className="flex-1" style={{ background: 'rgba(43, 40, 36, 0.25)' }} onClick={() => setCollapsed(true)} />

        <div
          className="w-full max-w-xl flex flex-col h-full relative overflow-hidden"
          style={{
            background: PAPER.base,
            boxShadow: '0 0 48px rgba(61, 47, 31, 0.28)',
            borderLeft: `1px solid ${PAPER.fold}`,
          }}
        >
          <PaperNoise opacity={0.08} />

          {/* Header — parchment title block */}
          <div className="relative flex-shrink-0" style={{ background: PAPER.highlight, borderBottom: `1px solid ${PAPER.fold}` }}>
            <PaperNoise opacity={0.06} />

            {/* Binding stitches — small decorative vertical dashes on left edge */}
            <div
              aria-hidden="true"
              className="absolute left-0 top-0 bottom-0 w-[12px] pointer-events-none"
              style={{
                backgroundImage: `repeating-linear-gradient(to bottom, transparent 0 10px, ${PAPER.stamp} 10px 14px, transparent 14px 24px)`,
                opacity: 0.5,
              }}
            />

            <div className="relative px-7 pt-5 pb-4 flex items-start justify-between">
              <div className="flex-1 min-w-0">
                {/* Eyebrow + title */}
                <p className="text-[10px] font-display uppercase tracking-[0.22em] mb-0.5" style={{ color: PAPER.stamp }}>
                  Research Notebook
                </p>
                <div className="flex items-baseline gap-2">
                  <h2 className="font-display text-[26px] leading-[1.1] tracking-tight" style={{ color: PAPER.ink, fontVariationSettings: "'opsz' 144" }}>
                    BOM Research
                  </h2>
                  <span className="font-display text-[18px] italic" style={{ color: PAPER.inkSoft }}>
                    №{runId}
                  </span>
                </div>
                <div className="mt-0.5">
                  <Squiggle color={PAPER.stamp} width={160} />
                </div>
                <p className="text-[10px] font-mono mt-1.5" style={{ color: PAPER.inkFaded }}>
                  claude-sonnet-4-6 · polling every 3 s
                </p>

                {runStatus && <div className="mt-3"><RunStatusStamp status={runStatus} /></div>}

                {/* Stats row — pen-drawn numerals */}
                <div className="flex items-baseline gap-5 mt-4">
                  {([
                    { label: 'Parts',   value: parts,      color: PAPER.ink },
                    { label: 'Sourced', value: sourced,    color: PAPER.sage },
                    { label: 'Quotes',  value: quoteCount, color: PAPER.ink },
                    { label: 'Entries', value: logEntries.length, color: PAPER.ink },
                  ] as const).flatMap(({ label, value, color }, i, arr) => {
                    const cells = [
                      <div key={label} className="flex flex-col items-start">
                        <span className="font-display text-[22px] leading-none tabular-nums" style={{ color }}>
                          {value}
                        </span>
                        <span className="text-[9px] uppercase tracking-[0.18em] mt-1 font-display" style={{ color: PAPER.inkFaded }}>
                          {label}
                        </span>
                      </div>,
                    ];
                    if (i < arr.length - 1) {
                      cells.push(
                        <span key={`sep-${label}`} className="w-px h-6 self-center" style={{ background: PAPER.fold }} />,
                      );
                    }
                    return cells;
                  })}
                </div>
              </div>

              <div className="flex items-center gap-1 flex-shrink-0">
                <button
                  onClick={() => setCollapsed(true)}
                  className="w-8 h-8 flex items-center justify-center rounded-[5px] hover:bg-black/5 transition-colors"
                  title="Minimize"
                >
                  <Minimize2 className="w-4 h-4" style={{ color: PAPER.inkSoft }} />
                </button>
                <button
                  onClick={onClose}
                  className="w-8 h-8 flex items-center justify-center rounded-[5px] hover:bg-black/5 transition-colors"
                  title="Close"
                >
                  <X className="w-4 h-4" style={{ color: PAPER.inkSoft }} />
                </button>
              </div>
            </div>

            {/* Tabs — fountain-pen underline */}
            <div className="flex relative px-7 gap-5" style={{ borderTop: `1px dashed ${PAPER.fold}` }}>
              {(['feed', 'items'] as const).map((tab) => {
                const active = activeSection === tab;
                return (
                  <button
                    key={tab}
                    onClick={() => setActiveSection(tab)}
                    className="relative pt-2.5 pb-2 text-[11px] font-display font-medium uppercase tracking-[0.18em] transition-colors"
                    style={{ color: active ? PAPER.ink : PAPER.inkFaded }}
                  >
                    {tab === 'feed' ? `Activity Feed (${logEntries.length})` : `Line Items (${parts})`}
                    {active && (
                      <svg
                        aria-hidden="true"
                        viewBox="0 0 220 12"
                        className="absolute left-0 right-0 bottom-0 w-full h-[7px]"
                        fill="none"
                        preserveAspectRatio="none"
                      >
                        <path
                          d="M2 7 Q 22 2, 44 6 T 88 5 Q 112 9, 136 4 T 180 6 Q 200 3, 218 7"
                          stroke={PAPER.stamp}
                          strokeWidth="2"
                          strokeLinecap="round"
                        />
                      </svg>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Feed tab — ruled paper with red margin */}
          {activeSection === 'feed' && (
            <div
              className="flex-1 overflow-y-auto relative"
              style={{ background: PAPER.base }}
            >
              <RuledLines />
              <PaperNoise opacity={0.09} />
              {/* Red vertical margin rule, notebook-style */}
              <div
                aria-hidden="true"
                className="absolute top-0 bottom-0 pointer-events-none"
                style={{
                  left: 68,
                  width: 1.5,
                  background: PAPER.margin,
                  opacity: 0.32,
                }}
              />

              <div className="relative px-2 py-4 min-h-full">
                {logEntries.length === 0 && (
                  <div className="flex flex-col items-center justify-center py-24 text-center">
                    <Feather className="w-6 h-6 mb-3 animate-pulse" style={{ color: PAPER.inkFaded }} />
                    <p className="font-display text-[13px] italic" style={{ color: PAPER.inkSoft }}>
                      Waiting for the agent to put pen to paper…
                    </p>
                  </div>
                )}
                {logEntries.map((entry, i) => (
                  <LogRow key={i} entry={entry} />
                ))}
                {runStatus && isActive(runStatus) && (
                  <div className="flex items-center gap-2 pl-4 pt-1">
                    <span
                      className="inline-block w-[7px] h-[14px]"
                      style={{ background: PAPER.ink, animation: 'blink 1s step-start infinite' }}
                    />
                  </div>
                )}
                <div ref={logEndRef} />
              </div>
            </div>
          )}

          {/* Items tab */}
          {activeSection === 'items' && (
            <div className="flex-1 overflow-y-auto px-5 py-5 space-y-3 relative" style={{ background: PAPER.base }}>
              <PaperNoise opacity={0.06} />
              <div className="relative space-y-3">
                {run?.status === 'completed' && <CompletionBanner run={run} />}
                {items.length === 0 && (
                  <div className="flex flex-col items-center justify-center py-20 text-center">
                    <Package className="w-8 h-8 mb-3" style={{ color: PAPER.inkFaded }} />
                    <p className="font-display text-[13px] italic" style={{ color: PAPER.inkSoft }}>No line items yet</p>
                  </div>
                )}
                {items.map((item) => (
                  <LineItemCard key={item.id} item={item} resultsJson={resultsJson} />
                ))}
              </div>
            </div>
          )}

          {/* Footer */}
          <div
            className="flex-shrink-0 px-6 py-3 flex items-center justify-between relative"
            style={{ background: PAPER.highlight, borderTop: `1px solid ${PAPER.fold}` }}
          >
            <p className="text-[11px] italic font-display" style={{ color: PAPER.inkSoft }}>
              {runStatus && isActive(runStatus) ? '⎯⎯ live — the agent writes ⎯⎯' : '⎯⎯ notebook closed ⎯⎯'}
            </p>
            <button
              onClick={() => setActiveSection(activeSection === 'feed' ? 'items' : 'feed')}
              className="text-[11px] font-display italic transition-colors"
              style={{ color: PAPER.stamp, textDecoration: 'underline', textDecorationStyle: 'dotted', textUnderlineOffset: '3px' }}
            >
              turn to {activeSection === 'feed' ? 'the line items' : 'the feed'}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
