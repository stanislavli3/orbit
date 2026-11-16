import { useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Loader2, Printer } from 'lucide-react';
import { useApiClient } from '../../api/client';
import type { CallSheet, HandoffStepKey, HandoffSummary, HandoffTimeline, PartComparison } from '../../api/types';
import { Dialog, DialogContent, DialogTitle } from './ui/dialog';

function useJson<T>(key: unknown[], path: string | null) {
  const apiFetch = useApiClient();
  return useQuery<T>({
    queryKey: key,
    enabled: path !== null,
    queryFn: async () => {
      const res = await apiFetch(path!);
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? 'Request failed');
      return data;
    },
  });
}

/** Opens the rendered sheet alone in a new window and prints it. */
function printNode(node: HTMLElement | null, title: string) {
  const w = window.open('', '_blank');
  if (!w || !node) return;
  w.document.title = title;
  w.document.body.style.fontFamily = 'system-ui, sans-serif';
  w.document.body.style.fontSize = '12px';
  w.document.body.innerHTML = node.innerHTML;
  w.print();
}

/** SCRUM-71: what to say and ask when phoning a shortlisted supplier about one BOM line. */
export function CallSheetDialog({ rowId, supplierId, onClose }: { rowId: number; supplierId: number; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const { data, error, isLoading } = useJson<CallSheet>(
    ['call-sheet', rowId, supplierId],
    `/api/parts/call-sheet/?row_id=${rowId}&supplier_id=${supplierId}`,
  );
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogTitle>Call sheet</DialogTitle>
        {isLoading && <Loader2 className="w-4 h-4 animate-spin" />}
        {error && <p className="text-sm text-[#DC2626]">{(error as Error).message}</p>}
        {data && (
          <>
            <div ref={ref} className="text-sm text-[#2B2824] space-y-3">
              <div>
                <h2 className="font-semibold">{data.supplier.name}</h2>
                <p>Contact: {data.supplier.contact_email}</p>
                <p className="text-[#8B7F73]">
                  {data.supplier.approval}
                  {data.supplier.certifications && ` · ${data.supplier.certifications}`}
                </p>
              </div>
              <div>
                <h3 className="font-medium">Part ({data.bom_reference} line {data.line_no})</h3>
                <p>{data.part_summary}</p>
              </div>
              <div>
                <h3 className="font-medium">Quote-critical specs</h3>
                <table className="w-full text-xs">
                  <tbody>
                    {data.specs.map((s) => (
                      <tr key={s.label} className="border-t border-[#F2EDE3]">
                        <td className="py-1 pr-3 text-[#8B7F73]">{s.label}</td>
                        <td className={`py-1 ${s.value === 'Confirm on call' ? 'text-amber-700' : ''}`}>{s.value}</td>
                        <td className="py-1 text-[#A89D91]">{s.source}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div>
                <h3 className="font-medium">Volume and timing</h3>
                <p>
                  {data.volume_and_timing.quantity} per build · needed by: {data.volume_and_timing.needed_by}
                  {data.volume_and_timing.last_quote && ` · last quote ${data.volume_and_timing.last_quote}`}
                  {data.volume_and_timing.last_lead_time_days && `, ${data.volume_and_timing.last_lead_time_days} days`}
                </p>
              </div>
              <div>
                <h3 className="font-medium">Questions to ask</h3>
                <ol className="list-decimal pl-5 space-y-1">
                  {data.questions.map((q) => <li key={q}>{q}</li>)}
                </ol>
              </div>
              <div className="text-xs">
                {data.pros.map((p) => <p key={p} className="text-emerald-700">+ {p}</p>)}
                {data.cons.map((c) => <p key={c} className="text-amber-700">− {c}</p>)}
              </div>
            </div>
            <button
              onClick={() => printNode(ref.current, `Call sheet — ${data.supplier.name}`)}
              className="self-start flex items-center gap-1 px-3 py-1.5 rounded-lg bg-[#2B2824] text-white text-sm"
            >
              <Printer className="w-4 h-4" /> Print
            </button>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

/** SCRUM-53: the current BOM line next to a prior-program part. */
export function CompareDialog({ rowId, partId, onClose }: { rowId: number; partId: number; onClose: () => void }) {
  const { data, error, isLoading } = useJson<PartComparison>(
    ['compare', rowId, partId],
    `/api/parts/compare/?row_id=${rowId}&b=${partId}`,
  );
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogTitle>Compare with past part</DialogTitle>
        {isLoading && <Loader2 className="w-4 h-4 animate-spin" />}
        {error && <p className="text-sm text-[#DC2626]">{(error as Error).message}</p>}
        {data && (
          <table className="w-full text-xs text-[#2B2824]">
            <thead className="text-[#8B7F73]">
              <tr>
                <th className="text-left py-1" />
                <th className="text-left py-1">Current (BOM line)</th>
                <th className="text-left py-1">
                  Past part · <a href={data.right.link} target="_blank" rel="noreferrer" className="underline">source</a>
                </th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((r) => (
                <tr key={r.key} className={`border-t border-[#F2EDE3] ${r.same ? 'bg-emerald-50' : ''}`}>
                  <td className="py-1 pr-2 text-[#8B7F73]">{r.label}</td>
                  <td className="py-1 pr-2" title={data.left.sources[r.key] ? `Source: ${data.left.sources[r.key]}` : ''}>
                    {r.left || '—'}
                  </td>
                  <td className="py-1" title={data.right.sources[r.key] ? `Source: ${data.right.sources[r.key]}` : ''}>
                    {r.right || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </DialogContent>
    </Dialog>
  );
}

const hours = (h: number | null) => (h === null ? '—' : h >= 48 ? `${(h / 24).toFixed(1)} d` : `${h} h`);

/** SCRUM-75: when each CAD-to-quote step happened, per part, with manual dates and CSV export. */
export function HandoffPanel({ bomId }: { bomId: number }) {
  const apiFetch = useApiClient();
  const queryClient = useQueryClient();
  const { data } = useJson<HandoffTimeline>(['handoff', bomId], `/api/parts/handoff/bom/${bomId}/`);
  const { data: summary } = useJson<HandoffSummary>(['handoff-summary'], '/api/parts/handoff/summary/');
  const [step, setStep] = useState<HandoffStepKey>('quote_accepted');
  const [part, setPart] = useState('');
  const [day, setDay] = useState('');
  const [error, setError] = useState('');

  async function save() {
    setError('');
    const res = await apiFetch(`/api/parts/handoff/bom/${bomId}/`, {
      method: 'POST',
      body: JSON.stringify({ step, date: day, part_number: part }),
    });
    const body = await res.json();
    if (!res.ok) return setError(body.detail ?? 'Could not save');
    queryClient.setQueryData(['handoff', bomId], body);
    queryClient.invalidateQueries({ queryKey: ['handoff-summary'] });
  }

  async function exportCsv() {
    const res = await apiFetch(`/api/parts/handoff/bom/${bomId}/?export=csv`);
    const url = URL.createObjectURL(await res.blob());
    const a = document.createElement('a');
    a.href = url;
    a.download = `${data?.reference ?? 'bom'}-handoff.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  if (!data) return null;
  return (
    <div className="border border-[#E8E0D3] rounded-lg p-3 space-y-2 text-xs text-[#2B2824]">
      <div className="flex items-baseline gap-3">
        <h3 className="text-sm font-medium">CAD-to-quote time</h3>
        <span className="text-[#8B7F73]">BOM total {hours(data.total_hours)}</span>
        {data.slowest_step && (
          <span className="text-amber-700">Slowest: {data.slowest_step.label} ({hours(data.slowest_step.median_hours)})</span>
        )}
        {summary?.median_total_hours != null && (
          <span className="text-[#8B7F73]">Median across {summary.parts_timed} parts: {hours(summary.median_total_hours)}</span>
        )}
        <div className="flex-1" />
        <button onClick={exportCsv} className="underline">Export CSV</button>
      </div>
      <table className="w-full">
        <thead className="text-[#8B7F73]">
          <tr>
            <th className="text-left py-1">Part</th>
            {data.steps.map((s) => <th key={s.key} className="text-left py-1">{s.label}</th>)}
            <th className="text-right py-1">Elapsed</th>
            <th className="text-left py-1 pl-3">Slowest step</th>
          </tr>
        </thead>
        <tbody>
          {data.parts.map((p) => (
            <tr key={p.part_number} className="border-t border-[#F2EDE3]">
              <td className="py-1 font-medium">{p.part_number}</td>
              {data.steps.map((s) => (
                <td key={s.key} className="py-1" title={p.manual.includes(s.key) ? 'Set by hand' : 'Recorded by Orbit'}>
                  {p.steps[s.key] ? new Date(p.steps[s.key]!).toLocaleDateString() : '—'}
                  {p.manual.includes(s.key) && '*'}
                </td>
              ))}
              <td className="py-1 text-right">{hours(p.total_hours)}</td>
              <td className="py-1 pl-3 text-[#8B7F73]">{p.slowest ? `${p.slowest.label} (${hours(p.slowest.hours)})` : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex items-center gap-2">
        <span className="text-[#8B7F73]">Set a date:</span>
        <select value={step} onChange={(e) => setStep(e.target.value as HandoffStepKey)} className="border border-[#E8E0D3] rounded px-1 py-0.5">
          {data.steps.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
        </select>
        <select value={part} onChange={(e) => setPart(e.target.value)} className="border border-[#E8E0D3] rounded px-1 py-0.5">
          <option value="">Whole BOM</option>
          {data.parts.map((p) => <option key={p.part_number} value={p.part_number}>{p.part_number}</option>)}
        </select>
        <input type="date" value={day} onChange={(e) => setDay(e.target.value)} className="border border-[#E8E0D3] rounded px-1 py-0.5" />
        <button onClick={save} disabled={!day} className="px-2 py-0.5 rounded bg-[#2B2824] text-white disabled:opacity-40">Save</button>
        {error && <span className="text-[#DC2626]">{error}</span>}
        <span className="text-[#A89D91]">* set by hand</span>
      </div>
    </div>
  );
}
