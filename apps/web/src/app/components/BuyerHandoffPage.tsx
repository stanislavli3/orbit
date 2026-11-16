import { useState } from 'react';
import { Link, useParams } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { Loader2, Printer } from 'lucide-react';
import { useApiClient } from '../../api/client';
import type { BomHandoff } from '../../api/types';
import { GalvanicFlags } from './GalvanicFlags';

const money = (v: string) => `$${Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

/** Read-only buyer view of a BOM (SCRUM-69). No edit controls; printable. */
export function BuyerHandoffPage() {
  const { bomId } = useParams();
  const apiFetch = useApiClient();
  const [harsh, setHarsh] = useState(false);
  const { data, isLoading, error } = useQuery<BomHandoff>({
    queryKey: ['bom-handoff', bomId, harsh],
    queryFn: async () => {
      const res = await apiFetch(`/api/bom/structured/${bomId}/handoff/${harsh ? '?environment=harsh' : ''}`);
      if (!res.ok) throw new Error('Could not load the handoff view.');
      return res.json();
    },
  });

  return (
    <div className="flex-1 h-full overflow-y-auto bg-[#F9F9F9] print:bg-white">
      <div className="max-w-5xl mx-auto px-8 py-8 space-y-4">
        <div className="flex items-start gap-4">
          <div className="flex-1">
            <p className="text-xs uppercase tracking-wide text-[#A89D91]">Buyer handoff · read-only</p>
            <h1 className="text-xl font-semibold text-[#2B2824]">
              {data ? `${data.bom.reference} · ${data.bom.source_name}` : 'BOM'}
            </h1>
          </div>
          <label className="text-xs text-[#5A524A] flex items-center gap-1.5 print:hidden">
            <input type="checkbox" checked={harsh} onChange={(e) => setHarsh(e.target.checked)} /> Harsh environment
          </label>
          <button onClick={() => window.print()} className="print:hidden inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#E8E0D3] bg-white text-sm text-[#4A4038]">
            <Printer className="w-4 h-4" /> Print
          </button>
        </div>
        {isLoading && <Loader2 className="w-5 h-5 animate-spin text-[#8B7F73]" />}
        {error && <p className="text-sm text-[#DC2626]">{(error as Error).message}</p>}
        {data && (
          <>
            <div className="flex flex-wrap gap-6 text-sm bg-white border border-[#E8E0D3] rounded-xl p-4">
              <div><div className="text-xs text-[#A89D91]">Lines</div>{data.lines.length}</div>
              <div><div className="text-xs text-[#A89D91]">Estimated build cost</div>{money(data.total.low)} – {money(data.total.high)}</div>
              <div><div className="text-xs text-[#A89D91]">Open questions</div>{data.open_question_count}</div>
              <div><div className="text-xs text-[#A89D91]">Material-pair flags</div>{data.galvanic.flags.length}</div>
              <p className="basis-full text-xs text-[#A89D91]">{data.note}{data.uses_sample_data ? ' Includes sample history data.' : ''}</p>
            </div>

            {data.lines.map((l) => (
              <section key={l.row_id} className="bg-white border border-[#E8E0D3] rounded-xl p-4 break-inside-avoid">
                <div className="flex items-baseline gap-3">
                  <span className="text-xs text-[#A89D91]">#{l.line_no}</span>
                  <span className="font-medium text-[#2B2824]">{l.part_number || '(no part number)'}</span>
                  <span className="text-sm text-[#5A524A]">{l.description}</span>
                  <span className="flex-1" />
                  <span className="text-sm text-[#2B2824]">qty {l.quantity}</span>
                </div>
                <p className="text-sm text-[#2B2824] mt-2">
                  {l.explanation}
                  {l.explanation_source === 'claude' && <span className="ml-1 text-[11px] text-[#A89D91]">(worded by Claude)</span>}
                </p>
                <div className="grid grid-cols-3 gap-4 mt-3 text-xs text-[#5A524A]">
                  <div>
                    <div className="font-medium text-[#2B2824]">Unit cost range</div>
                    {money(l.cost.low)} – {money(l.cost.high)}
                    <div className="text-[#A89D91]">
                      Should-cost {money(l.cost.should_cost.expected)} ({l.cost.should_cost.confidence})
                      {l.cost.historical ? ` · history ${money(l.cost.historical.unit_cost)}` : ' · no history'}
                    </div>
                  </div>
                  <div>
                    <div className="font-medium text-[#2B2824]">Approved supplier</div>
                    {l.supplier ? (
                      <>
                        {l.supplier.supplier}
                        {l.supplier.best_quote && ` · quoted ${money(l.supplier.best_quote.unit_price)}`}
                        {l.supplier.best_quote?.lead_time_days ? `, ${l.supplier.best_quote.lead_time_days} days` : ''}
                        {l.alternates.length > 0 && <div className="text-[#A89D91]">Alternates: {l.alternates.join(', ')}</div>}
                      </>
                    ) : <span className="text-[#A89D91]">None on the approved list yet</span>}
                  </div>
                  <div>
                    <div className="font-medium text-[#2B2824]">Open questions ({l.open_questions.length})</div>
                    {l.open_questions.length === 0 ? <span className="text-[#A89D91]">None</span> : (
                      <ul className="list-disc ml-4">{l.open_questions.map((q) => <li key={q}>{q}</li>)}</ul>
                    )}
                  </div>
                </div>
              </section>
            ))}

            <GalvanicFlags report={data.galvanic} />
            <p className="text-xs text-[#A89D91] print:hidden">
              <Link to={`/boms/${data.bom.id}`} className="underline">Back to BOM review</Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
