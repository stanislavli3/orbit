import { useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, Loader2, Wrench, Mail, Radio, AlertCircle, BarChart3 } from 'lucide-react';
import { useApiClient } from '../../api/client';
import type { BomResearchRun, Project, BomQuestion } from '../../api/types';
import { BomLivePanel } from './BomLivePanel';
import { BomQuestionsPanel } from './BomQuestionsPanel';
import { BomEmailPanel, type BomEmailComposerTrigger } from './BomEmailPanel';
import { BomResultsPanel } from './BomResultsPanel';
import { PageTitle } from './PageTitle';

function statusChip(status: BomResearchRun['status']): { label: string; className: string; spin: boolean } {
  switch (status) {
    case 'gathering_inputs':    return { label: 'Gathering inputs',    className: 'bg-slate-100 text-slate-700 border-slate-200',      spin: false };
    case 'researching':         return { label: 'Researching',         className: 'bg-blue-50 text-blue-700 border-blue-200',          spin: true  };
    case 'generating_report':   return { label: 'Generating report',   className: 'bg-indigo-50 text-indigo-700 border-indigo-200',    spin: true  };
    case 'awaiting_team_input': return { label: 'Awaiting input',      className: 'bg-amber-50 text-amber-700 border-amber-200',       spin: false };
    case 'completed':           return { label: 'Completed',           className: 'bg-emerald-50 text-emerald-700 border-emerald-200', spin: false };
    case 'failed':              return { label: 'Failed',              className: 'bg-red-50 text-red-700 border-red-200',             spin: false };
  }
}

export function BomRunPage() {
  const { id } = useParams<{ id: string }>();
  const runId = id ? Number(id) : null;
  const apiFetch = useApiClient();
  const navigate = useNavigate();

  const [questionsOpen, setQuestionsOpen] = useState(false);
  const [liveOpen, setLiveOpen] = useState(false);
  const [emailComposerTrigger, setEmailComposerTrigger] = useState<BomEmailComposerTrigger | null>(null);

  const { data: run, isLoading, error } = useQuery<BomResearchRun>({
    queryKey: ['bom-run', runId],
    queryFn: async () => {
      const res = await apiFetch(`/api/bom/runs/${runId}/`);
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
    enabled: runId !== null,
    refetchInterval: (query) => {
      const data = query.state.data as BomResearchRun | undefined;
      return data && (data.status === 'researching' || data.status === 'generating_report') ? 3_000 : false;
    },
  });

  const { data: project } = useQuery<Project>({
    queryKey: ['project', run?.project],
    queryFn: async () => {
      const res = await apiFetch(`/api/projects/${run!.project}/`);
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
    enabled: !!run?.project,
  });

  const runs = useMemo(() => (run ? [run] : []), [run]);
  const chip = run ? statusChip(run.status) : null;

  if (runId === null || Number.isNaN(runId)) {
    return (
      <div className="flex-1 flex items-center justify-center bg-[#FAF7F2]">
        <div className="text-sm text-[#8B7F73]">Invalid run id.</div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-auto bg-[#FAF7F2]">
      <div className="max-w-[1400px] mx-auto px-8 py-8">
        {/* Header */}
        <div className="flex items-center gap-3 mb-4">
          <button
            onClick={() => navigate('/bom')}
            className="w-9 h-9 rounded-lg border border-[#E8E0D3] bg-[#FFFCF7] hover:bg-white flex items-center justify-center transition-colors"
            title="Back to BOM runs"
          >
            <ArrowLeft className="w-4 h-4 text-[#4A4038]" strokeWidth={1.5} />
          </button>
        </div>

        <PageTitle
          title={`BOM Run #${runId}`}
          subtitle={
            <div className="flex items-center gap-3 flex-wrap">
              {chip && (
                <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium border ${chip.className}`}>
                  {chip.spin && <Loader2 className="w-3 h-3 animate-spin" />}
                  {chip.label}
                </span>
              )}
              <span className="text-[#8B7F73]">
                {project
                  ? <>Project: <button className="underline underline-offset-2 decoration-dotted hover:text-[#2B2824]" onClick={() => navigate(`/project/${project.id}`)}>{project.name}</button></>
                  : run ? `Project #${run.project}` : '—'}
              </span>
            </div>
          }
          icon={
            <div className="w-11 h-11 rounded-xl flex items-center justify-center bg-[#2B2824] rotate-[-1.5deg]" style={{ boxShadow: '0 2px 10px rgba(74, 58, 38, 0.08)' }}>
              <Wrench className="w-5 h-5 text-[#FAF7F2]" strokeWidth={1.5} />
            </div>
          }
          actions={
            <>
              <button
                onClick={() => setQuestionsOpen(true)}
                disabled={!run}
                className="px-3 py-2 rounded-lg border border-[#E8E0D3] bg-[#FFFCF7] hover:bg-white text-sm text-[#2B2824] disabled:opacity-50 flex items-center gap-2 transition-colors"
              >
                <AlertCircle className="w-4 h-4" strokeWidth={1.5} />
                Questions
              </button>
              <button
                onClick={() => setLiveOpen(true)}
                disabled={!run}
                className="px-3 py-2 rounded-lg border border-[#E8E0D3] bg-[#FFFCF7] hover:bg-white text-sm text-[#2B2824] disabled:opacity-50 flex items-center gap-2 transition-colors"
              >
                <Radio className="w-4 h-4" strokeWidth={1.5} />
                Live feed
              </button>
              <button
                onClick={() => navigate(`/bom/${runId}/analytics`)}
                disabled={!run}
                className="px-3 py-2 rounded-lg text-sm disabled:opacity-50 flex items-center gap-2 transition-colors"
                style={{ background: '#2B2824', color: '#FAF7F2' }}
              >
                <BarChart3 className="w-4 h-4" strokeWidth={1.75} />
                View analytics
              </button>
            </>
          }
        />

        {/* Main content */}
        {isLoading && !run ? (
          <div className="flex items-center justify-center py-24 text-sm text-[#8B7F73] gap-2">
            <Loader2 className="w-4 h-4 animate-spin" /> Loading run…
          </div>
        ) : error || !run ? (
          <div className="flex items-center justify-center py-24 text-sm text-[#8B7F73]">
            Could not load this run.
          </div>
        ) : (
          <>
            <div className="flex items-center gap-2 text-xs text-[#8B7F73] mb-2">
              <Mail className="w-3.5 h-3.5" strokeWidth={1.75} />
              <span>Team emails</span>
            </div>
            <BomEmailPanel
              runId={run.id}
              runStatus={run.status}
              composerTrigger={emailComposerTrigger}
              onComposerTriggerHandled={() => setEmailComposerTrigger(null)}
            />

            <BomResultsPanel
              runs={runs}
              selectedRun={run}
              selectedRunId={run.id}
              onSelectRun={() => { /* single-run view; selection is a no-op */ }}
            />
          </>
        )}
      </div>

      {/* Overlays */}
      {questionsOpen && run && (
        <BomQuestionsPanel
          runId={run.id}
          onClose={() => setQuestionsOpen(false)}
          onComplete={() => setQuestionsOpen(false)}
          onDraftEmail={(question: BomQuestion) => {
            setEmailComposerTrigger({ type: 'question', question, nonce: Date.now() });
          }}
        />
      )}

      {liveOpen && run && (
        <BomLivePanel
          runId={run.id}
          initialRun={run}
          onClose={() => setLiveOpen(false)}
        />
      )}
    </div>
  );
}
