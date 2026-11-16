import { Fragment, useRef, useState } from 'react';
import { Link } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, Loader2, Upload } from 'lucide-react';
import { useApiClient } from '../../api/client';
import type { Project, QuickEstimateReport, QuickEstimateRow } from '../../api/types';

const CONFIDENCE_STYLE: Record<QuickEstimateRow['confidence'], string> = {
  high: 'text-emerald-700',
  medium: 'text-[#8B7F73]',
  low: 'text-amber-700',
  none: 'text-[#A89D91]',
};

/** One row's "why": matched parts and their cost sources, assumptions, and the supplier shortlist. */
function RowDetails({ r }: { r: QuickEstimateRow }) {
  return (
    <div className="grid grid-cols-3 gap-4 text-xs text-[#2B2824] px-4 py-3 bg-[#FFFCF7]">
      <div>
        <p className="font-medium text-[#8B7F73] mb-1">Similar past parts</p>
        {r.matches.length === 0 && <p className="text-[#A89D91]">None found.</p>}
        {r.matches.map((m) => (
          <div key={m.part_id} className="mb-2">
            <p>
              <span className="font-medium">{m.part_number}</span> · ${m.cost.unit_cost}
              {m.cost.model_year && ` (${m.cost.model_year})`} → ${m.adjusted_unit_cost} today
            </p>
            <p className="text-[#8B7F73]">{m.reasons.join(' · ')}</p>
            <p className="text-[#A89D91]">Source: {m.cost.source}</p>
          </div>
        ))}
      </div>
      <div>
        <p className="font-medium text-[#8B7F73] mb-1">Assumptions</p>
        <ul className="space-y-1">
          {r.assumptions.map((a) => (
            <li key={a} className={a.startsWith('⚠') ? 'text-amber-700' : ''}>{a}</li>
          ))}
        </ul>
      </div>
      <div>
        <p className="font-medium text-[#8B7F73] mb-1">Approved suppliers</p>
        {r.shortlist.suppliers.length === 0 && <p className="text-[#A89D91]">No approved supplier has done this before.</p>}
        {r.shortlist.suppliers.map((s) => (
          <div key={s.supplier_id} className="mb-2">
            <p>
              <span className="font-medium">{s.supplier}</span>
              {s.best_quote && ` · $${s.best_quote.unit_price}`}
              {s.best_quote?.lead_time_days && `, ${s.best_quote.lead_time_days} days`}
            </p>
            {s.evidence.map((e) => (
              <p key={e.text} className="text-[#8B7F73]" title={`Source: ${e.source}`}>{e.text}</p>
            ))}
          </div>
        ))}
        {r.shortlist.non_approved_left_out > 0 && (
          <p className="text-[#A89D91]">{r.shortlist.non_approved_left_out} non-approved supplier(s) left out.</p>
        )}
      </div>
    </div>
  );
}

