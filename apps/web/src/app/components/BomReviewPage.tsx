import { useState } from 'react';
import { useParams } from 'react-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, CheckCircle2, FileText, Loader2 } from 'lucide-react';
import { TopBar } from './TopBar';
import { useApiClient } from '../../api/client';
import type { Bom, BomRow, QuickEstimateReport, RfqDraft } from '../../api/types';
import { CostRangeCell, EnteredPriceInput, PriceFlagBadge, PriceFlagSummaryText } from './ShouldCostRange';

type EditableField = 'part_number' | 'description' | 'material' | 'process' | 'quantity' | 'spec' | 'revision';

const COLUMNS: { field: EditableField; label: string; width: string }[] = [
  { field: 'part_number', label: 'Part number', width: 'w-36' },
  { field: 'description', label: 'Description', width: '' },
  { field: 'material', label: 'Material', width: 'w-32' },
  { field: 'process', label: 'Process', width: 'w-32' },
  { field: 'quantity', label: 'Qty', width: 'w-16' },
  { field: 'spec', label: 'Spec / tolerance', width: 'w-32' },
  { field: 'revision', label: 'Rev', width: 'w-16' },
];

const STATUS_LABEL: Record<Bom['status'], string> = {
  extracting: 'Extracting…',
  needs_review: 'Needs review',
  approved: 'Approved',
  failed: 'Failed',
};

/** One cell: shows the value, saves on blur when it changed. Hover shows where the value came from. */
function EditableCell({ row, field, onSave }: { row: BomRow; field: EditableField; onSave: (value: string) => void }) {
  const original = String(row[field] ?? '');
  const [value, setValue] = useState(original);
  return (
    <input
      value={value}
      title={row.sources[field] ? `Source: ${row.sources[field]}` : 'No source'}
      onChange={(e) => setValue(e.target.value)}
      onBlur={() => value !== original && onSave(value)}
      className="w-full bg-transparent px-1 py-0.5 rounded border border-transparent hover:border-[#E8E0D3] focus:border-[#8B7F73] focus:outline-none text-[#2B2824]"
    />
  );
}

