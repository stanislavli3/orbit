import { useMemo, useState } from 'react';
import {
  Download,
  ChevronDown,
  ChevronUp,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  FileSpreadsheet,
  AlertTriangle,
  Clock3,
  CircleAlert,
} from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { toast } from 'sonner';
import { useApiClient } from '../../api/client';
import type { BomExcelDownloadResponse, BomLineItem, BomResearchRun } from '../../api/types';

type SortKey =
  | 'index'
  | 'part_name'
  | 'material'
  | 'quantity'
  | 'unit_cost'
  | 'extended_cost'
  | 'supplier'
  | 'lead_time'
  | 'status';

type SortDirection = 'asc' | 'desc';
type FilterValue = 'all' | 'sourced' | 'needs_input' | 'cots';

type BomItemResult = {
  risk_flags?: string[];
  summary?: string;
};

interface Props {
  runs: BomResearchRun[];
  selectedRun: BomResearchRun | null;
  selectedRunId: number | null;
  onSelectRun: (runId: number) => void;
}

interface RowData {
  item: BomLineItem;
  index: number;
  bestQuote: BomLineItem['quotes'][number] | null;
  unitCost: number | null;
  extendedCost: number | null;
  leadTime: number | null;
  supplier: string;
  material: string;
  displayStatus: string;
  sortStatus: string;
  riskFlags: string[];
  hasNonAvl: boolean;
  summary?: string;
}

function formatCurrency(value: number | null): string {
  if (value == null) return '—';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
  }).format(value);
}

