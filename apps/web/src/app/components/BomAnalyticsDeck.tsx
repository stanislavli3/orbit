/**
 * BomAnalyticsDeck — the reusable consulting-deck chart surface.
 *
 * Pure presentational: give it a BomResearchRun, it produces the 4 KPIs,
 * 6 exhibits, and findings list. No routing, no data fetching.
 *
 * Used by BomAnalyticsPage (single run via /bom/:id/analytics) and
 * ProjectAnalyticsPage (via /project/:id/analytics).
 */

import { useMemo } from 'react';
import {
  Shield,
  Clock,
  DollarSign,
  AlertTriangle,
  CheckCircle2,
  Activity,
  Package,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Line,
  ComposedChart,
  ScatterChart,
  Scatter,
  ZAxis,
  ReferenceLine,
  Legend,
} from 'recharts';
import type { BomResearchRun, BomLineItem, SupplierQuote } from '../../api/types';

// ── Warm paper palette ───────────────────────────────────────────────────────
export const PAPER = {
  base:      '#FAF7F2',
  card:      '#FFFCF7',
  highlight: '#F8F0DC',
  fold:      '#E8D6AC',
  ink:       '#2B2824',
  inkSoft:   '#6B5A3F',
  inkFaded:  '#8B7F73',
  stamp:     '#C66A4E',
  sage:      '#5E7E52',
  honey:     '#D4A047',
  brick:     '#B63F2A',
  cobalt:    '#5B6FA3',
  plum:      '#7B5E9B',
  teal:      '#4D7472',
  clay:      '#A96F47',
};

// ── Helpers ───────────────────────────────────────────────────────────────────
function getBestQuote(item: BomLineItem): SupplierQuote | null {
  if (!item.quotes.length) return null;
  return [...item.quotes].sort((a, b) => {
    const aCost = Number(a.landed_cost_usd ?? a.unit_price);
    const bCost = Number(b.landed_cost_usd ?? b.unit_price);
    return aCost - bCost || a.lead_time_days - b.lead_time_days;
  })[0];
}

export function formatCurrency(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—';
  if (Math.abs(value) >= 10_000) {
    return `$${Math.round(value / 1000).toLocaleString()}k`;
  }
  return `$${value.toFixed(2)}`;
}

function percentOf(part: number, total: number): number {
  return total > 0 ? (part / total) * 100 : 0;
}

// ── Small building blocks ────────────────────────────────────────────────────

export function Squiggle({ color = PAPER.stamp, width = 150 }: { color?: string; width?: number }) {
  return (
    <svg viewBox="0 0 220 12" className="-rotate-[0.5deg] block" style={{ width, height: 9 }} fill="none" preserveAspectRatio="none">
      <path d="M2 7 Q 22 2, 44 6 T 88 5 Q 112 9, 136 4 T 180 6 Q 200 3, 218 7" stroke={color} strokeWidth="1.75" strokeLinecap="round" />
    </svg>
  );
}

function Exhibit({ index, title, kicker, children, className }: {
  index: number; title: string; kicker: string; children: React.ReactNode; className?: string;
}) {
  return (
    <div
      className={`rounded-[12px] p-5 relative flex flex-col ${className ?? ''}`}
      style={{
        background: PAPER.card,
        border: `1px solid ${PAPER.fold}`,
        boxShadow: '0 1px 0 rgba(61, 47, 31, 0.03), 0 6px 16px rgba(61, 47, 31, 0.05)',
      }}
    >
      <div className="mb-2">
        <p className="text-[10px] font-display uppercase tracking-[0.22em]" style={{ color: PAPER.stamp }}>Exhibit {index}</p>
        <h3 className="font-display text-[16px] leading-[1.2] font-medium mt-0.5" style={{ color: PAPER.ink }}>{title}</h3>
        <p className="text-[12px] italic mt-0.5" style={{ color: PAPER.inkSoft }}>
          <span className="font-display not-italic uppercase tracking-wider text-[10px]" style={{ color: PAPER.inkFaded }}>So what ·</span>{' '}
          {kicker}
        </p>
      </div>
      <div className="flex-1 min-h-0">{children}</div>
    </div>
  );
}

