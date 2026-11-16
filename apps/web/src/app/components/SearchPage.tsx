import { useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { Loader2, Search } from 'lucide-react';
import { TopBar } from './TopBar';
import { useApiClient } from '../../api/client';
import type { SearchResponse } from '../../api/types';

const GROUP_LABEL: Record<keyof SearchResponse['groups'], string> = {
  files: 'Files',
  bom_rows: 'BOM rows',
  parts: 'Parts & past costs',
  quotes: 'Quotes',
  suppliers: 'Suppliers',
};

/** SCRUM-24: one search across files, structured BOMs and cost history, grouped and cited. */
export function SearchPage() {
  const apiFetch = useApiClient();
  const [params, setParams] = useSearchParams();
  const q = params.get('q') ?? '';
  const [input, setInput] = useState(q);

  const { data, isFetching, error } = useQuery<SearchResponse>({
    queryKey: ['search', q],
    enabled: q.trim().length > 0,
    queryFn: async () => {
      const res = await apiFetch(`/api/assistant/search/?q=${encodeURIComponent(q)}`);
      if (!res.ok) throw new Error('Search failed.');
      return res.json();
    },
  });

  return (
    <div className="flex-1 flex flex-col h-full bg-[#F9F9F9]">
      <TopBar title="Search" subtitle="One search across your files, BOMs, part costs, quotes and suppliers." />
      <div className="flex-1 overflow-y-auto px-8 py-8 space-y-6 max-w-5xl">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setParams(input.trim() ? { q: input.trim() } : {});
          }}
          className="flex items-center gap-2 bg-white border border-[#E8E0D3] rounded-xl px-4 py-2"
        >
          <Search className="w-4 h-4 text-[#8B7F73]" />
          <input
            autoFocus
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="e.g. ORB-1042, aluminum bracket, anodized…"
            className="flex-1 bg-transparent text-sm focus:outline-none"
          />
          {isFetching && <Loader2 className="w-4 h-4 animate-spin text-[#8B7F73]" />}
        </form>
        {error && <p className="text-sm text-[#DC2626]">{(error as Error).message}</p>}
        {data && data.total === 0 && <p className="text-sm text-[#8B7F73]">No results for “{data.query}”.</p>}
        {data &&
          (Object.keys(GROUP_LABEL) as (keyof SearchResponse['groups'])[]).map((g) =>
            data.groups[g].length === 0 ? null : (
              <section key={g} className="space-y-2">
                <h2 className="text-xs font-medium uppercase tracking-wide text-[#8B7F73]">
                  {GROUP_LABEL[g]} ({data.groups[g].length})
                </h2>
                <div className="bg-white border border-[#E8E0D3] rounded-xl divide-y divide-[#F2EDE3]">
                  {data.groups[g].map((h) => (
                    <Link key={`${h.type}-${h.id}`} to={h.link} className="block px-4 py-3 hover:bg-[#FFFCF7]">
                      <p className="text-sm font-medium text-[#2B2824]">{h.title}</p>
                      {h.snippet && <p className="text-xs text-[#4A4038] mt-0.5">{h.snippet}</p>}
                      <p className="text-[11px] text-[#A89D91] mt-1">Source: {h.citation}</p>
                    </Link>
                  ))}
                </div>
              </section>
            ),
          )}
      </div>
    </div>
  );
}
