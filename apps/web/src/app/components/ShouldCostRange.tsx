import { useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import { useApiClient } from '../../api/client';
import type { CostRange, PriceFlag, PriceFlagSummary } from '../../api/types';

/** SCRUM-73: "likely $X ($low–$high)" with the data behind it on hover. */
export function CostRangeCell({ range }: { range: CostRange }) {
  const title = [range.method, ...range.similar_parts.map((p) => `${p.part_number} $${p.unit_cost} · ${p.source}`), ...range.rates].join('\n');
  return (
    <span title={title} className="text-xs whitespace-nowrap">
      <span className="text-[#8B7F73]">likely </span>
      <span className="font-medium text-[#2B2824]">${range.likely}</span>
      <span className="text-[#8B7F73]"> (${range.low}–${range.high})</span>
    </span>
  );
}

/** The data behind the range, for expanded row details. */
export function CostRangeDetails({ range }: { range: CostRange }) {
  return (
    <div>
      <p className="font-medium text-[#8B7F73] mb-1">Should-cost: low ${range.low} / likely ${range.likely} / high ${range.high}</p>
      <p className="mb-1">{range.method}</p>
      {range.similar_parts.map((p) => (
        <p key={p.part_number} className="text-[#8B7F73]">
          {p.part_number} · ${p.unit_cost} · {Math.round(p.similarity * 100)}% similar · Source: {p.source}
        </p>
      ))}
      <ul className="mt-1 space-y-1">
        {range.rates.map((b) => (
          <li key={b} className={b.startsWith('⚠') ? 'text-amber-700' : ''}>{b}</li>
        ))}
      </ul>
    </div>
  );
}

export function PriceFlagBadge({ flag }: { flag: PriceFlag | null }) {
  if (!flag || flag.level === 'ok') return null;
  const below = flag.level === 'far_below';
  return (
    <p className={`mt-0.5 flex items-start gap-1 text-[11px] ${below ? 'text-[#DC2626]' : 'text-amber-700'}`}>
      <AlertTriangle className="w-3 h-3 mt-0.5 shrink-0" />
      {flag.message}
    </p>
  );
}

export function PriceFlagSummaryText({ summary }: { summary: PriceFlagSummary }) {
  const n = summary.far_below + summary.far_above;
  if (!summary.priced) return null;
  return (
    <span className={n ? 'text-[#DC2626]' : 'text-[#8B7F73]'} title={`Flagged when an entered price is more than ${Math.round(summary.margin * 100)}% outside the should-cost range`}>
      {n} price surprise{n !== 1 ? 's' : ''} ({summary.far_below} far below, {summary.far_above} far above) of {summary.priced} priced
    </span>
  );
}

/** SCRUM-74: editable prototype / entered unit price for one BOM line. */
export function EnteredPriceInput({
  rowId, price, note, onSaved,
}: { rowId: number; price: string | null; note: string; onSaved: () => void }) {
  const apiFetch = useApiClient();
  const [value, setValue] = useState(price ?? '');
  const [source, setSource] = useState(note);
  const [error, setError] = useState('');

  async function save() {
    if (value === (price ?? '') && source === note) return;
    setError('');
    const res = await apiFetch(`/api/parts/rows/${rowId}/price/`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ entered_price: value === '' ? null : value, entered_price_note: source }),
    });
    if (!res.ok) {
      setError((await res.json()).detail ?? 'Could not save');
      return;
    }
    onSaved();
  }

  return (
    <div className="flex flex-col gap-0.5" onClick={(e) => e.stopPropagation()}>
      <input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onBlur={save}
        placeholder="$ entered"
        inputMode="decimal"
        className="w-20 text-xs border border-[#E8E0D3] rounded px-1.5 py-0.5"
      />
      <input
        value={source}
        onChange={(e) => setSource(e.target.value)}
        onBlur={save}
        placeholder="source, e.g. Amazon"
        className="w-28 text-[11px] border border-[#E8E0D3] rounded px-1.5 py-0.5 text-[#8B7F73]"
      />
      {error && <span className="text-[11px] text-[#DC2626]">{error}</span>}
    </div>
  );
}
