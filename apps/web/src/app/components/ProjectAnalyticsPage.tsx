/**
 * ProjectAnalyticsPage — BOM analytics scoped to a project.
 *
 * Route:  /project/:id/analytics
 *
 * Lists all BOM runs for the project, defaults to the most recent completed
 * one, and lets the user switch between them. Reuses <BomAnalyticsDeck>.
 */

import { useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, Loader2, AlertTriangle, Package, ChevronDown } from 'lucide-react';
import { useApiClient } from '../../api/client';
import type { BomResearchRun, Project } from '../../api/types';
import { BomAnalyticsDeck, Squiggle, PAPER, computeAnalyticsSummary, formatCurrency } from './BomAnalyticsDeck';

function runLabel(run: BomResearchRun): string {
  const d = new Date(run.created_at);
  const when = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  return `Run №${run.id} · ${when}`;
}

export function ProjectAnalyticsPage() {
  const { id } = useParams<{ id: string }>();
  const projectId = id ? Number(id) : null;
  const apiFetch = useApiClient();
  const navigate = useNavigate();
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);

  const { data: project } = useQuery<Project>({
    queryKey: ['project', projectId],
    queryFn: async () => {
      const res = await apiFetch(`/api/projects/${projectId}/`);
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
    enabled: projectId !== null,
  });

  // List of runs (metadata only; line_items come via run detail)
  const { data: runs = [], isLoading: runsLoading } = useQuery<BomResearchRun[]>({
    queryKey: ['bom-runs', 'project', projectId],
    queryFn: async () => {
      const res = await apiFetch(`/api/bom/runs/?project_id=${projectId}`);
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
    enabled: projectId !== null,
  });

  // Default selection: latest completed run, else latest of any status.
  const defaultRunId = useMemo(() => {
    if (!runs.length) return null;
    const sorted = [...runs].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
    const completed = sorted.find((r) => r.status === 'completed');
    return (completed ?? sorted[0]).id;
  }, [runs]);

  const effectiveRunId = selectedRunId ?? defaultRunId;

  // Full detail (line_items + quotes) for the selected run
  const { data: selectedRun, isLoading: runLoading, error: runError } = useQuery<BomResearchRun>({
    queryKey: ['bom-run', effectiveRunId],
    queryFn: async () => {
      const res = await apiFetch(`/api/bom/runs/${effectiveRunId}/`);
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
    enabled: effectiveRunId !== null,
  });

  const currentLabel = runs.find((r) => r.id === effectiveRunId)
    ? runLabel(runs.find((r) => r.id === effectiveRunId)!)
    : 'Select a run';

  if (projectId === null || Number.isNaN(projectId)) {
    return (
      <div className="flex-1 flex items-center justify-center" style={{ background: PAPER.base }}>
        <div className="text-sm" style={{ color: PAPER.inkSoft }}>Invalid project id.</div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-auto" style={{ background: PAPER.base }}>
      {/* Header */}
      <div className="relative" style={{ background: PAPER.highlight, borderBottom: `1px solid ${PAPER.fold}` }}>
        <div className="max-w-[1400px] mx-auto px-8 py-6 flex items-start justify-between gap-4">
          <div className="flex items-start gap-3 min-w-0">
            <button
              onClick={() => navigate(`/project/${projectId}`)}
              className="w-9 h-9 rounded-lg flex items-center justify-center transition-colors flex-shrink-0 mt-1"
              style={{ background: PAPER.card, border: `1px solid ${PAPER.fold}` }}
              title="Back to project"
            >
              <ArrowLeft className="w-4 h-4" strokeWidth={1.5} style={{ color: PAPER.inkSoft }} />
            </button>
            <div className="min-w-0">
              <p className="text-[10px] font-display uppercase tracking-[0.22em]" style={{ color: PAPER.stamp }}>
                BOM Analytics
              </p>
              <h1 className="font-display text-[30px] leading-[1.1] font-medium tracking-tight" style={{ color: PAPER.ink }}>
                {project?.name ?? 'Project'}
              </h1>
              <div className="mt-0.5"><Squiggle width={200} /></div>
              <p className="text-[12px] italic mt-1.5" style={{ color: PAPER.inkSoft }}>
                {runs.length > 0
                  ? `${runs.length} BOM run${runs.length !== 1 ? 's' : ''} on record · prepared ${new Date().toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}`
                  : 'No BOM runs yet for this project'}
              </p>
            </div>
          </div>

          {/* Run picker */}
          {runs.length > 0 && (
            <div className="relative self-start">
              <button
                onClick={() => setPickerOpen((v) => !v)}
                className="flex items-center gap-2 px-3 py-2 rounded-lg text-[12px]"
                style={{ background: PAPER.card, border: `1px solid ${PAPER.fold}`, color: PAPER.ink }}
              >
                <Package className="w-3.5 h-3.5" style={{ color: PAPER.stamp }} strokeWidth={1.75} />
                <span>{currentLabel}</span>
                <ChevronDown className="w-3.5 h-3.5" style={{ color: PAPER.inkFaded }} />
              </button>
              {pickerOpen && (
                <div
                  className="absolute right-0 mt-1 w-64 rounded-lg z-50 overflow-hidden"
                  style={{ background: PAPER.card, border: `1px solid ${PAPER.fold}`, boxShadow: '0 8px 24px rgba(61, 47, 31, 0.12)' }}
                >
                  {[...runs].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()).map((r) => {
                    const active = r.id === effectiveRunId;
                    return (
                      <button
                        key={r.id}
                        onClick={() => { setSelectedRunId(r.id); setPickerOpen(false); }}
                        className="w-full text-left px-3 py-2 flex items-center justify-between gap-2 transition-colors"
                        style={{
                          background: active ? PAPER.highlight : 'transparent',
                          borderBottom: `1px dashed ${PAPER.fold}`,
                          color: PAPER.ink,
                        }}
                      >
                        <div>
                          <p className="text-[12px] font-display font-medium">Run №{r.id}</p>
                          <p className="text-[10px] italic" style={{ color: PAPER.inkSoft }}>
                            {new Date(r.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                            {' · '}{r.status}
                          </p>
                        </div>
                        {active && <span className="text-[9px] uppercase tracking-wider font-display" style={{ color: PAPER.stamp }}>viewing</span>}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="max-w-[1400px] mx-auto px-8 py-8">
        {runsLoading && (
          <div className="flex items-center justify-center py-24 gap-2">
            <Loader2 className="w-4 h-4 animate-spin" style={{ color: PAPER.inkSoft }} />
            <span className="text-sm" style={{ color: PAPER.inkSoft }}>Loading runs…</span>
          </div>
        )}

        {!runsLoading && runs.length === 0 && (
          <div
            className="rounded-[14px] p-10 text-center"
            style={{ background: PAPER.card, border: `1px solid ${PAPER.fold}` }}
          >
            <Package className="w-10 h-10 mx-auto mb-3" style={{ color: PAPER.inkFaded }} strokeWidth={1.5} />
            <h2 className="font-display text-[18px] font-medium mb-2" style={{ color: PAPER.ink }}>
              No BOM runs yet for this project
            </h2>
            <p className="text-[12px] italic mb-5 max-w-md mx-auto" style={{ color: PAPER.inkSoft }}>
              Analytics appear once you generate your first BOM. Head back to the project and click "Generate BOM".
            </p>
            <button
              onClick={() => navigate(`/project/${projectId}`)}
              className="px-4 py-2 rounded-lg text-sm inline-flex items-center gap-2"
              style={{ background: PAPER.ink, color: PAPER.base }}
            >
              Back to project
            </button>
          </div>
        )}

        {runs.length > 0 && runLoading && !selectedRun && (
          <div className="flex items-center justify-center py-24 gap-2">
            <Loader2 className="w-4 h-4 animate-spin" style={{ color: PAPER.inkSoft }} />
            <span className="text-sm" style={{ color: PAPER.inkSoft }}>Loading run details…</span>
          </div>
        )}

        {runError && (
          <div className="rounded-[10px] p-4 flex items-start gap-3" style={{ background: 'rgba(182, 63, 42, 0.08)', border: `1.5px solid ${PAPER.brick}` }}>
            <AlertTriangle className="w-5 h-5 flex-shrink-0 mt-0.5" style={{ color: PAPER.brick }} />
            <p className="text-sm" style={{ color: PAPER.ink }}>Could not load the selected run.</p>
          </div>
        )}

        {selectedRun && <BomAnalyticsDeck run={selectedRun} />}
      </div>
    </div>
  );
}

// Re-export for use in CTA cards
export { computeAnalyticsSummary, formatCurrency };