function KPI({ icon: Icon, label, value, sub, tone = 'neutral' }: {
  icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  label: string; value: React.ReactNode; sub?: string;
  tone?: 'neutral' | 'positive' | 'caution' | 'risk';
}) {
  const accent = tone === 'positive' ? PAPER.sage : tone === 'caution' ? PAPER.honey : tone === 'risk' ? PAPER.brick : PAPER.stamp;
  return (
    <div className="p-4 rounded-[10px] relative overflow-hidden" style={{ background: PAPER.card, border: `1px solid ${PAPER.fold}` }}>
      <div className="absolute top-0 left-0 right-0 h-[3px]" style={{ background: accent }} />
      <div className="flex items-center gap-2 mb-2">
        <Icon className="w-3.5 h-3.5" style={{ color: accent }} strokeWidth={1.75} />
        <span className="text-[10px] font-display uppercase tracking-[0.16em]" style={{ color: PAPER.inkFaded }}>{label}</span>
      </div>
      <div className="font-display text-[26px] leading-none font-medium tabular-nums" style={{ color: PAPER.ink }}>{value}</div>
      {sub && <p className="text-[11px] italic mt-1.5" style={{ color: PAPER.inkSoft }}>{sub}</p>}
    </div>
  );
}

function PaperTooltip({ active, payload, label }: {active?: boolean; payload?: {color?: string; name?: string; value?: number | string}[]; label?: string | number}) {
  if (!active || !payload || !payload.length) return null;
  return (
    <div className="px-2.5 py-1.5 rounded-[5px] text-[11px]" style={{ background: PAPER.card, border: `1px solid ${PAPER.fold}`, color: PAPER.ink, boxShadow: '0 2px 8px rgba(61, 47, 31, 0.1)' }}>
      {label != null && <p className="font-display font-medium mb-0.5" style={{ color: PAPER.ink }}>{String(label)}</p>}
      {payload.map((p, i) => (
        <div key={i} className="flex items-center gap-2">
          {p.color && <span className="w-2 h-2 rounded-sm" style={{ background: p.color }} />}
          <span style={{ color: PAPER.inkSoft }}>{p.name}:</span>
          <span className="font-mono tabular-nums" style={{ color: PAPER.ink }}>{String(p.value)}</span>
        </div>
      ))}
    </div>
  );
}

function EmptyChart() {
  return (
    <div className="w-full h-full flex flex-col items-center justify-center text-center py-8">
      <Activity className="w-6 h-6 mb-2" style={{ color: PAPER.inkFaded }} strokeWidth={1.5} />
      <p className="text-[11px] italic" style={{ color: PAPER.inkSoft }}>Not enough data yet.</p>
    </div>
  );
}

