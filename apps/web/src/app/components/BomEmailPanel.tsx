import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Mail,
  Send,
  CheckCircle2,
  X,
  ChevronDown,
  ChevronUp,
  Trash2,
  Pencil,
  CheckCheck,
  Loader2,
  MessageSquareText,
} from 'lucide-react';
import { toast } from 'sonner';
import { useApiClient } from '../../api/client';
import type {
  BomQuestion,
  BomResearchRun,
  TeamRequest,
  TeamRequestApproveAllResponse,
  TeamRequestDraftResponse,
  TeamRequestPollResponse,
} from '../../api/types';

export interface BomEmailComposerTrigger {
  type: 'question' | 'request';
  nonce: number;
  question?: BomQuestion;
  requestId?: number;
}

interface Props {
  runId: number | null;
  runStatus?: BomResearchRun['status'];
  composerTrigger: BomEmailComposerTrigger | null;
  onComposerTriggerHandled: () => void;
}

function formatDateTime(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

function statusPresentation(request: TeamRequest) {
  if (request.status === 'answered') {
    return { label: '✅ Answered', detail: request.answered_at ? `answered ${formatDateTime(request.answered_at)}` : 'reply parsed', className: 'border-emerald-200 bg-emerald-50 text-emerald-700' };
  }
  if (request.is_overdue) {
    return { label: '🔴 No reply', detail: request.sent_at ? `${hoursAgo(request.sent_at)}h ago` : 'overdue', className: 'border-red-200 bg-red-50 text-red-700' };
  }
  if (request.status === 'sent' || request.status === 'follow_up') {
    return { label: '🟡 Waiting', detail: request.sent_at ? `sent ${hoursAgo(request.sent_at)}h ago` : 'waiting', className: 'border-amber-200 bg-amber-50 text-amber-700' };
  }
  if (request.status === 'approved') {
    return { label: 'Approved', detail: 'ready to send', className: 'border-sky-200 bg-sky-50 text-sky-700' };
  }
  return { label: 'Draft', detail: 'not approved', className: 'border-slate-200 bg-slate-50 text-slate-700' };
}

function hoursAgo(iso: string): number {
  const delta = Date.now() - new Date(iso).getTime();
  return Math.max(0, Math.round(delta / (1000 * 60 * 60)));
}

function ComposerModal({
  request,
  isOpen,
  onClose,
  allDrafts,
  onSelectRequest,
  onSave,
  onApprove,
  onApproveAll,
  onSend,
  onDiscard,
}: {
  request: TeamRequest | null;
  isOpen: boolean;
  onClose: () => void;
  allDrafts: TeamRequest[];
  onSelectRequest: (requestId: number) => void;
  onSave: (payload: Partial<TeamRequest>) => Promise<void>;
  onApprove: () => Promise<void>;
  onApproveAll: () => Promise<void>;
  onSend: () => Promise<void>;
  onDiscard: () => Promise<void>;
}) {
  const [draftState, setDraftState] = useState({
    recipient_name: request?.recipient_name ?? '',
    recipient_email: request?.recipient_email ?? '',
    email_subject: request?.email_subject ?? '',
    email_body: request?.email_body ?? '',
  });
  const [editing, setEditing] = useState(request?.status === 'draft');

  if (!isOpen || !request) return null;

  const canEdit = request.status === 'draft';
  const canApprove = request.status === 'draft';
  const canSend = request.status === 'approved';
  const sentState = request.status === 'sent' || request.status === 'follow_up' || request.status === 'answered';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 px-4">
      <div className="w-full max-w-6xl rounded-3xl border border-[#E6E6E6] bg-white shadow-2xl overflow-hidden">
        <div className="flex items-center justify-between border-b border-[#F0F0F0] px-6 py-4">
          <div>
            <p className="text-sm font-semibold text-[#111111]">Email Draft Composer</p>
            <p className="text-[12px] text-[#6B7280] mt-0.5">Edit, approve, and send team-request drafts for this BOM run.</p>
          </div>
          <button onClick={onClose} className="rounded-lg p-2 text-[#6B7280] hover:bg-[#F4F4F4] hover:text-[#111111]">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="grid min-h-[620px] lg:grid-cols-[280px_minmax(0,1fr)]">
          <aside className="border-r border-[#F0F0F0] bg-[#FBFBFB] p-4">
            <div className="flex items-center justify-between gap-2 mb-3">
              <div>
                <p className="text-[12px] font-semibold uppercase tracking-[0.16em] text-[#6B7280]">Drafts</p>
                <p className="text-[11px] text-[#9CA3AF] mt-1">{allDrafts.length} total</p>
              </div>
              {allDrafts.some((item) => item.status === 'draft') && (
                <button
                  type="button"
                  onClick={() => void onApproveAll()}
                  className="inline-flex items-center gap-1 rounded-lg border border-[#E6E6E6] bg-white px-2.5 py-1.5 text-[11px] font-medium text-[#111111] hover:border-[#111111]"
                >
                  <CheckCheck className="w-3.5 h-3.5" />
                  Approve all
                </button>
              )}
            </div>
            <div className="space-y-2">
              {allDrafts.map((item) => {
                const status = statusPresentation(item);
                const active = item.id === request.id;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => onSelectRequest(item.id)}
                    className={`w-full rounded-2xl border px-3 py-3 text-left transition-colors ${
                      active ? 'border-[#111111] bg-white' : 'border-[#E6E6E6] bg-white hover:border-[#BDBDBD]'
                    }`}
                  >
                    <p className="text-[12px] font-medium text-[#111111]">{item.recipient_name}</p>
                    <p className="text-[11px] text-[#6B7280] mt-0.5 line-clamp-2">{item.question}</p>
                    <span className={`mt-2 inline-flex rounded-full border px-2 py-0.5 text-[10px] font-medium ${status.className}`}>
                      {status.label}
                    </span>
                  </button>
                );
              })}
            </div>
          </aside>

          <div className="p-6 space-y-5">
            <div className="flex items-start justify-between gap-4 flex-wrap">
              <div>
                <p className="text-lg font-semibold text-[#111111]">{request.recipient_name}</p>
                <p className="text-[12px] text-[#6B7280] mt-1">{request.question}</p>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                <span className={`inline-flex rounded-full border px-2.5 py-1 text-[11px] font-medium ${statusPresentation(request).className}`}>
                  {statusPresentation(request).label}
                </span>
                {sentState && (
                  <span className="text-[12px] text-[#6B7280]">
                    ✅ Sent at {formatDateTime(request.sent_at)}
                  </span>
                )}
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <label className="block">
                <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.16em] text-[#6B7280]">Recipient name</span>
                <input
                  value={draftState.recipient_name}
                  disabled={!editing || !canEdit}
                  onChange={(event) => setDraftState((current) => ({ ...current, recipient_name: event.target.value }))}
                  className="w-full rounded-xl border border-[#E6E6E6] px-3 py-2.5 text-sm focus:border-[#111111] focus:outline-none disabled:bg-[#F8F8F8] disabled:text-[#6B7280]"
                />
              </label>
              <label className="block">
                <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.16em] text-[#6B7280]">Recipient email</span>
                <input
                  value={draftState.recipient_email}
                  disabled={!editing || !canEdit}
                  onChange={(event) => setDraftState((current) => ({ ...current, recipient_email: event.target.value }))}
                  className="w-full rounded-xl border border-[#E6E6E6] px-3 py-2.5 text-sm focus:border-[#111111] focus:outline-none disabled:bg-[#F8F8F8] disabled:text-[#6B7280]"
                />
              </label>
            </div>

            <label className="block">
              <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.16em] text-[#6B7280]">Subject</span>
              <input
                value={draftState.email_subject}
                disabled={!editing || !canEdit}
                onChange={(event) => setDraftState((current) => ({ ...current, email_subject: event.target.value }))}
                className="w-full rounded-xl border border-[#E6E6E6] px-3 py-2.5 text-sm focus:border-[#111111] focus:outline-none disabled:bg-[#F8F8F8] disabled:text-[#6B7280]"
              />
            </label>

            <label className="block">
              <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.16em] text-[#6B7280]">Body</span>
              <textarea
                value={draftState.email_body}
                disabled={!editing || !canEdit}
                onChange={(event) => setDraftState((current) => ({ ...current, email_body: event.target.value }))}
                className="min-h-[260px] w-full rounded-2xl border border-[#E6E6E6] px-4 py-3 text-sm leading-relaxed focus:border-[#111111] focus:outline-none disabled:bg-[#F8F8F8] disabled:text-[#6B7280]"
              />
            </label>

            {request.status === 'answered' && request.response && (
              <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3">
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-emerald-700">Parsed reply</p>
                <p className="text-sm text-emerald-900 mt-2 whitespace-pre-wrap">{request.response}</p>
              </div>
            )}

            <div className="flex items-center justify-between gap-3 flex-wrap border-t border-[#F0F0F0] pt-4">
              <div className="flex items-center gap-2 flex-wrap">
                <button
                  type="button"
                  onClick={() => setEditing((current) => !current)}
                  disabled={!canEdit}
                  className="inline-flex items-center gap-2 rounded-xl border border-[#E6E6E6] px-3 py-2 text-sm text-[#111111] hover:border-[#111111] disabled:cursor-not-allowed disabled:text-[#9CA3AF]"
                >
                  <Pencil className="w-4 h-4" />
                  {editing ? 'Editing' : 'Edit'}
                </button>
                <button
                  type="button"
                  onClick={() => void onSave(draftState)}
                  disabled={!canEdit}
                  className="inline-flex items-center gap-2 rounded-xl border border-[#E6E6E6] px-3 py-2 text-sm text-[#111111] hover:border-[#111111] disabled:cursor-not-allowed disabled:text-[#9CA3AF]"
                >
                  Save
                </button>
                <button
                  type="button"
                  onClick={() => void onApprove()}
                  disabled={!canApprove}
                  className="inline-flex items-center gap-2 rounded-xl bg-[#111111] px-3 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-[#D1D5DB]"
                >
                  <CheckCircle2 className="w-4 h-4" />
                  Approve
                </button>
                <button
                  type="button"
                  onClick={() => void onDiscard()}
                  disabled={!canEdit}
                  className="inline-flex items-center gap-2 rounded-xl border border-red-200 px-3 py-2 text-sm text-red-700 hover:border-red-400 disabled:cursor-not-allowed disabled:text-[#9CA3AF]"
                >
                  <Trash2 className="w-4 h-4" />
                  Discard
                </button>
              </div>
              <button
                type="button"
                onClick={() => void onSend()}
                disabled={!canSend}
                className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-[#C7CDD4]"
              >
                <Send className="w-4 h-4" />
                Send
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function BomEmailPanel({
  runId,
  runStatus,
  composerTrigger,
  onComposerTriggerHandled,
}: Props) {
  const apiFetch = useApiClient();
  const queryClient = useQueryClient();
  const [selectedRequestId, setSelectedRequestId] = useState<number | null>(null);
  const [composerOpen, setComposerOpen] = useState(false);
  const [expandedRows, setExpandedRows] = useState<number[]>([]);

  const { data: emails = [], isLoading } = useQuery<TeamRequest[]>({
    queryKey: ['bom-emails', runId],
    queryFn: async () => {
      const response = await apiFetch(`/api/bom/runs/${runId}/emails/`);
      if (!response.ok) {
        throw new Error('Failed to load BOM emails');
      }
      return response.json();
    },
    enabled: !!runId,
  });

  const outstanding = emails.some((request) =>
    ['draft', 'approved', 'sent', 'follow_up'].includes(request.status),
  );

  useEffect(() => {
    if (!runId || !outstanding) return;
    const timer = window.setInterval(async () => {
      try {
        const pollResponse = await apiFetch(`/api/bom/runs/${runId}/emails/poll/`, {
          method: 'POST',
        });
        if (pollResponse.ok) {
          const payload = (await pollResponse.json()) as TeamRequestPollResponse;
          if (payload.count > 0) {
            toast.success('New BOM email reply received.');
          }
        }
      } catch {
        // best-effort background refresh
      } finally {
        void queryClient.invalidateQueries({ queryKey: ['bom-emails', runId] });
        void queryClient.invalidateQueries({ queryKey: ['bom-run', runId] });
      }
    }, 30000);
    return () => window.clearInterval(timer);
  }, [apiFetch, outstanding, queryClient, runId]);

  useEffect(() => {
    if (composerTrigger == null || runId == null) return;

    const trigger = composerTrigger;
    let cancelled = false;
    async function handleTrigger() {
      try {
        if (trigger.type === 'question' && trigger.question) {
          const response = await apiFetch(`/api/bom/runs/${runId}/draft-emails/`, {
            method: 'POST',
          });
          if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.detail ?? 'Failed to generate email drafts');
          }
          const payload = (await response.json()) as TeamRequestDraftResponse;
          const matching =
            payload.requests.find((request) => request.question_key === trigger.question?.id)
            ?? payload.requests.find((request) => request.question === trigger.question?.text)
            ?? null;
          void queryClient.invalidateQueries({ queryKey: ['bom-emails', runId] });
          if (!cancelled && matching) {
            setSelectedRequestId(matching.id);
            setComposerOpen(true);
          } else if (!cancelled) {
            toast.message('Drafts generated for outstanding team questions.');
          }
        } else if (trigger.type === 'request' && trigger.requestId) {
          if (!cancelled) {
            setSelectedRequestId(trigger.requestId);
            setComposerOpen(true);
          }
        }
      } catch (error) {
        toast.error(error instanceof Error ? error.message : 'Failed to open draft composer');
      } finally {
        onComposerTriggerHandled();
      }
    }

    void handleTrigger();
    return () => {
      cancelled = true;
    };
  }, [apiFetch, composerTrigger, onComposerTriggerHandled, queryClient, runId]);

  useEffect(() => {
    if (selectedRequestId) return;
    const firstDraft = emails.find((request) => request.status === 'draft') ?? emails[0];
    if (firstDraft) {
      setSelectedRequestId(firstDraft.id);
    }
  }, [emails, selectedRequestId]);

  const selectedRequest = useMemo(
    () => emails.find((request) => request.id === selectedRequestId) ?? null,
    [emails, selectedRequestId],
  );

  const persistMutation = useMutation({
    mutationFn: async ({
      requestId,
      payload,
    }: {
      requestId: number;
      payload: Partial<TeamRequest>;
    }) => {
      const response = await apiFetch(`/api/bom/runs/${runId}/emails/${requestId}/`, {
        method: 'PATCH',
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail ?? 'Failed to save draft');
      }
      return response.json() as Promise<TeamRequest>;
    },
    onSuccess: (request) => {
      toast.success('Draft updated.');
      setSelectedRequestId(request.id);
      void queryClient.invalidateQueries({ queryKey: ['bom-emails', runId] });
    },
    onError: (error: Error) => toast.error(error.message),
  });

  async function postAction(path: string, successMessage: string) {
    const response = await apiFetch(path, { method: 'POST' });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail ?? successMessage);
    }
    return response;
  }

  async function handleApprove() {
    if (!selectedRequest || runId == null) return;
    try {
      await postAction(`/api/bom/runs/${runId}/emails/${selectedRequest.id}/approve/`, 'Failed to approve draft');
      toast.success('Draft approved.');
      await queryClient.invalidateQueries({ queryKey: ['bom-emails', runId] });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to approve draft');
    }
  }

  async function handleApproveAll() {
    if (runId == null) return;
    try {
      const response = await postAction(`/api/bom/runs/${runId}/emails/approve-all/`, 'Failed to approve all drafts');
      const payload = (await response.json()) as TeamRequestApproveAllResponse;
      toast.success(`Approved ${payload.approved_count} draft${payload.approved_count === 1 ? '' : 's'}.`);
      await queryClient.invalidateQueries({ queryKey: ['bom-emails', runId] });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to approve all drafts');
    }
  }

  async function handleSend() {
    if (!selectedRequest || runId == null) return;
    try {
      await postAction(`/api/bom/runs/${runId}/emails/${selectedRequest.id}/send/`, 'Failed to send email');
      toast.success('Email sent.');
      await queryClient.invalidateQueries({ queryKey: ['bom-emails', runId] });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to send email');
    }
  }

  async function handleDiscard() {
    if (!selectedRequest || runId == null) return;
    try {
      const response = await apiFetch(`/api/bom/runs/${runId}/emails/${selectedRequest.id}/`, {
        method: 'DELETE',
      });
      if (!response.ok && response.status !== 204) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail ?? 'Failed to discard draft');
      }
      toast.success('Draft discarded.');
      setComposerOpen(false);
      setSelectedRequestId(null);
      await queryClient.invalidateQueries({ queryKey: ['bom-emails', runId] });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to discard draft');
    }
  }

  async function handleFollowUp(requestId: number) {
    if (runId == null) return;
    try {
      const response = await postAction(`/api/bom/runs/${runId}/emails/${requestId}/follow-up/`, 'Failed to generate follow-up');
      const payload = (await response.json()) as TeamRequest;
      setSelectedRequestId(payload.id);
      setComposerOpen(true);
      toast.success('Follow-up draft generated. Approve it before sending.');
      await queryClient.invalidateQueries({ queryKey: ['bom-emails', runId] });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to generate follow-up');
    }
  }

  const shouldShow = !!runId && (emails.length > 0 || composerOpen || runStatus === 'awaiting_team_input');
  if (!shouldShow) return null;

  return (
    <>
      <section className="mb-8 rounded-3xl border border-[#E6E6E6] bg-white overflow-hidden">
        <div className="px-6 py-5 border-b border-[#F0F0F0] bg-[linear-gradient(135deg,#FDFCFB_0%,#F8FAFC_100%)]">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-[#E6E6E6] bg-white px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#6B7280]">
                <Mail className="w-3.5 h-3.5" />
                Team Requests
              </div>
              <h2 className="text-xl font-semibold text-[#111111] mt-3">Email Status Tracker</h2>
              <p className="text-sm text-[#6B7280] mt-1">
                Track BOM clarification emails, approvals, replies, and follow-ups in one place.
              </p>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              {isLoading && <Loader2 className="w-4 h-4 animate-spin text-[#6B7280]" />}
              {emails.some((request) => request.status === 'draft') && (
                <button
                  type="button"
                  onClick={() => setComposerOpen(true)}
                  className="inline-flex items-center gap-2 rounded-xl border border-[#E6E6E6] bg-white px-4 py-2.5 text-sm font-medium text-[#111111] hover:border-[#111111]"
                >
                  <MessageSquareText className="w-4 h-4" />
                  Open drafts
                </button>
              )}
            </div>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px]">
            <thead className="bg-[#FAFAFA] border-b border-[#EFEFEF]">
              <tr className="text-left text-[11px] font-semibold uppercase tracking-[0.16em] text-[#6B7280]">
                <th className="px-4 py-3">Contact</th>
                <th className="px-4 py-3">Question</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {emails.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-4 py-10 text-center text-sm text-[#6B7280]">
                    No team email drafts have been created for this BOM run yet.
                  </td>
                </tr>
              )}
              {emails.map((request) => {
                const expanded = expandedRows.includes(request.id);
                const status = statusPresentation(request);
                return (
                  <>
                    <tr key={request.id} className="border-b border-[#F0F0F0] align-top">
                      <td className="px-4 py-4">
                        <div>
                          <p className="text-sm font-medium text-[#111111]">{request.recipient_name}</p>
                          <p className="text-[12px] text-[#6B7280] mt-1">{request.recipient_email}</p>
                        </div>
                      </td>
                      <td className="px-4 py-4 text-sm text-[#374151]">{request.question}</td>
                      <td className="px-4 py-4">
                        <div className="space-y-2">
                          <span className={`inline-flex rounded-full border px-2.5 py-1 text-[11px] font-medium ${status.className}`}>
                            {status.label}
                          </span>
                          <p className="text-[12px] text-[#6B7280]">{status.detail}</p>
                        </div>
                      </td>
                      <td className="px-4 py-4">
                        <div className="flex items-center justify-end gap-2 flex-wrap">
                          {(request.status === 'draft' || request.status === 'approved') && (
                            <button
                              type="button"
                              onClick={() => {
                                setSelectedRequestId(request.id);
                                setComposerOpen(true);
                              }}
                              className="rounded-lg border border-[#E6E6E6] px-3 py-1.5 text-[12px] font-medium text-[#111111] hover:border-[#111111]"
                            >
                              View draft
                            </button>
                          )}
                          {request.is_overdue && (
                            <button
                              type="button"
                              onClick={() => void handleFollowUp(request.id)}
                              className="rounded-lg border border-red-200 px-3 py-1.5 text-[12px] font-medium text-red-700 hover:border-red-400"
                            >
                              Send follow-up
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={() =>
                              setExpandedRows((current) =>
                                expanded ? current.filter((value) => value !== request.id) : [...current, request.id],
                              )
                            }
                            className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-[#E6E6E6] text-[#6B7280] hover:border-[#111111] hover:text-[#111111]"
                          >
                            {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                          </button>
                        </div>
                      </td>
                    </tr>
                    {expanded && (
                      <tr key={`${request.id}-timeline`} className="border-b border-[#F0F0F0] bg-[#FBFBFB]">
                        <td colSpan={4} className="px-4 py-4">
                          <div className="rounded-2xl border border-[#E6E6E6] bg-white p-4">
                            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[#6B7280]">Timeline</p>
                            <div className="mt-3 grid gap-3 md:grid-cols-4">
                              <div className="rounded-xl border border-[#E6E6E6] bg-[#FAFAFA] px-3 py-3">
                                <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#6B7280]">Draft created</p>
                                <p className="text-[12px] text-[#111111] mt-2">{formatDateTime(request.created_at)}</p>
                              </div>
                              <div className="rounded-xl border border-[#E6E6E6] bg-[#FAFAFA] px-3 py-3">
                                <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#6B7280]">Approved</p>
                                <p className="text-[12px] text-[#111111] mt-2">
                                  {request.approved_at ? formatDateTime(request.approved_at) : 'Pending'}
                                </p>
                              </div>
                              <div className="rounded-xl border border-[#E6E6E6] bg-[#FAFAFA] px-3 py-3">
                                <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#6B7280]">Sent</p>
                                <p className="text-[12px] text-[#111111] mt-2">{request.sent_at ? formatDateTime(request.sent_at) : 'Not sent yet'}</p>
                              </div>
                              <div className="rounded-xl border border-[#E6E6E6] bg-[#FAFAFA] px-3 py-3">
                                <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#6B7280]">Answered</p>
                                <p className="text-[12px] text-[#111111] mt-2">{request.answered_at ? formatDateTime(request.answered_at) : 'Awaiting reply'}</p>
                              </div>
                            </div>
                            {request.response && (
                              <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3">
                                <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-emerald-700">Reply text</p>
                                <p className="mt-2 whitespace-pre-wrap text-sm text-emerald-900">{request.response}</p>
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <ComposerModal
        key={selectedRequest?.id ?? 'empty'}
        request={selectedRequest}
        isOpen={composerOpen}
        onClose={() => setComposerOpen(false)}
        allDrafts={emails}
        onSelectRequest={(requestId) => setSelectedRequestId(requestId)}
        onSave={async (payload) => {
          if (!selectedRequest) return;
          await persistMutation.mutateAsync({ requestId: selectedRequest.id, payload });
        }}
        onApprove={handleApprove}
        onApproveAll={handleApproveAll}
        onSend={handleSend}
        onDiscard={handleDiscard}
      />
    </>
  );
}
