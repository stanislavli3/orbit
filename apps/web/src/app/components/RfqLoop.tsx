import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, CheckCircle2, Loader2, Mail, RefreshCw } from 'lucide-react';
import { useApiClient } from '../../api/client';
import type { RfqDraft, RfqStatus } from '../../api/types';

const STATUS_LABEL: Record<RfqStatus, string> = {
  draft: 'Draft',
  final: 'Final',
  sent: 'Sent — awaiting reply',
  send_failed: 'Send failed',
  needs_review: 'Needs review',
  quoted: 'Quoted',
  declined: 'Declined',
  info_requested: 'Info requested',
  escalated: 'Escalated',
};

const STATUS_STYLE: Partial<Record<RfqStatus, string>> = {
  send_failed: 'bg-red-50 text-[#DC2626]',
  needs_review: 'bg-amber-50 text-amber-700',
  info_requested: 'bg-amber-50 text-amber-700',
  escalated: 'bg-amber-50 text-amber-700',
  quoted: 'bg-green-50 text-green-700',
  declined: 'bg-[#F2EDE3] text-[#8B7F73]',
};

export function RfqStatusBadge({ status }: { status: RfqStatus }) {
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_STYLE[status] ?? 'bg-[#F2EDE3] text-[#8B7F73]'}`}>
      {STATUS_LABEL[status]}
    </span>
  );
}

function useRfqAction(onChange: (rfq: RfqDraft) => void) {
  const apiFetch = useApiClient();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ path, body }: { path: string; body?: object }) => {
      const res = await apiFetch(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        // A failed Gmail send still returns the record, so the error state shows on the card.
        if (data.rfq) onChange(data.rfq as RfqDraft);
        throw new Error(data.detail ?? 'Request failed.');
      }
      return data as RfqDraft;
    },
    onSuccess: onChange,
    onSettled: () => qc.invalidateQueries({ queryKey: ['rfqs'] }),
  });
}

/** SCRUM-33/34/35: send the RFQ from Gmail and follow the supplier thread. */
export function RfqLoopPanel({ rfq, onChange }: { rfq: RfqDraft; onChange: (rfq: RfqDraft) => void }) {
  const action = useRfqAction(onChange);
  const [kind, setKind] = useState('quote');
  const canSend = ['draft', 'final', 'send_failed'].includes(rfq.status);
  const threadOpen = ['sent', 'escalated', 'info_requested'].includes(rfq.status);
  const p = rfq.parsed_reply;

  return (
    <div className="bg-white border border-[#E8E0D3] rounded-xl p-5 space-y-3">
      <div className="flex items-center gap-3">
        <Mail className="w-4 h-4 text-[#8B7F73]" />
        <h3 className="text-sm font-medium text-[#2B2824]">Supplier email · {rfq.supplier_name || rfq.supplier_email || 'no supplier yet'}</h3>
        <RfqStatusBadge status={rfq.status} />
        {rfq.row_sourcing_status === 'sourced' && (
          <span className="text-xs text-green-700 flex items-center gap-1"><CheckCircle2 className="w-3.5 h-3.5" /> Line sourced</span>
        )}
      </div>

      {rfq.send_error && (
        <p className="text-sm text-[#DC2626] bg-red-50 rounded p-2">Gmail send failed: {rfq.send_error}</p>
      )}
      {rfq.needs_attention && (
        <p className="text-sm text-amber-800 bg-amber-50 rounded p-2 flex gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" /> {rfq.attention_reason}
        </p>
      )}
      {rfq.gmail_thread_id && (
        <p className="text-xs text-[#8B7F73]">
          Gmail thread {rfq.gmail_thread_id}
          {rfq.sent_at && ` · sent ${new Date(rfq.sent_at).toLocaleString()}`}
        </p>
      )}

      {rfq.reply_text && (
        <div className="text-sm space-y-1">
          <p className="text-xs text-[#8B7F73]">
            Supplier reply · read as <b>{p.intent}</b>
            {p.confidence != null && ` (confidence ${Math.round(p.confidence * 100)}%)`}
          </p>
          <pre className="whitespace-pre-wrap text-xs bg-[#F9F9F9] rounded p-2 text-[#4A4038]">{rfq.reply_text}</pre>
          {p.intent === 'quote' && (
            <p className="text-xs text-[#4A4038]">
              Price ${p.unit_price ?? '?'} · lead time {p.lead_time_days ?? '?'} days · MOQ {p.moq ?? '?'}
              {p.notes && ` · ${p.notes}`}
            </p>
          )}
        </div>
      )}

      {rfq.status === 'declined' && (
        <div className="text-xs text-[#4A4038]">
          Research resumed without {rfq.excluded_suppliers.join(', ')}.{' '}
          {rfq.next_suppliers.length
            ? <>Next suppliers to try: {rfq.next_suppliers.map((s) => s.supplier).join(', ')}.</>
            : 'No other approved supplier has history for this part — add one in Part history.'}
        </div>
      )}

      {action.error && <p className="text-xs text-[#DC2626]">{(action.error as Error).message}</p>}
      <div className="flex flex-wrap gap-2 items-center">
        {canSend && (
          <button
            onClick={() => action.mutate({ path: `/api/bom/rfqs/${rfq.id}/send/` })}
            disabled={action.isPending || !rfq.supplier_email}
            title={rfq.supplier_email ? '' : 'Save a supplier email first'}
            className="px-3 py-1.5 rounded-lg bg-[#2B2824] text-white text-sm hover:opacity-90 disabled:opacity-50"
          >
            {rfq.status === 'send_failed' ? 'Retry send' : 'Approve & send from Gmail'}
          </button>
        )}
        {rfq.status === 'needs_review' && <ReviewButtons rfq={rfq} onChange={onChange} />}
        {rfq.demo_mode && threadOpen && (
          <span className="flex gap-2 items-center border border-dashed border-[#E8E0D3] rounded-lg px-2 py-1">
            <span className="text-xs text-[#8B7F73]">Demo:</span>
            <select value={kind} onChange={(e) => setKind(e.target.value)} className="text-xs border border-[#E8E0D3] rounded px-1 py-0.5">
              <option value="quote">Clear quote</option>
              <option value="unclear">Unclear quote (review)</option>
              <option value="decline">Decline</option>
              <option value="info">Info request</option>
            </select>
            <button
              onClick={() => action.mutate({ path: `/api/bom/rfqs/${rfq.id}/simulate-reply/`, body: { kind } })}
              disabled={action.isPending}
              className="text-xs px-2 py-1 rounded bg-[#F2EDE3] text-[#4A4038]"
            >
              Simulate supplier reply
            </button>
          </span>
        )}
        {action.isPending && <Loader2 className="w-4 h-4 animate-spin text-[#8B7F73]" />}
      </div>
    </div>
  );
}

function ReviewButtons({ rfq, onChange }: { rfq: RfqDraft; onChange: (rfq: RfqDraft) => void }) {
  const action = useRfqAction(onChange);
  const [price, setPrice] = useState(rfq.parsed_reply.unit_price ?? '');
  const [lead, setLead] = useState(rfq.parsed_reply.lead_time_days?.toString() ?? '');
  const [moq, setMoq] = useState(rfq.parsed_reply.moq?.toString() ?? '');
  const path = `/api/bom/rfqs/${rfq.id}/review/`;
  const input = 'w-20 px-1.5 py-1 rounded border border-[#E8E0D3] text-xs';
  return (
    <span className="flex flex-wrap gap-2 items-center">
      <input className={input} value={price} onChange={(e) => setPrice(e.target.value)} placeholder="Price" />
      <input className={input} value={lead} onChange={(e) => setLead(e.target.value)} placeholder="Lead days" />
      <input className={input} value={moq} onChange={(e) => setMoq(e.target.value)} placeholder="MOQ" />
      <button
        onClick={() => action.mutate({
          path,
          body: { action: 'accept', unit_price: price, lead_time_days: lead ? Number(lead) : null, moq: moq ? Number(moq) : null },
        })}
        disabled={action.isPending || !price}
        className="text-xs px-2 py-1 rounded bg-green-700 text-white disabled:opacity-50"
      >
        Accept
      </button>
      <button
        onClick={() => action.mutate({ path, body: { action: 'reject' } })}
        disabled={action.isPending}
        className="text-xs px-2 py-1 rounded border border-[#E8E0D3] text-[#4A4038]"
      >
        Reject
      </button>
      {action.error && <span className="text-xs text-[#DC2626]">{(action.error as Error).message}</span>}
    </span>
  );
}

/** Human-review queue: low-confidence parses wait here instead of auto-committing. */
export function RfqReviewQueue() {
  const apiFetch = useApiClient();
  const qc = useQueryClient();
  const { data = [] } = useQuery<RfqDraft[]>({
    queryKey: ['rfqs', 'needs_review'],
    queryFn: async () => {
      const res = await apiFetch('/api/bom/rfqs/?status=needs_review');
      if (!res.ok) throw new Error('Could not load the review queue.');
      return res.json();
    },
  });
  if (!data.length) return null;
  const refresh = () => void qc.invalidateQueries({ queryKey: ['rfqs'] });
  return (
    <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 space-y-2">
      <h3 className="text-sm font-medium text-amber-900">Supplier replies to review ({data.length})</h3>
      {data.map((rfq) => (
        <div key={rfq.id} className="text-sm space-y-1 border-t border-amber-200 pt-2">
          <p className="text-[#2B2824]">
            {rfq.supplier_name || rfq.supplier_email} · {rfq.part_number} ({rfq.bom_reference})
          </p>
          <p className="text-xs text-[#4A4038] whitespace-pre-wrap">{rfq.reply_text}</p>
          <ReviewButtons rfq={rfq} onChange={refresh} />
        </div>
      ))}
    </div>
  );
}

/** Every RFQ for this BOM, so thread state survives a reload. */
export function RfqList({ bomId, onOpen }: { bomId: number; onOpen: (rfq: RfqDraft) => void }) {
  const apiFetch = useApiClient();
  const qc = useQueryClient();
  const { data = [] } = useQuery<RfqDraft[]>({
    queryKey: ['rfqs', 'bom', bomId],
    queryFn: async () => {
      const res = await apiFetch(`/api/bom/rfqs/?bom=${bomId}`);
      if (!res.ok) throw new Error('Could not load RFQs.');
      return res.json();
    },
  });
  const poll = useMutation({
    mutationFn: async () => {
      const res = await apiFetch('/api/bom/rfqs/poll/', { method: 'POST' });
      if (!res.ok) throw new Error('Could not check Gmail for replies.');
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ['rfqs'] }),
  });
  if (!data.length) return null;
  return (
    <div className="bg-white border border-[#E8E0D3] rounded-xl p-5 space-y-2">
      <div className="flex items-center gap-3">
        <h3 className="text-sm font-medium text-[#2B2824]">RFQs for this BOM</h3>
        <button
          onClick={() => poll.mutate()}
          disabled={poll.isPending}
          className="ml-auto text-xs flex items-center gap-1 px-2 py-1 rounded border border-[#E8E0D3] text-[#4A4038]"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${poll.isPending ? 'animate-spin' : ''}`} /> Check for replies
        </button>
      </div>
      {poll.error && <p className="text-xs text-[#DC2626]">{(poll.error as Error).message}</p>}
      <ul className="divide-y divide-[#F2EDE3]">
        {data.map((rfq) => (
          <li key={rfq.id} className="py-1.5 flex items-center gap-3 text-sm">
            <button onClick={() => onOpen(rfq)} className="text-[#2B2824] hover:underline">
              RFQ #{rfq.id} · {rfq.part_number || 'part'}
            </button>
            <span className="text-xs text-[#8B7F73]">{rfq.supplier_name || rfq.supplier_email || '—'}</span>
            <RfqStatusBadge status={rfq.status} />
            {rfq.needs_attention && <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />}
          </li>
        ))}
      </ul>
    </div>
  );
}