// ── The deck itself ──────────────────────────────────────────────────────────
export function BomAnalyticsDeck({ run }: { run: BomResearchRun }) {
  const analytics = useMemo(() => {
    const items = run.line_items ?? [];
    const rows = items.map((item) => {
      const best = getBestQuote(item);
      const unitCost = best ? Number(best.landed_cost_usd ?? best.unit_price) : null;
      const extended = unitCost != null ? unitCost * item.quantity : null;
      const resultsSection = ((run.results_json ?? {}) as Record<string, unknown>)[`item_${item.id}`] as Record<string, unknown> | undefined;
      const riskFlags = (resultsSection?.risk_flags as string[] | undefined) ?? [];
      return {
        item, best, unitCost, extended,
        supplier: best?.supplier_name ?? '—',
        leadTime: best?.lead_time_days ?? null,
        isAvl: best?.is_avl ?? false,
        riskFlags,
      };
    });

    const totalSpend = rows.reduce((sum, r) => sum + (r.extended ?? 0), 0);
    const sourcedCount = items.filter((i) => i.status === 'sourced').length;
    const needsInputCount = items.filter((i) => i.status === 'needs_input').length;
    const allQuotes = items.flatMap((i) => i.quotes);
    const totalQuotes = allQuotes.length;
    const avlSpend = rows.reduce((sum, r) => sum + (r.isAvl ? (r.extended ?? 0) : 0), 0);
    const avlCoverage = percentOf(avlSpend, totalSpend);
    const totalRiskFlags = rows.reduce((sum, r) => sum + r.riskFlags.length, 0);

    const spendByPart = [...rows]
      .filter((r) => r.extended != null)
      .sort((a, b) => (b.extended ?? 0) - (a.extended ?? 0))
      .slice(0, 10)
      .map((r) => ({
        name: r.item.part_name.length > 18 ? r.item.part_name.slice(0, 18) + '…' : r.item.part_name,
        fullName: r.item.part_name,
        cost: Math.round(r.extended ?? 0),
      }));

    const supplierSpend = new Map<string, number>();
    for (const r of rows) {
      if (r.extended != null && r.supplier && r.supplier !== '—') {
        supplierSpend.set(r.supplier, (supplierSpend.get(r.supplier) ?? 0) + r.extended);
      }
    }
    const supplierArr = [...supplierSpend.entries()].map(([name, spend]) => ({ name, spend })).sort((a, b) => b.spend - a.spend);
    let cum = 0;
    const supplierPareto = supplierArr.map((s) => {
      cum += s.spend;
      return {
        name: s.name.length > 14 ? s.name.slice(0, 14) + '…' : s.name,
        spend: Math.round(s.spend),
        cumPct: Math.round(percentOf(cum, totalSpend)),
      };
    });

    const nonAvlSpend = totalSpend - avlSpend;
    const avlDonut = [
      { name: 'AVL-approved', value: Math.round(avlSpend), color: PAPER.sage },
      { name: 'Non-AVL', value: Math.round(nonAvlSpend), color: PAPER.brick },
    ];

    const leadTimes = rows.map((r) => r.leadTime).filter((x): x is number => x != null);
    const leadBins = [
      { label: '0–14 d', min: 0, max: 14, count: 0 },
      { label: '15–30 d', min: 15, max: 30, count: 0 },
      { label: '31–60 d', min: 31, max: 60, count: 0 },
      { label: '61–90 d', min: 61, max: 90, count: 0 },
      { label: '> 90 d', min: 91, max: Number.POSITIVE_INFINITY, count: 0 },
    ];
    for (const t of leadTimes) {
      const bin = leadBins.find((b) => t >= b.min && t <= b.max);
      if (bin) bin.count += 1;
    }

    const costLeadPoints = rows
      .filter((r) => r.unitCost != null && r.leadTime != null)
      .map((r) => ({
        x: r.leadTime as number,
        y: r.unitCost as number,
        z: Math.max(r.item.quantity, 1) * 40,
        name: r.item.part_name,
        isAvl: r.isAvl,
      }));
    const medianCost = (() => {
      const vals = costLeadPoints.map((p) => p.y).sort((a, b) => a - b);
      return vals.length ? vals[Math.floor(vals.length / 2)] : 0;
    })();
    const medianLead = (() => {
      const vals = costLeadPoints.map((p) => p.x).sort((a, b) => a - b);
      return vals.length ? vals[Math.floor(vals.length / 2)] : 0;
    })();

    const riskCategories = [
      { key: 'single-source',            label: 'Single source',     color: PAPER.brick },
      { key: 'long-lead-time',           label: 'Long lead',         color: PAPER.honey },
      { key: 'compliance-gap',           label: 'Compliance gap',    color: PAPER.brick },
      { key: 'geographic-concentration', label: 'Geo concentration', color: PAPER.honey },
      { key: 'cost-outlier',             label: 'Cost outlier',      color: PAPER.brick },
    ];
    const riskHeatmap = rows.map((r) => ({
      name: r.item.part_name.length > 22 ? r.item.part_name.slice(0, 22) + '…' : r.item.part_name,
      cells: riskCategories.map((cat) => ({
        key: cat.key, label: cat.label, color: cat.color,
        active: r.riskFlags.includes(cat.key),
      })),
    }));

    const findings: { tone: 'positive' | 'caution' | 'risk'; title: string; body: string }[] = [];
    if (supplierPareto.length >= 3) {
      const top3Pct = supplierPareto[2]?.cumPct ?? 0;
      if (top3Pct >= 70) {
        findings.push({
          tone: 'risk',
          title: `Top 3 suppliers concentrate ${top3Pct}% of spend`,
          body: `Negotiating leverage is strong but single-point-of-failure risk is high. Qualify one backup supplier per top-3 category within the next 60 days.`,
        });
      }
    }
    if (avlCoverage < 50 && totalSpend > 0) {
      findings.push({
        tone: 'caution',
        title: `Only ${avlCoverage.toFixed(0)}% of spend flows to AVL-approved suppliers`,
        body: `Material variance, quality exposure, and audit risk all elevated. Route the largest non-AVL line items through supplier qualification before next PO.`,
      });
    } else if (avlCoverage >= 80 && totalSpend > 0) {
      findings.push({
        tone: 'positive',
        title: `${avlCoverage.toFixed(0)}% AVL coverage — supply base is healthy`,
        body: `Quality and compliance risk are mitigated. Focus remaining effort on the long-lead minority to compress time-to-market.`,
      });
    }
    if (leadBins.find((b) => b.label === '> 90 d' && b.count > 0)) {
      const count = leadBins.find((b) => b.label === '> 90 d')!.count;
      findings.push({
        tone: 'caution',
        title: `${count} part${count !== 1 ? 's' : ''} with lead time > 90 days`,
        body: `These line items will gate the assembly date. Consider dual-sourcing, air-freight, or in-house substitution.`,
      });
    }
    if (totalRiskFlags === 0 && totalQuotes > 0) {
      findings.push({
        tone: 'positive',
        title: `No risk flags raised across ${items.length} line item${items.length !== 1 ? 's' : ''}`,
        body: `Based on supplier coverage, lead times, and compliance signals, this BOM is investment-ready. Lock in quotes before market conditions shift.`,
      });
    }
    if (needsInputCount > 0) {
      findings.push({
        tone: 'risk',
        title: `${needsInputCount} line item${needsInputCount !== 1 ? 's' : ''} still need human clarification`,
        body: `Analytics below reflect sourced items only. Resolve the flagged questions to unlock full cost visibility.`,
      });
    }

    return {
      items, rows, totalSpend, sourcedCount, needsInputCount, totalQuotes, avlCoverage, totalRiskFlags,
      spendByPart, supplierPareto, avlDonut, leadBins, costLeadPoints, medianCost, medianLead,
      riskCategories, riskHeatmap, findings,
    };
  }, [run]);

  return (
    <>
      {/* Executive Summary */}
      <div className="p-6 mb-6 rounded-[14px] relative" style={{ background: PAPER.card, border: `1px solid ${PAPER.fold}`, boxShadow: '0 2px 14px rgba(61, 47, 31, 0.06)' }}>
        <p className="text-[10px] font-display uppercase tracking-[0.22em] mb-1" style={{ color: PAPER.stamp }}>Executive Summary</p>
        <h2 className="font-display text-[22px] leading-[1.2] mb-3" style={{ color: PAPER.ink }}>
          {analytics.totalQuotes === 0
            ? 'Research in progress — metrics will populate as quotes land.'
            : analytics.avlCoverage >= 80
              ? `A healthy supply base: ${analytics.avlCoverage.toFixed(0)}% of spend is AVL-approved across ${analytics.items.length} line item${analytics.items.length !== 1 ? 's' : ''}.`
              : analytics.avlCoverage >= 50
                ? `Mixed exposure: ${analytics.avlCoverage.toFixed(0)}% AVL coverage across ${formatCurrency(analytics.totalSpend)} of projected spend.`
                : `Concentrated risk: only ${analytics.avlCoverage.toFixed(0)}% of ${formatCurrency(analytics.totalSpend)} flows through approved suppliers.`}
        </h2>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <KPI icon={DollarSign} label="Total projected spend" value={formatCurrency(analytics.totalSpend)} sub={`${analytics.totalQuotes} quote${analytics.totalQuotes !== 1 ? 's' : ''} captured`} tone="neutral" />
          <KPI icon={CheckCircle2} label="Parts sourced" value={`${analytics.sourcedCount}/${analytics.items.length}`} sub={analytics.needsInputCount > 0 ? `${analytics.needsInputCount} need human input` : 'Full coverage'} tone={analytics.needsInputCount === 0 ? 'positive' : 'caution'} />
          <KPI icon={Shield} label="AVL coverage" value={`${analytics.avlCoverage.toFixed(0)}%`} sub="of projected spend" tone={analytics.avlCoverage >= 80 ? 'positive' : analytics.avlCoverage >= 50 ? 'caution' : 'risk'} />
          <KPI icon={AlertTriangle} label="Open risks" value={analytics.totalRiskFlags} sub={analytics.totalRiskFlags === 0 ? 'Clean profile' : 'Flagged across line items'} tone={analytics.totalRiskFlags === 0 ? 'positive' : 'risk'} />
        </div>
      </div>

      {/* Exhibits grid */}
      <div className="grid grid-cols-12 gap-5">
        <div className="col-span-12 lg:col-span-7">
          <Exhibit index={1} title="Spend composition — top 10 parts by extended cost"
            kicker={analytics.spendByPart.length > 0 ? `The top ${Math.min(3, analytics.spendByPart.length)} parts drive most of the bill; protect their supply continuity first.` : 'Not enough quote data yet to decompose spend.'}
            className="h-[360px]">
            {analytics.spendByPart.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={analytics.spendByPart} layout="vertical" margin={{ left: 8, right: 16, top: 8, bottom: 8 }}>
                  <CartesianGrid stroke={PAPER.fold} strokeDasharray="2 4" horizontal={false} />
                  <XAxis type="number" stroke={PAPER.inkFaded} tick={{ fontSize: 10, fill: PAPER.inkSoft }} tickFormatter={(v) => `$${v >= 1000 ? (v/1000).toFixed(0) + 'k' : v}`} />
                  <YAxis type="category" dataKey="name" stroke={PAPER.inkFaded} tick={{ fontSize: 10, fill: PAPER.ink }} width={120} />
                  <Tooltip content={<PaperTooltip />} cursor={{ fill: 'rgba(198, 106, 78, 0.08)' }} />
                  <Bar dataKey="cost" fill={PAPER.stamp} radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : <EmptyChart />}
          </Exhibit>
        </div>
        <div className="col-span-12 lg:col-span-5">
          <Exhibit index={2} title="Supply-base posture — AVL vs non-AVL"
            kicker={analytics.totalSpend > 0 ? (analytics.avlCoverage >= 80 ? `Approved-vendor coverage is strong. Quality and compliance risk is contained.` : `Non-AVL exposure is material. Qualify these suppliers before production PO.`) : 'Spend unknown — cannot assess posture.'}
            className="h-[360px]">
            {analytics.totalSpend > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={analytics.avlDonut} cx="50%" cy="50%" innerRadius={60} outerRadius={95} paddingAngle={2} dataKey="value" stroke={PAPER.card} strokeWidth={2}>
                    {analytics.avlDonut.map((entry, i) => (<Cell key={i} fill={entry.color} />))}
                  </Pie>
                  <Tooltip content={<PaperTooltip />} />
                  <Legend verticalAlign="bottom" iconType="square" formatter={(v) => <span style={{ fontSize: 11, color: PAPER.ink }}>{v}</span>} />
                </PieChart>
              </ResponsiveContainer>
            ) : <EmptyChart />}
          </Exhibit>
        </div>
        <div className="col-span-12 lg:col-span-7">
          <Exhibit index={3} title="Supplier Pareto — cumulative share of spend"
            kicker={analytics.supplierPareto.length > 0 ? `Top ${Math.min(3, analytics.supplierPareto.length)} suppliers carry ${analytics.supplierPareto[Math.min(2, analytics.supplierPareto.length - 1)]?.cumPct ?? 0}% of spend. Leverage is high; fragility is the mirror image.` : 'Not enough supplier-assigned quotes yet.'}
            className="h-[360px]">
            {analytics.supplierPareto.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={analytics.supplierPareto} margin={{ left: 8, right: 16, top: 12, bottom: 8 }}>
                  <CartesianGrid stroke={PAPER.fold} strokeDasharray="2 4" />
                  <XAxis dataKey="name" stroke={PAPER.inkFaded} tick={{ fontSize: 10, fill: PAPER.ink }} interval={0} angle={-15} textAnchor="end" height={52} />
                  <YAxis yAxisId="left" stroke={PAPER.inkFaded} tick={{ fontSize: 10, fill: PAPER.inkSoft }} tickFormatter={(v) => `$${v >= 1000 ? (v/1000).toFixed(0) + 'k' : v}`} />
                  <YAxis yAxisId="right" orientation="right" stroke={PAPER.inkFaded} tick={{ fontSize: 10, fill: PAPER.inkSoft }} tickFormatter={(v) => `${v}%`} domain={[0, 100]} />
                  <Tooltip content={<PaperTooltip />} />
                  <Bar yAxisId="left" dataKey="spend" fill={PAPER.cobalt} radius={[4, 4, 0, 0]} />
                  <Line yAxisId="right" dataKey="cumPct" type="monotone" stroke={PAPER.brick} strokeWidth={2} dot={{ r: 3, fill: PAPER.brick }} />
                  <ReferenceLine yAxisId="right" y={80} stroke={PAPER.honey} strokeDasharray="4 4" label={{ value: '80% threshold', position: 'insideTopRight', fontSize: 10, fill: PAPER.honey }} />
                </ComposedChart>
              </ResponsiveContainer>
            ) : <EmptyChart />}
          </Exhibit>
        </div>
        <div className="col-span-12 lg:col-span-5">
          <Exhibit index={4} title="Lead-time distribution"
            kicker={analytics.leadBins.find((b) => b.label === '> 90 d' && b.count > 0) ? `Long-lead items ( > 90 d ) will gate your assembly date — de-risk those first.` : `Lead times are well-contained; operational risk from delays is low.`}
            className="h-[360px]">
            {analytics.leadBins.some((b) => b.count > 0) ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={analytics.leadBins} margin={{ left: 8, right: 8, top: 8, bottom: 8 }}>
                  <CartesianGrid stroke={PAPER.fold} strokeDasharray="2 4" vertical={false} />
                  <XAxis dataKey="label" stroke={PAPER.inkFaded} tick={{ fontSize: 10, fill: PAPER.ink }} />
                  <YAxis stroke={PAPER.inkFaded} tick={{ fontSize: 10, fill: PAPER.inkSoft }} allowDecimals={false} />
                  <Tooltip content={<PaperTooltip />} cursor={{ fill: 'rgba(212, 160, 71, 0.08)' }} />
                  <Bar dataKey="count" fill={PAPER.honey} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : <EmptyChart />}
          </Exhibit>
        </div>
        <div className="col-span-12 lg:col-span-7">
          <Exhibit index={5} title="Cost × lead-time quadrants"
            kicker={`Upper-right parts are strategic (expensive + slow) — reserve them for dual-sourcing attention.`}
            className="h-[420px]">
            {analytics.costLeadPoints.length > 0 ? (
              <div className="relative w-full h-full">
                <ResponsiveContainer width="100%" height="100%">
                  <ScatterChart margin={{ left: 12, right: 12, top: 12, bottom: 24 }}>
                    <CartesianGrid stroke={PAPER.fold} strokeDasharray="2 4" />
                    <XAxis type="number" dataKey="x" name="Lead time" stroke={PAPER.inkFaded} tick={{ fontSize: 10, fill: PAPER.inkSoft }} label={{ value: 'Lead time (days) →', position: 'insideBottom', offset: -12, fontSize: 10, fill: PAPER.inkSoft }} />
                    <YAxis type="number" dataKey="y" name="Unit cost" stroke={PAPER.inkFaded} tick={{ fontSize: 10, fill: PAPER.inkSoft }} label={{ value: '↑ Unit cost ($)', angle: -90, position: 'insideLeft', fontSize: 10, fill: PAPER.inkSoft }} tickFormatter={(v) => `$${v >= 1000 ? (v/1000).toFixed(0) + 'k' : v.toFixed(0)}`} />
                    <ZAxis type="number" dataKey="z" range={[50, 400]} />
                    <Tooltip
                      content={({ active, payload }) => {
                        if (!active || !payload || !payload.length) return null;
                        const d = payload[0].payload as { name: string; x: number; y: number; isAvl: boolean };
                        return (
                          <div className="px-2.5 py-1.5 rounded-[5px] text-[11px]" style={{ background: PAPER.card, border: `1px solid ${PAPER.fold}`, color: PAPER.ink }}>
                            <p className="font-display font-medium mb-0.5">{d.name}</p>
                            <p className="font-mono tabular-nums" style={{ color: PAPER.inkSoft }}>{d.x}d · ${d.y.toFixed(2)}</p>
                            <p className="text-[10px] italic" style={{ color: d.isAvl ? PAPER.sage : PAPER.brick }}>{d.isAvl ? 'AVL' : 'Non-AVL'}</p>
                          </div>
                        );
                      }}
                    />
                    {analytics.medianLead > 0 && <ReferenceLine x={analytics.medianLead} stroke={PAPER.inkFaded} strokeDasharray="4 4" label={{ value: 'median lead', position: 'top', fontSize: 9, fill: PAPER.inkFaded }} />}
                    {analytics.medianCost > 0 && <ReferenceLine y={analytics.medianCost} stroke={PAPER.inkFaded} strokeDasharray="4 4" label={{ value: 'median cost', position: 'right', fontSize: 9, fill: PAPER.inkFaded }} />}
                    <Scatter data={analytics.costLeadPoints} fill={PAPER.stamp}>
                      {analytics.costLeadPoints.map((p, i) => (<Cell key={i} fill={p.isAvl ? PAPER.sage : PAPER.brick} />))}
                    </Scatter>
                  </ScatterChart>
                </ResponsiveContainer>
                <div className="absolute top-2 right-3 text-[10px] font-display uppercase tracking-[0.14em] italic" style={{ color: PAPER.inkFaded }}>Strategic</div>
                <div className="absolute top-2 left-12 text-[10px] font-display uppercase tracking-[0.14em] italic" style={{ color: PAPER.inkFaded }}>Bottleneck</div>
                <div className="absolute bottom-8 right-3 text-[10px] font-display uppercase tracking-[0.14em] italic" style={{ color: PAPER.inkFaded }}>Leverage</div>
                <div className="absolute bottom-8 left-12 text-[10px] font-display uppercase tracking-[0.14em] italic" style={{ color: PAPER.inkFaded }}>Commodity</div>
              </div>
            ) : <EmptyChart />}
          </Exhibit>
        </div>
        <div className="col-span-12 lg:col-span-5">
          <Exhibit index={6} title="Risk heatmap — part × category"
            kicker={analytics.totalRiskFlags === 0 ? 'No flagged risks — BOM is ready for approval.' : 'Each filled cell is a risk flag the agent raised during review.'}
            className="h-[420px]">
            {analytics.items.length > 0 ? (
              <div className="h-full overflow-auto">
                <table className="w-full text-[10px]" style={{ borderCollapse: 'separate', borderSpacing: 0 }}>
                  <thead>
                    <tr>
                      <th className="sticky top-0 text-left px-2 py-2 font-display uppercase tracking-[0.14em]" style={{ background: PAPER.card, color: PAPER.inkFaded, borderBottom: `1px solid ${PAPER.fold}` }}>Part</th>
                      {analytics.riskCategories.map((c) => (
                        <th key={c.key} className="sticky top-0 px-1 py-2 font-display uppercase tracking-[0.1em] text-center" style={{ background: PAPER.card, color: PAPER.inkFaded, borderBottom: `1px solid ${PAPER.fold}`, minWidth: 50 }}>
                          {c.label.split(' ').map((w, i) => <div key={i}>{w}</div>)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {analytics.riskHeatmap.map((row, i) => (
                      <tr key={i}>
                        <td className="px-2 py-1.5 text-left" style={{ color: PAPER.ink, borderBottom: `1px dashed ${PAPER.fold}` }}>{row.name}</td>
                        {row.cells.map((cell) => (
                          <td key={cell.key} className="p-1 text-center" style={{ borderBottom: `1px dashed ${PAPER.fold}` }}>
                            {cell.active ? (
                              <span className="inline-block w-6 h-5 rounded-[3px]" style={{ background: cell.color, boxShadow: `inset 0 0 0 1px ${PAPER.card}` }} title={cell.label} />
                            ) : (
                              <span className="inline-block w-6 h-5 rounded-[3px]" style={{ background: PAPER.fold, opacity: 0.2 }} />
                            )}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : <EmptyChart />}
          </Exhibit>
        </div>
      </div>

      {/* Findings */}
      <div className="mt-6 p-6 rounded-[14px] relative" style={{ background: PAPER.card, border: `1px solid ${PAPER.fold}`, boxShadow: '0 2px 14px rgba(61, 47, 31, 0.06)' }}>
        <p className="text-[10px] font-display uppercase tracking-[0.22em] mb-1" style={{ color: PAPER.stamp }}>Findings & recommendations</p>
        <h2 className="font-display text-[20px] leading-[1.2] mb-4" style={{ color: PAPER.ink }}>What we'd do next</h2>
        {analytics.findings.length === 0 ? (
          <p className="text-[13px] italic" style={{ color: PAPER.inkSoft }}>
            No material findings to surface yet. Metrics will firm up as the research completes.
          </p>
        ) : (
          <ol className="space-y-4">
            {analytics.findings.map((f, i) => {
              const accent = f.tone === 'positive' ? PAPER.sage : f.tone === 'caution' ? PAPER.honey : PAPER.brick;
              const Icon = f.tone === 'positive' ? CheckCircle2 : f.tone === 'caution' ? Clock : AlertTriangle;
              return (
                <li key={i} className="flex items-start gap-3 pb-4" style={{ borderBottom: i < analytics.findings.length - 1 ? `1px dashed ${PAPER.fold}` : 'none' }}>
                  <span className="font-display text-[18px] font-medium tabular-nums w-6 flex-shrink-0 leading-none mt-0.5" style={{ color: accent }}>{String(i + 1).padStart(2, '0')}</span>
                  <Icon className="w-4 h-4 flex-shrink-0 mt-0.5" style={{ color: accent }} strokeWidth={1.5} />
                  <div>
                    <p className="font-display text-[14px] font-medium" style={{ color: PAPER.ink }}>{f.title}</p>
                    <p className="text-[12px] mt-0.5 leading-relaxed" style={{ color: PAPER.inkSoft }}>{f.body}</p>
                  </div>
                </li>
              );
            })}
          </ol>
        )}
      </div>

      {/* Methodology footer */}
      <div className="mt-8 pt-6 flex items-start justify-between gap-6" style={{ borderTop: `1px dashed ${PAPER.fold}` }}>
        <div>
          <p className="text-[10px] font-display uppercase tracking-[0.22em]" style={{ color: PAPER.inkFaded }}>Methodology</p>
          <p className="text-[11px] italic mt-1 max-w-[640px]" style={{ color: PAPER.inkSoft }}>
            All metrics derived from agent-captured supplier quotes. Best quote = lowest landed cost, tie-broken on lead time. Extended cost = unit cost × quantity. Risk flags are agent-raised and rule-verified.
          </p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <Package className="w-3.5 h-3.5" style={{ color: PAPER.inkFaded }} strokeWidth={1.5} />
          <span className="text-[10px] font-display uppercase tracking-[0.18em]" style={{ color: PAPER.inkFaded }}>
            {analytics.items.length} parts · {analytics.totalQuotes} quotes
          </span>
        </div>
      </div>
    </>
  );
}

// Aggregate summary for CTA banners / cards.
export function computeAnalyticsSummary(run: BomResearchRun) {
  const items = run.line_items ?? [];
  const rows = items.map((item) => {
    const best = getBestQuote(item);
    const unitCost = best ? Number(best.landed_cost_usd ?? best.unit_price) : null;
    return {
      extended: unitCost != null ? unitCost * item.quantity : null,
      isAvl: best?.is_avl ?? false,
      riskFlags: (((run.results_json ?? {}) as Record<string, unknown>)[`item_${item.id}`] as {risk_flags?: string[]} | undefined)?.risk_flags ?? [],
    };
  });
  const totalSpend = rows.reduce((s, r) => s + (r.extended ?? 0), 0);
  const avlSpend = rows.reduce((s, r) => s + (r.isAvl ? (r.extended ?? 0) : 0), 0);
  const avlCoverage = totalSpend > 0 ? (avlSpend / totalSpend) * 100 : 0;
  const riskCount = rows.reduce((s, r) => s + r.riskFlags.length, 0);
  const quoteCount = items.reduce((s, i) => s + i.quotes.length, 0);
  return { totalSpend, avlCoverage, riskCount, quoteCount, itemCount: items.length };
}