function formatBytes(bytes: number | null): string {
  if (bytes == null) return 'Unknown size';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDateTime(iso: string | null): string {
  if (!iso) return 'Unknown time';
  return new Date(iso).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

function getBestQuote(item: BomLineItem) {
  if (!item.quotes.length) return null;
  return [...item.quotes].sort((left, right) => {
    const leftCost = Number(left.landed_cost_usd ?? left.unit_price);
    const rightCost = Number(right.landed_cost_usd ?? right.unit_price);
    return leftCost - rightCost || Number(left.unit_price) - Number(right.unit_price) || left.lead_time_days - right.lead_time_days;
  })[0];
}

function getDisplayStatus(item: BomLineItem, bestQuote: BomLineItem['quotes'][number] | null) {
  if (item.status === 'needs_input') return { label: 'Needs Input', sortValue: 'needs_input' as const };
  if (item.status === 'sourced' && bestQuote && Number(bestQuote.tooling_cost) === 0) {
    return { label: 'COTS', sortValue: 'cots' as const };
  }
  if (item.status === 'sourced') return { label: 'Sourced', sortValue: 'sourced' as const };
  if (item.status === 'researching') return { label: 'Researching', sortValue: 'researching' as const };
  return { label: 'Pending', sortValue: 'pending' as const };
}

function getRiskBadges(row: RowData) {
  const badges: { key: string; label: string; className: string }[] = [];
  if (row.riskFlags.includes('single-source')) {
    badges.push({ key: 'single-source', label: '🔴 Single source', className: 'bg-red-50 text-red-700 border-red-200' });
  }
  if (row.riskFlags.includes('long-lead-time')) {
    badges.push({ key: 'long-lead-time', label: '🟡 Long lead time', className: 'bg-amber-50 text-amber-700 border-amber-200' });
  }
  if (row.hasNonAvl) {
    badges.push({ key: 'not-on-avl', label: '⚠️ Not on AVL', className: 'bg-orange-50 text-orange-700 border-orange-200' });
  }
  return badges;
}

function SortButton({
  label,
  sortKey,
  activeSort,
  onClick,
}: {
  label: string;
  sortKey: SortKey;
  activeSort: { key: SortKey; direction: SortDirection };
  onClick: (key: SortKey) => void;
}) {
  const active = activeSort.key === sortKey;
  return (
    <button
      type="button"
      onClick={() => onClick(sortKey)}
      className={`inline-flex items-center gap-1 transition-colors ${active ? 'text-[#111111]' : 'text-[#6B7280] hover:text-[#111111]'}`}
    >
      <span>{label}</span>
      {active ? (
        activeSort.direction === 'asc' ? <ArrowUp className="w-3.5 h-3.5" /> : <ArrowDown className="w-3.5 h-3.5" />
      ) : (
        <ArrowUpDown className="w-3.5 h-3.5" />
      )}
    </button>
  );
}

function ResultsTable({ run }: { run: BomResearchRun }) {
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [sort, setSort] = useState<{ key: SortKey; direction: SortDirection }>({
    key: 'index',
    direction: 'asc',
  });
  const [filter, setFilter] = useState<FilterValue>('all');

  const rows = useMemo<RowData[]>(() => {
    return run.line_items.map((item, index) => {
      const bestQuote = getBestQuote(item);
      const results = (run.results_json[`item_${item.id}`] ?? {}) as BomItemResult;
      const unitCost = bestQuote ? Number(bestQuote.unit_price) : null;
      const extendedCost = unitCost != null ? unitCost * item.quantity : null;
      const status = getDisplayStatus(item, bestQuote);
      return {
        item,
        index: index + 1,
        bestQuote,
        unitCost,
        extendedCost,
        leadTime: bestQuote?.lead_time_days ?? null,
        supplier: bestQuote?.supplier_name ?? '—',
        material: item.material_spec || (results as { material?: string }).material || '—',
        displayStatus: status.label,
        sortStatus: status.sortValue,
        riskFlags: results.risk_flags ?? [],
        hasNonAvl: item.quotes.some((quote) => !quote.is_avl),
        summary: results.summary,
      };
    });
  }, [run]);

  const filteredRows = useMemo(() => {
    return rows.filter((row) => {
      if (filter === 'all') return true;
      return row.sortStatus === filter;
    });
  }, [filter, rows]);

  const sortedRows = useMemo(() => {
    const direction = sort.direction === 'asc' ? 1 : -1;
    const sorted = [...filteredRows];
    sorted.sort((left, right) => {
      const compare = (() => {
        switch (sort.key) {
          case 'index':
            return left.index - right.index;
          case 'part_name':
            return left.item.part_name.localeCompare(right.item.part_name);
          case 'material':
            return left.material.localeCompare(right.material);
          case 'quantity':
            return left.item.quantity - right.item.quantity;
          case 'unit_cost':
            return (left.unitCost ?? Number.POSITIVE_INFINITY) - (right.unitCost ?? Number.POSITIVE_INFINITY);
          case 'extended_cost':
            return (left.extendedCost ?? Number.POSITIVE_INFINITY) - (right.extendedCost ?? Number.POSITIVE_INFINITY);
          case 'supplier':
            return left.supplier.localeCompare(right.supplier);
          case 'lead_time':
            return (left.leadTime ?? Number.POSITIVE_INFINITY) - (right.leadTime ?? Number.POSITIVE_INFINITY);
          case 'status':
            return left.displayStatus.localeCompare(right.displayStatus);
        }
      })();
      return compare * direction;
    });
    return sorted;
  }, [filteredRows, sort]);

  function toggleSort(key: SortKey) {
    setSort((current) => {
      if (current.key === key) {
        return { key, direction: current.direction === 'asc' ? 'desc' : 'asc' };
      }
      return { key, direction: 'asc' };
    });
  }

  return (
    <div className="rounded-2xl border border-[#E6E6E6] bg-white overflow-hidden">
      <div className="px-5 py-4 border-b border-[#EFEFEF] bg-[#FBFBFB]">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div>
            <p className="text-sm font-semibold text-[#111111]">Results Table</p>
            <p className="text-[12px] text-[#6B7280] mt-0.5">
              {run.line_items.length} part{run.line_items.length !== 1 ? 's' : ''} · client-side sort and filter
            </p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {[
              { value: 'all', label: 'All' },
              { value: 'sourced', label: 'Sourced' },
              { value: 'needs_input', label: 'Needs Input' },
              { value: 'cots', label: 'COTS' },
            ].map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => setFilter(option.value as FilterValue)}
                className={`px-3 py-1.5 rounded-full border text-[12px] transition-colors ${
                  filter === option.value
                    ? 'bg-[#111111] text-white border-[#111111]'
                    : 'bg-white text-[#4B5563] border-[#E6E6E6] hover:border-[#111111]'
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[1080px]">
          <thead className="bg-[#FAFAFA] border-b border-[#EFEFEF]">
            <tr className="text-left text-[11px] font-semibold uppercase tracking-[0.16em]">
              <th className="px-4 py-3"><SortButton label="#" sortKey="index" activeSort={sort} onClick={toggleSort} /></th>
              <th className="px-4 py-3"><SortButton label="Part Name" sortKey="part_name" activeSort={sort} onClick={toggleSort} /></th>
              <th className="px-4 py-3"><SortButton label="Material" sortKey="material" activeSort={sort} onClick={toggleSort} /></th>
              <th className="px-4 py-3"><SortButton label="Qty" sortKey="quantity" activeSort={sort} onClick={toggleSort} /></th>
              <th className="px-4 py-3"><SortButton label="Best Unit Cost" sortKey="unit_cost" activeSort={sort} onClick={toggleSort} /></th>
              <th className="px-4 py-3"><SortButton label="Extended Cost" sortKey="extended_cost" activeSort={sort} onClick={toggleSort} /></th>
              <th className="px-4 py-3"><SortButton label="Supplier" sortKey="supplier" activeSort={sort} onClick={toggleSort} /></th>
              <th className="px-4 py-3"><SortButton label="Lead Time" sortKey="lead_time" activeSort={sort} onClick={toggleSort} /></th>
              <th className="px-4 py-3"><SortButton label="Status" sortKey="status" activeSort={sort} onClick={toggleSort} /></th>
              <th className="px-4 py-3 text-right text-[#6B7280]">Expand</th>
            </tr>
          </thead>
          <tbody>
            {sortedRows.length === 0 && (
              <tr>
                <td colSpan={10} className="px-4 py-10 text-center text-sm text-[#6B7280]">
                  No rows match the current filter.
                </td>
              </tr>
            )}
            {sortedRows.map((row) => {
              const riskBadges = getRiskBadges(row);
              const open = expandedId === row.item.id;
              return (
                <>
                  <tr key={row.item.id} className="border-b border-[#F0F0F0] align-top hover:bg-[#FCFCFC]">
                    <td className="px-4 py-4 text-sm text-[#6B7280]">{row.index}</td>
                    <td className="px-4 py-4">
                      <div className="space-y-2">
                        <div>
                          <p className="text-sm font-medium text-[#111111]">{row.item.part_name}</p>
                          {row.item.part_number && (
                            <p className="text-[11px] font-mono text-[#9CA3AF] mt-0.5">{row.item.part_number}</p>
                          )}
                        </div>
                        {riskBadges.length > 0 && (
                          <div className="flex flex-wrap gap-1.5">
                            {riskBadges.map((badge) => (
                              <span key={badge.key} className={`inline-flex items-center px-2 py-0.5 rounded-full border text-[10px] font-medium ${badge.className}`}>
                                {badge.label}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-4 text-sm text-[#374151]">{row.material}</td>
                    <td className="px-4 py-4 text-sm text-[#111111]">{row.item.quantity}</td>
                    <td className="px-4 py-4 text-sm font-medium text-[#111111]">{formatCurrency(row.unitCost)}</td>
                    <td className="px-4 py-4 text-sm font-medium text-[#111111]">{formatCurrency(row.extendedCost)}</td>
                    <td className="px-4 py-4 text-sm text-[#374151]">{row.supplier}</td>
                    <td className="px-4 py-4 text-sm text-[#374151]">{row.leadTime != null ? `${row.leadTime}d` : '—'}</td>
                    <td className="px-4 py-4">
                      <span className="inline-flex items-center rounded-full border border-[#E6E6E6] bg-[#FAFAFA] px-2.5 py-1 text-[11px] font-medium text-[#374151]">
                        {row.displayStatus}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-right">
                      <button
                        type="button"
                        onClick={() => setExpandedId(open ? null : row.item.id)}
                        className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-[#E6E6E6] text-[#6B7280] hover:border-[#111111] hover:text-[#111111]"
                      >
                        {open ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                      </button>
                    </td>
                  </tr>
                  {open && (
                    <tr key={`${row.item.id}-expanded`} className="border-b border-[#F0F0F0] bg-[#FBFBFB]">
                      <td colSpan={10} className="px-4 py-4">
                        <div className="rounded-xl border border-[#EAEAEA] bg-white overflow-hidden">
                          <div className="px-4 py-3 border-b border-[#EFEFEF] flex items-center justify-between gap-3 flex-wrap">
                            <div>
                              <p className="text-[12px] font-semibold uppercase tracking-[0.16em] text-[#6B7280]">Supplier Comparison</p>
                              {row.summary && <p className="text-[12px] text-[#4B5563] mt-1">{row.summary}</p>}
                            </div>
                          </div>
                          <div className="overflow-x-auto">
                            <table className="w-full min-w-[760px]">
                              <thead className="bg-[#FAFAFA] border-b border-[#EFEFEF]">
                                <tr className="text-left text-[11px] font-semibold uppercase tracking-[0.16em] text-[#6B7280]">
                                  <th className="px-4 py-3">Supplier</th>
                                  <th className="px-4 py-3">Unit Price</th>
                                  <th className="px-4 py-3">MOQ</th>
                                  <th className="px-4 py-3">Lead Time</th>
                                  <th className="px-4 py-3">Tooling Cost</th>
                                  <th className="px-4 py-3">Notes</th>
                                </tr>
                              </thead>
                              <tbody>
                                {row.item.quotes.map((quote) => (
                                  <tr key={quote.id} className="border-b border-[#F4F4F4] last:border-b-0 align-top">
                                    <td className="px-4 py-3 text-sm text-[#111111]">
                                      <div className="flex items-center gap-2 flex-wrap">
                                        <span>{quote.supplier_name}</span>
                                        {!quote.is_avl && (
                                          <span className="inline-flex items-center rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[10px] font-medium text-amber-700">
                                            ⚠️ Non-AVL
                                          </span>
                                        )}
                                      </div>
                                    </td>
                                    <td className="px-4 py-3 text-sm text-[#111111]">{formatCurrency(Number(quote.unit_price))}</td>
                                    <td className="px-4 py-3 text-sm text-[#374151]">{quote.moq}</td>
                                    <td className="px-4 py-3 text-sm text-[#374151]">{quote.lead_time_days}d</td>
                                    <td className="px-4 py-3 text-sm text-[#374151]">{formatCurrency(Number(quote.tooling_cost))}</td>
                                    <td className="px-4 py-3 text-sm text-[#4B5563]">{quote.notes || '—'}</td>
                                  </tr>
                                ))}
                                {row.item.quotes.length === 0 && (
                                  <tr>
                                    <td colSpan={6} className="px-4 py-6 text-center text-sm text-[#6B7280]">
                                      No supplier quotes captured for this part.
                                    </td>
                                  </tr>
                                )}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function BomResultsPanel({ runs, selectedRun, selectedRunId, onSelectRun }: Props) {
  const apiFetch = useApiClient();

  const { data: excelDownload, isFetching: excelLoading } = useQuery<BomExcelDownloadResponse>({
    queryKey: ['bom-excel', selectedRunId],
    queryFn: async () => {
      const res = await apiFetch(`/api/bom/runs/${selectedRunId}/excel/`);
      if (!res.ok) {
        const error = await res.json().catch(() => ({}));
        throw new Error(error.detail ?? 'Failed to load Excel metadata');
      }
      return res.json();
    },
    enabled: !!selectedRunId && selectedRun?.status === 'completed',
    staleTime: 60_000,
  });

  async function openExcelDownload(runId: number) {
    try {
      const res = await apiFetch(`/api/bom/runs/${runId}/excel/`);
      if (!res.ok) {
        const error = await res.json().catch(() => ({}));
        throw new Error(error.detail ?? 'Excel report not available yet');
      }
      const payload = (await res.json()) as BomExcelDownloadResponse;
      window.open(payload.url, '_blank', 'noopener');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to open Excel report');
    }
  }

  return (
    <section className="mb-8 space-y-5">
      <div className="rounded-3xl border border-[#E6E6E6] bg-white overflow-hidden">
        <div className="px-6 py-5 border-b border-[#F0F0F0] bg-[linear-gradient(135deg,#FCFCFC_0%,#F5F7FA_100%)]">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-[#E6E6E6] bg-white px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#6B7280]">
                <FileSpreadsheet className="w-3.5 h-3.5" />
                BOM Research
              </div>
              <h2 className="text-xl font-semibold text-[#111111] mt-3">Results & Run History</h2>
              <p className="text-sm text-[#6B7280] mt-1">
                Review sourced parts, compare supplier quotes, and reopen previous BOM research runs.
              </p>
            </div>

            <div className="flex items-center gap-3 flex-wrap">
              {selectedRun?.status === 'completed' && excelDownload && (
                <div className="text-right">
                  <p className="text-[12px] text-[#4B5563]">{formatBytes(excelDownload.file_size)}</p>
                  <p className="text-[11px] text-[#9CA3AF]">Generated {formatDateTime(excelDownload.generated_at)}</p>
                </div>
              )}
              <button
                type="button"
                onClick={() => selectedRunId && openExcelDownload(selectedRunId)}
                disabled={!selectedRunId || selectedRun?.status !== 'completed' || excelLoading}
                className="inline-flex items-center gap-2 rounded-xl bg-[#111111] px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[#262626] disabled:cursor-not-allowed disabled:bg-[#D1D5DB]"
              >
                <Download className="w-4 h-4" />
                Download Excel
              </button>
            </div>
          </div>
        </div>

        <div className="grid gap-0 lg:grid-cols-[minmax(0,1fr)_320px]">
          <div className="p-5 border-b border-[#F0F0F0] lg:border-b-0 lg:border-r">
            {!selectedRun ? (
              <div className="rounded-2xl border border-dashed border-[#D6D6D6] bg-[#FAFAFA] px-6 py-12 text-center">
                <p className="text-sm font-medium text-[#111111]">No BOM runs yet</p>
                <p className="text-[12px] text-[#6B7280] mt-1">Start a BOM run to see the in-app results table and Excel export.</p>
              </div>
            ) : selectedRun.status === 'completed' ? (
              <ResultsTable run={selectedRun} />
            ) : (
              <div className="rounded-2xl border border-[#E6E6E6] bg-[#FAFAFA] px-6 py-10">
                <div className="flex items-center gap-3">
                  {selectedRun.status === 'failed' ? (
                    <CircleAlert className="w-5 h-5 text-red-500" />
                  ) : (
                    <Clock3 className="w-5 h-5 text-blue-500" />
                  )}
                  <div>
                    <p className="text-sm font-medium text-[#111111]">
                      {selectedRun.status === 'failed' ? 'This BOM run failed' : 'This BOM run is still in progress'}
                    </p>
                    <p className="text-[12px] text-[#6B7280] mt-1">
                      {selectedRun.status === 'failed'
                        ? 'Reopen the run from history or start a new one once inputs are fixed.'
                        : 'The live panel will keep polling while research continues. Results table appears when the run completes.'}
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>

          <aside className="p-5 bg-[#FCFCFC]">
            <div className="flex items-center justify-between gap-2 mb-4">
              <div>
                <p className="text-sm font-semibold text-[#111111]">Run History</p>
                <p className="text-[12px] text-[#6B7280] mt-0.5">{runs.length} run{runs.length !== 1 ? 's' : ''}</p>
              </div>
            </div>

            <div className="space-y-3">
              {runs.length === 0 && (
                <div className="rounded-2xl border border-dashed border-[#D6D6D6] bg-white px-4 py-6 text-center text-sm text-[#6B7280]">
                  No BOM runs yet.
                </div>
              )}
              {runs.map((run) => {
                const active = selectedRunId === run.id;
                const partCount = run.line_items.length;
                return (
                  <div
                    key={run.id}
                    className={`rounded-2xl border px-4 py-4 transition-colors ${
                      active ? 'border-[#111111] bg-white' : 'border-[#E6E6E6] bg-white hover:border-[#B8B8B8]'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-medium text-[#111111]">Run #{run.id}</p>
                        <p className="text-[12px] text-[#6B7280] mt-1">
                          {formatDateTime(run.completed_at ?? run.created_at)}
                        </p>
                      </div>
                      <span className="rounded-full border border-[#E6E6E6] bg-[#FAFAFA] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-[#4B5563]">
                        {run.status.replace(/_/g, ' ')}
                      </span>
                    </div>
                    <div className="mt-3 flex items-center gap-2 flex-wrap text-[12px] text-[#4B5563]">
                      <span>{partCount} part{partCount !== 1 ? 's' : ''}</span>
                      {run.excel_s3_key && <span>• Excel ready</span>}
                    </div>
                    <div className="mt-4 flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => onSelectRun(run.id)}
                        className="inline-flex items-center rounded-lg border border-[#E6E6E6] bg-white px-3 py-1.5 text-[12px] font-medium text-[#111111] hover:border-[#111111]"
                      >
                        View
                      </button>
                      <button
                        type="button"
                        onClick={() => openExcelDownload(run.id)}
                        disabled={!run.excel_s3_key}
                        className="inline-flex items-center gap-1 rounded-lg border border-[#E6E6E6] bg-white px-3 py-1.5 text-[12px] font-medium text-[#111111] hover:border-[#111111] disabled:cursor-not-allowed disabled:text-[#9CA3AF]"
                      >
                        <Download className="w-3.5 h-3.5" />
                        Download
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>

            {selectedRun?.status === 'completed' && selectedRun.line_items.some((item) => item.quotes.some((quote) => !quote.is_avl)) && (
              <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-600 mt-0.5" />
                  <p className="text-[12px] text-amber-800">
                    At least one selected run includes non-AVL supplier options. Expand affected rows to review them.
                  </p>
                </div>
              </div>
            )}
          </aside>
        </div>
      </div>
    </section>
  );
}
