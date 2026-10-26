import { useState } from 'react';
import { useParams } from 'react-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, CheckCircle2, Loader2 } from 'lucide-react';
import { TopBar } from './TopBar';
import { useApiClient } from '../../api/client';
import type { Bom, BomRow } from '../../api/types';

type EditableField = 'part_number' | 'description' | 'material' | 'process' | 'quantity' | 'spec';

const COLUMNS: { field: EditableField; label: string; width: string }[] = [
  { field: 'part_number', label: 'Part number', width: 'w-36' },
  { field: 'description', label: 'Description', width: '' },
  { field: 'material', label: 'Material', width: 'w-32' },
  { field: 'process', label: 'Process', width: 'w-32' },
  { field: 'quantity', label: 'Qty', width: 'w-16' },
  { field: 'spec', label: 'Spec / tolerance', width: 'w-32' },
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
    onSettled: () => qc.invalidateQueries({ queryKey }),
  });

  const approve = useMutation({
    mutationFn: async () => {
      const res = await apiFetch(`/api/bom/structured/${id}/approve/`, { method: 'POST' });
      if (!res.ok) throw new Error('Could not approve this BOM.');
    },
    onSettled: () => qc.invalidateQueries({ queryKey }),
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
        {(saveRow.error || approve.error) && (
          <p className="text-sm text-[#DC2626]">{((saveRow.error || approve.error) as Error).message}</p>
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
                    <th className="px-3 py-3 text-left text-xs font-medium text-[#8B7F73] w-24">Confidence</th>
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
                      <td className="px-3 py-2 text-xs">
                        {row.edited ? (
                          <span className="text-emerald-700">Reviewed</span>
                        ) : (
                          <span className={row.needs_review ? 'text-amber-700 font-medium' : 'text-[#8B7F73]'}>
                            {Math.round(row.confidence * 100)}%
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-xs text-[#A89D91]">Hover a value to see where it came from. Edited rows are marked reviewed.</p>
          </>
        )}
      </div>
    </div>
  );
}
