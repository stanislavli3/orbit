import { useState, useEffect } from 'react';
import { X, Mail, MessageSquare, Users, ChevronRight, Check, Loader2 } from 'lucide-react';
import { Link } from 'react-router';
import { useQuery, useMutation } from '@tanstack/react-query';
import { useApiClient } from '../../api/client';
import type { BomQuestion, BomQuestionsResponse, BomResearchRun } from '../../api/types';
import { toast } from 'sonner';

interface Props {
  runId: number;
  onClose: () => void;
  onComplete: (run: BomResearchRun) => void;
  onDraftEmail: (question: BomQuestion) => void;
}

// ── Single question renderer ──────────────────────────────────────────────────

function QuestionCard({
  question,
  answer,
  onChange,
  onDraftEmail,
}: {
  question: BomQuestion;
  answer: string | string[] | undefined;
  onChange: (val: string | string[]) => void;
  onDraftEmail: (question: BomQuestion) => void;
}) {
  const contact = question.matched_contact;

  return (
    <div className="space-y-3">
      {/* Question text */}
      <p className="text-sm font-medium text-[#111111] leading-snug">{question.text}</p>

      {/* Context file tag */}
      {question.context_file && (
        <span className="inline-block text-[11px] px-2 py-0.5 rounded bg-[#F4F4F4] text-[#6B7280] font-mono">
          {question.context_file}
        </span>
      )}

      {/* Single-select chips */}
      {question.type === 'single_select' && question.options && (
        <div className="flex flex-wrap gap-2">
          {question.options.map((opt) => (
            <button
              key={opt}
              type="button"
              onClick={() => onChange(opt)}
              className={`px-3 py-1.5 rounded-full text-sm border transition-colors ${
                answer === opt
                  ? 'border-[#111111] bg-[#111111] text-white'
                  : 'border-[#E6E6E6] text-[#374151] hover:border-[#111111]'
              }`}
            >
              {opt}
            </button>
          ))}
        </div>
      )}

      {/* Multi-select chips */}
      {question.type === 'multi_select' && question.options && (
        <div className="flex flex-wrap gap-2">
          {question.options.map((opt) => {
            const selected = Array.isArray(answer) && answer.includes(opt);
            return (
              <button
                key={opt}
                type="button"
                onClick={() => {
                  const current = Array.isArray(answer) ? answer : [];
                  onChange(
                    selected ? current.filter((v) => v !== opt) : [...current, opt],
                  );
                }}
                className={`px-3 py-1.5 rounded-full text-sm border transition-colors flex items-center gap-1.5 ${
                  selected
                    ? 'border-[#111111] bg-[#111111] text-white'
                    : 'border-[#E6E6E6] text-[#374151] hover:border-[#111111]'
                }`}
              >
                {selected && <Check className="w-3 h-3" />}
                {opt}
              </button>
            );
          })}
        </div>
      )}

      {/* Free text */}
      {question.type === 'text' && (
        <input
          type="text"
          value={typeof answer === 'string' ? answer : ''}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Type your answer… (optional)"
          className="w-full px-3 py-2 border border-[#E6E6E6] rounded-lg text-sm focus:outline-none focus:border-[#111111] transition-colors"
        />
      )}

      {/* Team contact suggestion */}
      {contact && (
        <div className="rounded-xl border border-[#E6E6E6] bg-[#FAFAFA] p-3 space-y-2">
          <div className="flex items-start gap-2">
            <div className="w-7 h-7 rounded-full bg-[#F4F4F4] flex items-center justify-center flex-shrink-0 text-[11px] font-semibold text-[#6B7280]">
              {contact.full_name.charAt(0)}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-[12px] font-medium text-[#111111]">{contact.full_name}</p>
              <p className="text-[11px] text-[#6B7280]">{contact.role}</p>
              <div className="flex flex-wrap gap-1 mt-1">
                {contact.expertise_tags.map((t) => (
                  <span key={t} className="px-1.5 py-0.5 rounded-full bg-[#F0F0F0] text-[10px] text-[#6B7280]">{t}</span>
                ))}
              </div>
            </div>
            <span className="flex items-center gap-1 text-[11px] text-[#9CA3AF]">
              {contact.preferred_channel === 'slack'
                ? <><MessageSquare className="w-3 h-3" /> Slack</>
                : <><Mail className="w-3 h-3" /> Email</>}
            </span>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => onDraftEmail(question)}
              className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 border border-[#E6E6E6] rounded-lg text-xs text-[#374151] hover:bg-white hover:border-[#111111] transition-colors"
            >
              <Mail className="w-3 h-3" />
              Draft email to {contact.full_name.split(' ')[0]}
            </button>
            {question.default && (
              <button
                type="button"
                onClick={() => onChange(question.default!)}
                className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 border border-[#E6E6E6] rounded-lg text-xs text-[#374151] hover:bg-white hover:border-[#111111] transition-colors"
              >
                Use default: {question.default}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main panel ────────────────────────────────────────────────────────────────

export function BomQuestionsPanel({ runId, onClose, onComplete, onDraftEmail }: Props) {
  const apiFetch = useApiClient();
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string | string[]>>({});

  const { data, isLoading, isError } = useQuery<BomQuestionsResponse>({
    queryKey: ['bom-questions', runId],
    queryFn: async () => {
      const res = await apiFetch(`/api/bom/runs/${runId}/questions/`);
      if (!res.ok) throw new Error('Failed to load questions');
      return res.json();
    },
  });

  // Pre-fill defaults on load
  useEffect(() => {
    if (!data) return;
    const defaults: Record<string, string | string[]> = {};
    for (const q of data.questions) {
      if (q.default !== undefined && q.default !== '' && !(q.id in answers)) {
        defaults[q.id] = q.type === 'multi_select' ? [q.default] : q.default;
      }
    }
    if (Object.keys(defaults).length > 0) {
      setAnswers((prev) => ({ ...defaults, ...prev }));
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);

  const submitMutation = useMutation({
    mutationFn: async () => {
      const res = await apiFetch(`/api/bom/runs/${runId}/inputs/`, {
        method: 'PATCH',
        body: JSON.stringify({ answers }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail ?? 'Failed to submit answers');
      }
      return res.json() as Promise<BomResearchRun>;
    },
    onSuccess: (run) => {
      toast.success('BOM research started — watch it live!');
      onComplete(run);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const questions = data?.questions ?? [];
  const total = questions.length;
  const current = questions[step];
  const answeredCount = questions.filter((q) => q.id in answers).length;

  function setAnswer(val: string | string[]) {
    if (!current) return;
    setAnswers((prev) => ({ ...prev, [current.id]: val }));
  }

  function handleNext() {
    if (step < total - 1) setStep((s) => s + 1);
    else submitMutation.mutate();
  }

  function handleBack() {
    setStep((s) => Math.max(0, s - 1));
  }

  const canAdvance =
    !current ||
    current.type === 'text' ||
    !!answers[current.id];

  return (
    <div className="fixed inset-0 z-40 flex items-stretch justify-end">
      {/* Backdrop */}
      <div className="flex-1 bg-black/20" onClick={onClose} />

      {/* Panel */}
      <div className="w-full max-w-lg bg-white flex flex-col h-full shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#F4F4F4]">
          <div>
            <h2 className="text-base font-semibold text-[#111111]">Generate BOM</h2>
            <p className="text-xs text-[#6B7280] mt-0.5">Answer a few questions to start research</p>
          </div>
          <button onClick={onClose} className="text-[#9CA3AF] hover:text-[#111111] transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Progress */}
        {total > 0 && (
          <div className="px-6 py-3 border-b border-[#F4F4F4]">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs text-[#6B7280]">
                Question {step + 1} of {total}
              </span>
              <span className="text-xs text-[#6B7280]">{answeredCount} answered</span>
            </div>
            <div className="h-1 bg-[#F4F4F4] rounded-full overflow-hidden">
              <div
                className="h-full bg-[#111111] rounded-full transition-all"
                style={{ width: `${((step + 1) / total) * 100}%` }}
              />
            </div>
          </div>
        )}

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-6">
          {isLoading && (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="w-6 h-6 animate-spin text-[#9CA3AF]" />
            </div>
          )}

          {isError && (
            <p className="text-sm text-red-600">Failed to load questions. Please close and try again.</p>
          )}

          {!isLoading && !isError && total === 0 && (
            <div className="text-center py-12">
              <Check className="w-10 h-10 mx-auto text-green-500 mb-3" />
              <p className="text-sm font-medium text-[#111111]">No questions needed!</p>
              <p className="text-xs text-[#6B7280] mt-1">Click Submit to start BOM research.</p>
            </div>
          )}

          {!isLoading && !isError && current && (
            <QuestionCard
              question={current}
              answer={answers[current.id]}
              onChange={setAnswer}
              onDraftEmail={onDraftEmail}
            />
          )}

          {/* No team contacts nudge */}
          {!isLoading && data && !data.has_team_contacts && (
            <div className="mt-6 rounded-xl border border-amber-200 bg-amber-50 p-4">
              <div className="flex items-start gap-3">
                <Users className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-medium text-amber-900">
                    No team contacts configured
                  </p>
                  <p className="text-xs text-amber-700 mt-0.5">
                    Add colleagues in Settings so the agent knows who to contact for missing specs.
                  </p>
                  <Link
                    to="/settings"
                    className="inline-flex items-center gap-1 mt-2 text-xs font-medium text-amber-900 underline underline-offset-2 hover:opacity-70"
                    onClick={onClose}
                  >
                    Go to Settings → Team
                    <ChevronRight className="w-3 h-3" />
                  </Link>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center gap-2 px-6 py-4 border-t border-[#F4F4F4]">
          {step > 0 && (
            <button
              onClick={handleBack}
              className="px-4 py-2 text-sm border border-[#E6E6E6] rounded-lg hover:bg-[#F4F4F4] transition-colors"
            >
              Back
            </button>
          )}
          <div className="flex-1" />
          {total === 0 ? (
            <button
              onClick={() => submitMutation.mutate()}
              disabled={submitMutation.isPending}
              className="px-5 py-2 text-sm bg-[#111111] text-white rounded-lg hover:bg-[#333333] disabled:opacity-50 transition-colors"
            >
              {submitMutation.isPending ? <><Loader2 className="w-4 h-4 animate-spin inline mr-1.5" />Starting…</> : 'Start research'}
            </button>
          ) : step < total - 1 ? (
            <button
              onClick={handleNext}
              disabled={!canAdvance}
              className="px-5 py-2 text-sm bg-[#111111] text-white rounded-lg hover:bg-[#333333] disabled:opacity-40 transition-colors flex items-center gap-1.5"
            >
              Next
              <ChevronRight className="w-4 h-4" />
            </button>
          ) : (
            <button
              onClick={handleNext}
              disabled={submitMutation.isPending}
              className="px-5 py-2 text-sm bg-[#111111] text-white rounded-lg hover:bg-[#333333] disabled:opacity-50 transition-colors"
            >
              {submitMutation.isPending ? <><Loader2 className="w-4 h-4 animate-spin inline mr-1.5" />Starting…</> : 'Submit answers'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
