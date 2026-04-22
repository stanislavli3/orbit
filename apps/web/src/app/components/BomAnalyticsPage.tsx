/**
 * BomAnalyticsPage — run-scoped analytics deck.
 *
 * Route:  /bom/:id/analytics
 *
 * Thin wrapper around <BomAnalyticsDeck> that fetches a single run by id.
 */

import { useNavigate, useParams } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, Loader2, AlertTriangle } from 'lucide-react';
import { useApiClient } from '../../api/client';
import type { BomResearchRun } from '../../api/types';
import { BomAnalyticsDeck, Squiggle, PAPER } from './BomAnalyticsDeck';

export function BomAnalyticsPage() {
  const { id } = useParams<{ id: string }>();
  const runId = id ? Number(id) : null;
  const apiFetch = useApiClient();
  const navigate = useNavigate();

  const { data: run, isLoading, error } = useQuery<BomResearchRun>({
    queryKey: ['bom-run', runId],
    queryFn: async () => {
      const res = await apiFetch(`/api/bom/runs/${runId}/`);
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
    enabled: runId !== null,
  });

  if (runId === null || Number.isNaN(runId)) {
    return (
      <div className="flex-1 flex items-center justify-center" style={{ background: PAPER.base }}>
        <div className="text-sm" style={{ color: PAPER.inkSoft }}>Invalid run id.</div>
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
              onClick={() => navigate(`/bom/${runId}`)}
              className="w-9 h-9 rounded-lg flex items-center justify-center transition-colors flex-shrink-0 mt-1"
              style={{ background: PAPER.card, border: `1px solid ${PAPER.fold}` }}
              title="Back to run"
            >
              <ArrowLeft className="w-4 h-4" strokeWidth={1.5} style={{ color: PAPER.inkSoft }} />
            </button>
            <div className="min-w-0">
              <p className="text-[10px] font-display uppercase tracking-[0.22em]" style={{ color: PAPER.stamp }}>
                BOM Analytics
              </p>
              <h1 className="font-display text-[30px] leading-[1.1] font-medium tracking-tight" style={{ color: PAPER.ink }}>
                Bill-of-Materials Review
              </h1>
              <div className="mt-0.5"><Squiggle width={180} /></div>
              <p className="text-[12px] italic mt-1.5" style={{ color: PAPER.inkSoft }}>
                Prepared for Run №{runId} · {new Date().toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}
              </p>
            </div>
          </div>
          <span
            className="text-[10px] font-display uppercase tracking-[0.2em] px-3 py-1.5 self-start rotate-[-2deg]"
            style={{ color: PAPER.brick, border: `1.5px solid ${PAPER.brick}`, borderRadius: '3px' }}
          >
            Confidential · Draft
          </span>
        </div>
      </div>

      <div className="max-w-[1400px] mx-auto px-8 py-8">
        {isLoading && (
          <div className="flex items-center justify-center py-24 gap-2">
            <Loader2 className="w-4 h-4 animate-spin" style={{ color: PAPER.inkSoft }} />
            <span className="text-sm" style={{ color: PAPER.inkSoft }}>Loading run data…</span>
          </div>
        )}
        {error && (
          <div className="rounded-[10px] p-4 flex items-start gap-3" style={{ background: 'rgba(182, 63, 42, 0.08)', border: `1.5px solid ${PAPER.brick}` }}>
            <AlertTriangle className="w-5 h-5 flex-shrink-0 mt-0.5" style={{ color: PAPER.brick }} />
            <p className="text-sm" style={{ color: PAPER.ink }}>Could not load this run.</p>
          </div>
        )}
        {run && <BomAnalyticsDeck run={run} />}
      </div>
    </div>
  );
}