/** Thin slice: drop a STEP/PDF → BOM → estimate per line → approved-supplier shortlist. */
export function QuickEstimateCard() {
  const apiFetch = useApiClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [projectId, setProjectId] = useState('');
  const [report, setReport] = useState<QuickEstimateReport | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const { data: projects = [] } = useQuery<Project[]>({
    queryKey: ['projects'],
    queryFn: async () => {
      const res = await apiFetch('/api/projects/');
      if (!res.ok) throw new Error('Failed to load projects');
      return res.json();
    },
  });

  async function run(file: File) {
    setBusy(true);
    setError('');
    setReport(null);
    const body = new FormData();
    body.append('file', file);
    body.append('project_id', projectId);
    try {
      const res = await apiFetch('/api/parts/quick-estimate/', { method: 'POST', body });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? 'Estimate failed');
      setReport(data);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="bg-white border border-[#E8E0D3] rounded-xl p-5 space-y-4">
      <div className="flex items-center gap-3">
        <Upload className="w-5 h-5 text-[#8B7F73]" strokeWidth={1.5} />
        <div className="flex-1">
          <h2 className="text-sm font-medium text-[#2B2824]">Quick estimate</h2>
          <p className="text-xs text-[#8B7F73]">Drop a STEP or PDF: get its BOM, a cost per line and approved suppliers.</p>
        </div>
        <select
          value={projectId}
          onChange={(e) => setProjectId(e.target.value)}
          className="text-sm border border-[#E8E0D3] rounded-lg px-2 py-1.5 bg-white text-[#2B2824]"
        >
          <option value="">Choose project…</option>
          {projects.map((p) => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </select>
        <input
          ref={inputRef}
          type="file"
          accept=".step,.stp,.pdf"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            e.target.value = '';
            if (file) run(file);
          }}
        />
        <button
          onClick={() => inputRef.current?.click()}
          disabled={busy || !projectId}
          className="px-3 py-1.5 rounded-lg bg-[#2B2824] text-white text-sm hover:opacity-90 disabled:opacity-40"
        >
          Upload file
        </button>
      </div>

      {busy && (
        <p className="flex items-center gap-2 text-sm text-[#8B7F73]">
          <Loader2 className="w-4 h-4 animate-spin" /> Reading the file and estimating…
        </p>
      )}
      {error && <p className="text-sm text-[#DC2626]">{error}</p>}

      {report && (
        <div className="space-y-3">
          {report.uses_sample_data && (
            <p className="flex items-center gap-2 text-xs px-3 py-2 rounded-lg bg-amber-50 text-amber-800 border border-amber-200">
              <AlertTriangle className="w-3.5 h-3.5" /> These estimates use SAMPLE data, not real costs.
            </p>
          )}
          {report.bom.error && <p className="text-sm text-[#DC2626]">{report.bom.error}</p>}
          <div className="flex items-baseline gap-4 text-sm">
            <Link to={`/boms/${report.bom.id}`} className="font-medium text-[#2B2824] underline">
              {report.bom.reference}
            </Link>
            <span className="text-[#8B7F73]">{report.bom.source_name}</span>
            {report.bom.review_count > 0 && (
              <span className="text-amber-700">{report.bom.review_count} line(s) need review</span>
            )}
            <div className="flex-1" />
            <span className="text-[#2B2824]">
              Estimated total <span className="font-semibold">${report.total.extended_cost}</span>
            </span>
            {report.elapsed_ms !== undefined && (
              <span className="text-xs text-[#A89D91]">{(report.elapsed_ms / 1000).toFixed(1)} s</span>
            )}
          </div>

          <div className="border border-[#E8E0D3] rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-[#F9F9F9] border-b border-[#E8E0D3] text-xs text-[#8B7F73]">
                <tr>
                  <th className="px-3 py-2 text-left w-8">#</th>
                  <th className="px-3 py-2 text-left">Part</th>
                  <th className="px-3 py-2 text-right w-14">Qty</th>
                  <th className="px-3 py-2 text-right w-24">Unit est.</th>
                  <th className="px-3 py-2 text-right w-24">Line total</th>
                  <th className="px-3 py-2 text-left w-24">Confidence</th>
                  <th className="px-3 py-2 text-left w-48">Top approved supplier</th>
                </tr>
              </thead>
              <tbody>
                {report.rows.map((r) => (
                  <Fragment key={r.row_id}>
                    <tr
                      onClick={() => setOpen(open === r.row_id ? null : r.row_id)}
                      className="border-t border-[#F2EDE3] cursor-pointer hover:bg-[#FFFCF7]"
                    >
                      <td className="px-3 py-2 text-[#A89D91]">{r.line_no}</td>
                      <td className="px-3 py-2">
                        <span className="font-medium text-[#2B2824]">{r.part_number || '(no part number)'}</span>
                        <span className="text-[#8B7F73]"> · {r.description}</span>
                        {r.row.needs_review && <AlertTriangle className="inline w-3.5 h-3.5 ml-1 text-amber-600" />}
                      </td>
                      <td className="px-3 py-2 text-right" title={`Source: ${r.row.sources.quantity ?? '—'}`}>{r.quantity}</td>
                      <td className="px-3 py-2 text-right">{r.estimate ? `$${r.estimate.unit_cost}` : '—'}</td>
                      <td className="px-3 py-2 text-right font-medium">{r.estimate ? `$${r.estimate.extended_cost}` : '—'}</td>
                      <td className={`px-3 py-2 text-xs ${CONFIDENCE_STYLE[r.confidence]}`}>{r.confidence}</td>
                      <td className="px-3 py-2 text-xs text-[#2B2824]">{r.shortlist.suppliers[0]?.supplier ?? '—'}</td>
                    </tr>
                    {open === r.row_id && (
                      <tr>
                        <td colSpan={7}>
                          <RowDetails r={r} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-[#A89D91]">Click a line to see where each number came from.</p>
        </div>
      )}
    </div>
  );
}
