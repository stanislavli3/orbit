import { useState } from 'react';
import { Link, useParams } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, Loader2 } from 'lucide-react';
import { TopBar } from './TopBar';
import { useApiClient } from '../../api/client';
import type { Bom, BomCitation, BomComparison, BomNeighbours } from '../../api/types';

const METHOD_LABEL: Record<BomNeighbours['method'], string> = {
  placement_distance: 'by placement distance (STEP positions)',
  assembly_structure: 'by assembly structure (same parent; no positions in the file)',
  not_in_assembly: 'part not found in the assembly',
};

function Cite({ c }: { c: BomCitation }) {
  return (
    <Link to={`/boms/${c.bom_id}`} className="text-xs text-[#8B7F73] underline hover:text-[#2B2824]">
      {c.reference} · {c.source_name}{c.line_no ? `, row ${c.line_no}` : ''}
    </Link>
  );
}

function Recheck({ n }: { n?: BomNeighbours }) {
  if (!n) return null;
  return (
    <div className="mt-2 text-xs text-[#5A524A]">
      <span className="font-medium">Parts to recheck</span> <span className="text-[#A89D91]">— {METHOD_LABEL[n.method]}</span>
      {n.parts.length === 0 ? (
        <span className="text-[#A89D91]"> · none</span>
      ) : (
        <ul className="mt-1 flex flex-wrap gap-1.5">
          {n.parts.map((p) => (
            <li key={p.part_number} title={p.reason} className="px-2 py-0.5 rounded-full bg-[#F2EDE3]">
              {p.part_number}{p.distance !== null ? ` · ${p.distance}` : ''}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

const card = 'bg-white border border-[#E8E0D3] rounded-xl p-4';

export function BomComparePage() {
  const { id } = useParams();
  const apiFetch = useApiClient();
  const [base, setBase] = useState('');
  const [target, setTarget] = useState('');
  const [radius, setRadius] = useState('50');

  const { data: boms = [] } = useQuery<Bom[]>({
    queryKey: ['boms', 'project', id],
    queryFn: async () => {
      const res = await apiFetch(`/api/bom/structured/?project_id=${id}`);
      if (!res.ok) throw new Error('Could not load BOMs.');
      return res.json();
    },
  });

  const ready = !!base && !!target && base !== target;
  const { data: cmp, isFetching, error } = useQuery<BomComparison>({
    queryKey: ['bom-compare', base, target, radius],
    enabled: ready,
    queryFn: async () => {
      const res = await apiFetch(`/api/bom/structured/compare/?base=${base}&target=${target}&radius=${Number(radius) || 50}`);
      if (!res.ok) throw new Error('Could not compare these BOMs.');
      return res.json();
    },
  });

  const picker = (value: string, set: (v: string) => void, label: string) => (
    <label className="text-xs text-[#8B7F73] flex flex-col gap-1">
      {label}
      <select value={value} onChange={(e) => set(e.target.value)} className="text-sm px-2 py-1.5 rounded-lg border border-[#E8E0D3] bg-white text-[#2B2824] min-w-64">
        <option value="">Choose a BOM…</option>
        {boms.filter((b) => b.status !== 'failed' && b.status !== 'extracting').map((b) => (
          <option key={b.id} value={b.id}>{b.reference} · {b.source_name}</option>
        ))}
      </select>
    </label>
  );

  return (
    <div className="flex-1 flex flex-col h-full bg-[#F9F9F9]">
      <TopBar title="Compare versions" subtitle="Pick two BOMs to see what changed, conflicting callouts, and parts to recheck." />
      <div className="flex-1 overflow-y-auto px-8 py-8 space-y-4">
        <div className="flex flex-wrap items-end gap-4">
          {picker(base, setBase, 'Older version')}
          {picker(target, setTarget, 'Newer version')}
          <label className="text-xs text-[#8B7F73] flex flex-col gap-1">
            Neighbour distance
            <input value={radius} onChange={(e) => setRadius(e.target.value)} className="w-24 text-sm px-2 py-1.5 rounded-lg border border-[#E8E0D3] bg-white" />
          </label>
          {isFetching && <Loader2 className="w-5 h-5 animate-spin text-[#8B7F73]" />}
        </div>
        {error && <p className="text-sm text-[#DC2626]">{(error as Error).message}</p>}

        {cmp && (
          <>
            <p className="text-sm text-[#2B2824]">
              <span className="font-medium">Summary:</span> {cmp.summary}
              {!cmp.assembly && <span className="text-[#A89D91]"> · neither version is a STEP assembly, so no neighbours</span>}
            </p>

            <section className={card}>
              <h2 className="text-sm font-medium text-[#2B2824] mb-2 flex items-center gap-1.5">
                <AlertTriangle className="w-4 h-4 text-amber-600" /> Conflicts across project files ({cmp.conflicts.length})
              </h2>
              {cmp.conflicts.length === 0 && <p className="text-xs text-[#A89D91]">No conflicting part numbers, revisions, materials or tolerances.</p>}
              <ul className="space-y-2">
                {cmp.conflicts.map((f, i) => (
                  <li key={i} className="text-sm border-l-2 border-amber-400 pl-3">
                    <div className="text-[#2B2824]"><span className="font-medium">{f.title}</span> — {f.detail}</div>
                    <div className="flex flex-wrap gap-x-3">{f.citations.map((c, j) => <Cite key={j} c={c} />)}</div>
                  </li>
                ))}
              </ul>
            </section>

            <section className={card}>
              <h2 className="text-sm font-medium text-[#2B2824] mb-2">Changed ({cmp.changed.length})</h2>
              <ul className="space-y-3">
                {cmp.changed.map((c) => (
                  <li key={c.part_number} className="text-sm">
                    <div className="font-medium text-[#2B2824]">{c.part_number}</div>
                    <ul className="text-xs text-[#5A524A]">
                      {c.fields.map((f) => (
                        <li key={f.field}>{f.field}: <s className="text-[#A89D91]">{String(f.before) || '—'}</s> → {String(f.after) || '—'}</li>
                      ))}
                    </ul>
                    <div className="flex gap-3">{c.rows.map((r, j) => <Cite key={j} c={r} />)}</div>
                    <Recheck n={cmp.recheck[c.part_number]} />
                  </li>
                ))}
              </ul>
            </section>

            <div className="grid grid-cols-2 gap-4">
              {(['added', 'removed'] as const).map((k) => (
                <section key={k} className={card}>
                  <h2 className="text-sm font-medium text-[#2B2824] mb-2 capitalize">{k} ({cmp[k].length})</h2>
                  <ul className="space-y-3">
                    {cmp[k].map((p) => (
                      <li key={p.part_number} className="text-sm">
                        <div className="font-medium text-[#2B2824]">{p.part_number}</div>
                        <Cite c={p.row} />
                        <Recheck n={cmp.recheck[p.part_number]} />
                      </li>
                    ))}
                  </ul>
                </section>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
