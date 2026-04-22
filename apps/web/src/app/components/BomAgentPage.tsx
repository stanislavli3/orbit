import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { Loader2, CheckCircle2, AlertCircle, Clock, Wrench, Package } from 'lucide-react';
import { useApiClient } from '../../api/client';
import type { BomResearchRun, Project } from '../../api/types';
import { PageTitle } from './PageTitle';

type StatusKey = BomResearchRun['status'];

const STATUS_CFG: Record<StatusKey, { label: string; className: string; Icon: React.ComponentType<{ className?: string }> }> = {
  gathering_inputs:    { label: 'Gathering inputs',    className: 'bg-slate-100 text-slate-700 border-slate-200',           Icon: Clock },
  researching:         { label: 'Researching',         className: 'bg-blue-50 text-blue-700 border-blue-200',               Icon: Loader2 },
  generating_report:   { label: 'Generating report',   className: 'bg-indigo-50 text-indigo-700 border-indigo-200',         Icon: Loader2 },
  awaiting_team_input: { label: 'Awaiting input',      className: 'bg-amber-50 text-amber-700 border-amber-200',            Icon: Clock },
  completed:           { label: 'Completed',           className: 'bg-emerald-50 text-emerald-700 border-emerald-200',      Icon: CheckCircle2 },
  failed:              { label: 'Failed',              className: 'bg-red-50 text-red-700 border-red-200',                  Icon: AlertCircle },
};

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

const FILTERS = [
  { value: 'all',    label: 'All'       },
  { value: 'active', label: 'Active'    },
  { value: 'done',   label: 'Completed' },
  { value: 'failed', label: 'Failed'    },
] as const;

type FilterValue = typeof FILTERS[number]['value'];

function matchesFilter(run: BomResearchRun, f: FilterValue): boolean {
  if (f === 'all') return true;
  if (f === 'done') return run.status === 'completed';
  if (f === 'failed') return run.status === 'failed';
  return run.status !== 'completed' && run.status !== 'failed';
}

export function BomAgentPage() {
  const apiFetch = useApiClient();
  const navigate = useNavigate();
  const [filter, setFilter] = useState<FilterValue>('all');

  const { data: runs = [], isLoading: runsLoading } = useQuery<BomResearchRun[]>({
    queryKey: ['bom-runs', 'all'],
    queryFn: async () => {
      const res = await apiFetch('/api/bom/runs/');
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
    refetchInterval: (query) => {
      const data = query.state.data as BomResearchRun[] | undefined;
      return data?.some((r) => r.status === 'researching' || r.status === 'generating_report') ? 10_000 : false;
    },
  });

  const { data: projects = [] } = useQuery<Project[]>({
    queryKey: ['projects'],
    queryFn: async () => {
      const res = await apiFetch('/api/projects/');
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
  });

  const projectsById = useMemo(() => {
    const m = new Map<number, Project>();
    for (const p of projects) m.set(p.id, p);
    return m;
  }, [projects]);

  const visible = useMemo(() => {
    return runs
      .filter((r) => matchesFilter(r, filter))
      .slice()
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
  }, [runs, filter]);

  return (
    <div className="flex-1 overflow-auto bg-[#FAF7F2]">
      <div className="max-w-[1400px] mx-auto px-8 py-8">
        <PageTitle
          title="BOM Agent"
          subtitle="All bill-of-materials research runs across your projects"
          icon={
            <div className="w-11 h-11 rounded-xl flex items-center justify-center bg-[#2B2824] rotate-[-1.5deg]" style={{ boxShadow: '0 2px 10px rgba(74, 58, 38, 0.08)' }}>
              <Wrench className="w-5 h-5 text-[#FAF7F2]" strokeWidth={1.5} />
            </div>
          }
        />

        <div className="flex items-center gap-2 mb-4">
          {FILTERS.map((f) => {
            const active = filter === f.value;
            const count = runs.filter((r) => matchesFilter(r, f.value)).length;
            return (
              <button
                key={f.value}
                onClick={() => setFilter(f.value)}
                className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                  active
                    ? 'bg-[#2B2824] text-white border-[#2B2824]'
                    : 'bg-white text-[#8B7F73] border-[#E8E0D3] hover:bg-[#FFFCF7]'
                }`}
              >
                {f.label} <span className="opacity-60 ml-1">{count}</span>
              </button>
            );
          })}
        </div>

        <div className="bg-white rounded-xl border border-[#E8E0D3] overflow-hidden">
          {runsLoading ? (
            <div className="flex items-center justify-center py-16 text-[#8B7F73] text-sm gap-2">
              <Loader2 className="w-4 h-4 animate-spin" /> Loading runs…
            </div>
          ) : visible.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <Package className="w-8 h-8 text-[#C4B8A8] mb-3" strokeWidth={1.5} />
              <p className="text-sm text-[#8B7F73] max-w-sm">
                {filter === 'all'
                  ? 'No BOM runs yet. Open a project and click "Generate BOM" to start.'
                  : `No ${FILTERS.find((f) => f.value === filter)?.label.toLowerCase()} runs.`}
              </p>
            </div>
          ) : (
            <table className="w-full">
              <thead className="bg-[#FFFCF7] border-b border-[#E8E0D3]">
                <tr>
                  <th className="text-left text-[10px] font-semibold uppercase tracking-wider text-[#8B7F73] px-4 py-3">Run</th>
                  <th className="text-left text-[10px] font-semibold uppercase tracking-wider text-[#8B7F73] px-4 py-3">Project</th>
                  <th className="text-left text-[10px] font-semibold uppercase tracking-wider text-[#8B7F73] px-4 py-3">Status</th>
                  <th className="text-left text-[10px] font-semibold uppercase tracking-wider text-[#8B7F73] px-4 py-3">Parts</th>
                  <th className="text-left text-[10px] font-semibold uppercase tracking-wider text-[#8B7F73] px-4 py-3">Created</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((run) => {
                  const project = projectsById.get(run.project);
                  const cfg = STATUS_CFG[run.status] ?? STATUS_CFG.gathering_inputs;
                  const spinning = run.status === 'researching' || run.status === 'generating_report';
                  return (
                    <tr
                      key={run.id}
                      onClick={() => navigate(`/bom/${run.id}`)}
                      className="border-b border-[#EEE6D8] last:border-b-0 hover:bg-[#FFFCF7] cursor-pointer transition-colors"
                    >
                      <td className="px-4 py-3 text-sm text-[#2B2824] font-medium">Run #{run.id}</td>
                      <td className="px-4 py-3 text-sm text-[#4A4038]">{project?.name ?? `Project #${run.project}`}</td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium border ${cfg.className}`}>
                          <cfg.Icon className={`w-3 h-3 ${spinning ? 'animate-spin' : ''}`} />
                          {cfg.label}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm text-[#4A4038]">{run.line_items.length}</td>
                      <td className="px-4 py-3 text-sm text-[#8B7F73]">{formatDate(run.created_at)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