export function BomReviewPage() {
  const { id } = useParams();
  const apiFetch = useApiClient();
  const qc = useQueryClient();
  const queryKey = ['bom', id];

  const { data: bom, isLoading, error } = useQuery<Bom>({
    queryKey,
    queryFn: async () => {
      const res = await apiFetch(`/api/bom/structured/${id}/`);
      if (!res.ok) throw new Error('Could not load this BOM.');
      return res.json();
    },
    refetchInterval: (q) => (q.state.data?.status === 'extracting' ? 2000 : false),
  });

  const saveRow = useMutation({
    mutationFn: async ({ rowId, field, value }: { rowId: number; field: EditableField; value: string }) => {
      const res = await apiFetch(`/api/bom/structured/${id}/rows/${rowId}/`, {
        method: 'PATCH',
        body: JSON.stringify({ [field]: field === 'quantity' ? Number(value) : value }),
      });
      if (!res.ok) throw new Error('Could not save that change.');
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey });
      qc.invalidateQueries({ queryKey: ['bom-should-cost', id] });
    },
  });

  const approve = useMutation({
    mutationFn: async () => {
      const res = await apiFetch(`/api/bom/structured/${id}/approve/`, { method: 'POST' });
      if (!res.ok) throw new Error('Could not approve this BOM.');
    },
    onSettled: () => qc.invalidateQueries({ queryKey }),
  });

  // SCRUM-73/74: should-cost range and price flags per line, from the quick-estimate report.
  const costKey = ['bom-should-cost', id];
  const { data: costs } = useQuery<QuickEstimateReport>({
    queryKey: costKey,
    queryFn: async () => {
      const res = await apiFetch(`/api/parts/quick-estimate/${id}/`);
      if (!res.ok) throw new Error('Could not load should-cost');
      return res.json();
    },
    enabled: !!bom,
  });
  const costByRow = new Map((costs?.rows ?? []).map((r) => [r.row_id, r]));

  const [rfq, setRfq] = useState<RfqDraft | null>(null);
  const draftRfq = useMutation({
    mutationFn: async (rowId: number) => {
      const res = await apiFetch(`/api/bom/structured/${id}/rows/${rowId}/rfq/`, { method: 'POST' });
      if (!res.ok) throw new Error('Could not draft an RFQ for that row.');
      return (await res.json()) as RfqDraft;
    },
    onSuccess: setRfq,
  });

  return (
    <div className="flex-1 flex flex-col h-full bg-[#F9F9F9]">
      <TopBar
        title={bom ? `${bom.reference} · ${bom.source_name}` : 'BOM'}
        subtitle="Check the extracted parts, fix anything flagged, then approve."
      />
      <div className="flex-1 overflow-y-auto px-8 py-8 space-y-4">
        {isLoading && <Loader2 className="w-5 h-5 animate-spin text-[#8B7F73]" />}
        {error && <p className="text-sm text-[#DC2626]">{(error as Error).message}</p>}
        {(saveRow.error || approve.error || draftRfq.error) && (
          <p className="text-sm text-[#DC2626]">{((saveRow.error || approve.error || draftRfq.error) as Error).message}</p>
        )}

        {bom && (
          <>
            <div className="flex items-center gap-3">
              <span className="text-xs px-2 py-1 rounded-full bg-[#F2EDE3] text-[#8B7F73] font-medium">
                {STATUS_LABEL[bom.status]}
              </span>
              {bom.review_count > 0 && (
                <span className="inline-flex items-center gap-1 text-xs text-amber-700">
                  <AlertTriangle className="w-3.5 h-3.5" />
                  {bom.review_count} row{bom.review_count !== 1 ? 's' : ''} flagged for review
                </span>
              )}
              {bom.error && <span className="text-xs text-[#DC2626]">{bom.error}</span>}
              {costs && <span className="text-xs"><PriceFlagSummaryText summary={costs.price_flags} /></span>}
              <div className="flex-1" />
              {bom.status === 'needs_review' && (
                <button
                  onClick={() => approve.mutate()}
                  disabled={approve.isPending}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#2B2824] text-white text-sm hover:opacity-90 disabled:opacity-50"
                >
                  <CheckCircle2 className="w-4 h-4" />
                  Approve BOM
                </button>
              )}
            </div>

            <div className="bg-white border border-[#E8E0D3] rounded-xl overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-[#F9F9F9] border-b border-[#E8E0D3]">
                  <tr>
                    <th className="px-3 py-3 text-left text-xs font-medium text-[#8B7F73] w-10">#</th>
                    {COLUMNS.map((c) => (
                      <th key={c.field} className={`px-3 py-3 text-left text-xs font-medium text-[#8B7F73] ${c.width}`}>
                        {c.label}
                      </th>
                    ))}
                    <th className="px-3 py-3 text-right text-xs font-medium text-[#8B7F73] w-44">Should-cost (low–high)</th>
                    <th className="px-3 py-3 text-left text-xs font-medium text-[#8B7F73] w-32">Entered price</th>
                    <th className="px-3 py-3 text-left text-xs font-medium text-[#8B7F73] w-24">Confidence</th>
                    <th className="px-3 py-3 w-24" />
                  </tr>
                </thead>
                <tbody>
                  {bom.rows.map((row) => (
                    <tr key={row.id} className={`border-t border-[#F2EDE3] align-top ${row.needs_review ? 'bg-amber-50/60' : ''}`}>
                      <td className="px-3 py-2 text-[#A89D91]">{row.line_no}</td>
                      {COLUMNS.map((c) => (
                        <td key={c.field} className="px-2 py-1.5">
                          <EditableCell
                            key={`${row.id}-${String(row[c.field])}`}
                            row={row}
                            field={c.field}
                            onSave={(value) => saveRow.mutate({ rowId: row.id, field: c.field, value })}
                          />
                          {c.field === 'description' && row.flags.length > 0 && (
                            <p className="mt-1 px-1 text-[11px] text-amber-700">{row.flags.join(' · ')}</p>
                          )}
                        </td>
                      ))}
                      <td className="px-3 py-2 text-right">
                        {costByRow.get(row.id) && <CostRangeCell range={costByRow.get(row.id)!.cost_range} />}
                        <PriceFlagBadge flag={costByRow.get(row.id)?.price_flag ?? null} />
                      </td>
                      <td className="px-3 py-2">
                        <EnteredPriceInput
                          key={`${row.id}-${row.entered_price}-${row.entered_price_note}`}
                          rowId={row.id}
                          price={row.entered_price}
                          note={row.entered_price_note}
                          onSaved={() => {
                            qc.invalidateQueries({ queryKey });
                            qc.invalidateQueries({ queryKey: costKey });
                          }}
                        />
                      </td>
                      <td className="px-3 py-2 text-xs">
                        {row.edited ? (
                          <span className="text-emerald-700">Reviewed</span>
                        ) : (
                          <span className={row.needs_review ? 'text-amber-700 font-medium' : 'text-[#8B7F73]'}>
                            {Math.round(row.confidence * 100)}%
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-2">
                        <button
                          onClick={() => draftRfq.mutate(row.id)}
                          disabled={draftRfq.isPending}
                          className="inline-flex items-center gap-1 text-xs text-[#4A4038] hover:underline disabled:opacity-50"
                        >
                          <FileText className="w-3.5 h-3.5" />
                          Draft RFQ
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {rfq && <RfqEditor key={rfq.id} rfq={rfq} onChange={setRfq} />}
            <p className="text-xs text-[#A89D91]">Hover a value to see where it came from. Edited rows are marked reviewed.</p>
          </>
        )}
      </div>
    </div>
  );
}

type RfqField = 'part_context' | 'material' | 'blank_size' | 'tolerance' | 'quantity' | 'due_date' | 'notes';

const RFQ_FIELDS: { field: RfqField; label: string; type?: string }[] = [
  { field: 'part_context', label: 'Part description' },
  { field: 'material', label: 'Material' },
  { field: 'blank_size', label: 'Blank / stock size' },
  { field: 'tolerance', label: 'Tolerance' },
  { field: 'quantity', label: 'Quantity', type: 'number' },
  { field: 'due_date', label: 'Quote due date', type: 'date' },
  { field: 'notes', label: 'Notes' },
];

/** SCRUM-32: edit an RFQ draft; blanks stay "assumption — confirm" in the export. */
function RfqEditor({ rfq, onChange }: { rfq: RfqDraft; onChange: (rfq: RfqDraft) => void }) {
  const apiFetch = useApiClient();
  const [form, setForm] = useState(() =>
    Object.fromEntries(RFQ_FIELDS.map(({ field }) => [field, rfq[field] == null ? '' : String(rfq[field])])),
  );

  const save = useMutation({
    mutationFn: async () => {
      const body = Object.fromEntries(
        RFQ_FIELDS.map(({ field }) => {
          const value = form[field].trim();
          if (field === 'quantity' || field === 'due_date') return [field, value === '' ? null : value];
          return [field, value];
        }),
      );
      const res = await apiFetch(`/api/bom/rfqs/${rfq.id}/`, { method: 'PATCH', body: JSON.stringify(body) });
      if (!res.ok) throw new Error('Could not save the RFQ draft.');
      return (await res.json()) as RfqDraft;
    },
    onSuccess: onChange,
  });

  const openPrintable = async () => {
    const res = await apiFetch(`/api/bom/rfqs/${rfq.id}/export/`);
    const url = URL.createObjectURL(await res.blob());
    window.open(url, '_blank');
  };

  return (
    <div className="bg-white border border-[#E8E0D3] rounded-xl p-5 space-y-3">
      <div className="flex items-center gap-3">
        <h3 className="text-sm font-medium text-[#2B2824]">
          RFQ spec sheet · {rfq.part_number || 'part'} ({rfq.bom_reference})
        </h3>
        <span className="text-xs px-2 py-0.5 rounded-full bg-[#F2EDE3] text-[#8B7F73]">{rfq.status}</span>
      </div>
      <div className="grid grid-cols-2 gap-3">
        {RFQ_FIELDS.map(({ field, label, type }) => (
          <label key={field} className="text-xs text-[#8B7F73] space-y-1">
            <span>{label}</span>
            <input
              type={type ?? 'text'}
              value={form[field]}
              onChange={(e) => setForm({ ...form, [field]: e.target.value })}
              placeholder="Assumption — confirm"
              className="w-full px-2 py-1.5 rounded border border-[#E8E0D3] text-sm text-[#2B2824]"
            />
          </label>
        ))}
      </div>
      {rfq.assumptions.length > 0 && (
        <ul className="text-xs text-amber-700 list-disc pl-5">
          {rfq.assumptions.map((a) => <li key={a}>{a}</li>)}
        </ul>
      )}
      {save.error && <p className="text-xs text-[#DC2626]">{(save.error as Error).message}</p>}
      <div className="flex gap-2">
        <button
          onClick={() => save.mutate()}
          disabled={save.isPending}
          className="px-3 py-1.5 rounded-lg bg-[#2B2824] text-white text-sm hover:opacity-90 disabled:opacity-50"
        >
          Save draft
        </button>
        <button onClick={openPrintable} className="px-3 py-1.5 rounded-lg border border-[#E8E0D3] text-sm text-[#4A4038]">
          Open printable sheet
        </button>
      </div>
    </div>
  );
}
