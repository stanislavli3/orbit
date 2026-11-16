import { useState } from 'react';
import { Link, useParams } from 'react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Check, X } from 'lucide-react';
import { toast } from 'sonner';
import { useApiClient } from '../../api/client';
import type { DesignChange, MembersResponse } from '../../api/types';
import { TopBar } from './TopBar';

const STATE_STYLE: Record<DesignChange['state'], string> = {
  pending: 'bg-amber-50 text-amber-700',
  approved: 'bg-emerald-50 text-emerald-700',
  rejected: 'bg-red-50 text-red-700',
};

const card = 'bg-white rounded-xl border border-[#E8E1D8] p-5';
const input = 'border border-[#E8E1D8] rounded-md px-2 py-1 text-sm';
const btn = 'px-3 py-1.5 rounded-md text-sm font-medium disabled:opacity-50';

async function errorText(res: Response) {
  try {
    const body = await res.json();
    return body.detail ?? JSON.stringify(body);
  } catch {
    return `Request failed (${res.status})`;
  }
}

function ChangeCard({ change, base, canReview, onDone }: {
  change: DesignChange; base: string; canReview: boolean; onDone: () => void;
}) {
  const apiFetch = useApiClient();
  const [comment, setComment] = useState('');
  const [part, setPart] = useState(change.parts[0] ?? '');
  const [baseline, setBaseline] = useState('');
  const [busy, setBusy] = useState(false);
  const latest = change.interference_checks[change.interference_checks.length - 1];

  const post = async (path: string, body: object) => {
    setBusy(true);
    try {
      const res = await apiFetch(`${base}/changes/${change.id}/${path}`, { method: 'POST', body: JSON.stringify(body) });
      if (!res.ok) toast.error(await errorText(res));
      onDone();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={card}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-medium text-[#2B2824]">{change.title}</p>
          <p className="text-xs text-[#8B7F73]">
            by {change.author} · {new Date(change.created_at).toLocaleString()}
            {change.parts.length > 0 && ` · parts: ${change.parts.join(', ')}`}
            {change.files.length > 0 && ` · ${change.files.length} file(s)`}
          </p>
          {change.description && <p className="text-sm mt-1">{change.description}</p>}
        </div>
        <span className={`text-xs px-2 py-0.5 rounded-full capitalize ${STATE_STYLE[change.state]}`}>{change.state}</span>
      </div>

      {canReview && change.state === 'pending' && (
        <div className="flex gap-2 mt-3">
          <input className={`${input} flex-1`} placeholder="Review comment" value={comment} onChange={(e) => setComment(e.target.value)} />
          <button disabled={busy} className={`${btn} bg-emerald-600 text-white flex items-center gap-1`} onClick={() => post('decision/', { decision: 'approved', comment })}>
            <Check size={14} /> Approve
          </button>
          <button disabled={busy} className={`${btn} bg-red-600 text-white flex items-center gap-1`} onClick={() => post('decision/', { decision: 'rejected', comment })}>
            <X size={14} /> Reject
          </button>
        </div>
      )}

      <div className="mt-4 border-t border-[#F0EAE2] pt-3">
        <p className="text-xs font-medium text-[#8B7F73] mb-2">Interference check (bounding-box approximation, prototype)</p>
        <div className="flex gap-2 items-center">
          <input className={input} placeholder="Changed part" value={part} onChange={(e) => setPart(e.target.value)} />
          <input className={`${input} w-40`} type="number" placeholder="Manual baseline (min)" value={baseline} onChange={(e) => setBaseline(e.target.value)} />
          <button disabled={busy || !part} className={`${btn} bg-[#2B2824] text-white`} onClick={() => post('interference/', { changed_part: part, manual_baseline_minutes: baseline || null })}>
            Run interference check
          </button>
        </div>
        {latest && (
          <div className="mt-2 text-xs">
            <p className="text-[#8B7F73]">
              {latest.changed_part} vs {latest.results.length} neighbours from {latest.source} · {latest.elapsed_ms.toFixed(2)} ms
              {latest.manual_baseline_minutes != null && ` (manual baseline ${latest.manual_baseline_minutes} min)`}
            </p>
            <ul className="mt-1 space-y-0.5">
              {latest.results.map((r) => (
                <li key={r.part_b} className={r.interferes ? 'text-red-700' : 'text-[#8B7F73]'}>
                  {r.part_a} ↔ {r.part_b}: {r.interferes ? `interferes, overlap ${r.overlap_volume} mm³` : 'clear'}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <div className="mt-4 border-t border-[#F0EAE2] pt-3">
        <p className="text-xs font-medium text-[#8B7F73] mb-2">History</p>
        <ol className="border-l border-[#E8E1D8] pl-3 space-y-1">
          {change.events.map((e) => (
            <li key={e.id} className="text-xs">
              <span className="text-[#A89D91]">{new Date(e.created_at).toLocaleString()}</span>{' '}
              <span className="font-medium">{e.actor}</span> {e.action.replace('_', ' ')}
              {e.comment && <span className="text-[#8B7F73]"> — {e.comment}</span>}
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}

export function DesignReviewPage() {
  const { id } = useParams();
  const apiFetch = useApiClient();
  const queryClient = useQueryClient();
  const base = `/api/review/${id}`;
  const [title, setTitle] = useState('');
  const [parts, setParts] = useState('');
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<'designer' | 'reviewer'>('reviewer');

  const { data: members } = useQuery<MembersResponse>({
    queryKey: ['review-members', id],
    queryFn: async () => (await apiFetch(`${base}/members/`)).json(),
  });
  const { data: changes = [] } = useQuery<DesignChange[]>({
    queryKey: ['review-changes', id],
    queryFn: async () => (await apiFetch(`${base}/changes/`)).json(),
  });
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['review-changes', id] });
    queryClient.invalidateQueries({ queryKey: ['review-members', id] });
  };

  const canSubmit = members?.is_owner || members?.my_role === 'designer';
  const canReview = members?.my_role === 'reviewer';

  const submit = async () => {
    const res = await apiFetch(`${base}/changes/`, {
      method: 'POST',
      body: JSON.stringify({ title, parts: parts.split(',').map((p) => p.trim()).filter(Boolean) }),
    });
    if (!res.ok) return toast.error(await errorText(res));
    setTitle('');
    setParts('');
    refresh();
  };

  const addMember = async () => {
    const res = await apiFetch(`${base}/members/`, { method: 'POST', body: JSON.stringify({ email, role }) });
    if (!res.ok) return toast.error(await errorText(res));
    setEmail('');
    refresh();
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-[#F9F9F9]">
      <TopBar title="Design review" subtitle="Changes, approvals and interference checks for this project." />
      <div className="flex-1 overflow-y-auto px-8 py-6 space-y-4 max-w-5xl">
        <Link to={`/project/${id}`} className="text-sm text-[#8B7F73] flex items-center gap-1">
          <ArrowLeft size={14} /> Back to project
        </Link>

        <div className={card}>
          <p className="text-sm font-medium mb-2">Team roles {members?.my_role && <span className="text-[#8B7F73]">(you: {members.my_role})</span>}</p>
          <ul className="text-sm space-y-0.5">
            {members?.members.map((m) => (
              <li key={m.id}>{m.username} — <span className="capitalize">{m.role}</span></li>
            ))}
            {members?.members.length === 0 && <li className="text-[#A89D91]">No members yet.</li>}
          </ul>
          {members?.is_owner && (
            <div className="flex gap-2 mt-3">
              <input className={`${input} flex-1`} placeholder="Teammate email" value={email} onChange={(e) => setEmail(e.target.value)} />
              <select className={input} value={role} onChange={(e) => setRole(e.target.value as 'designer' | 'reviewer')}>
                <option value="designer">Designer</option>
                <option value="reviewer">Reviewer</option>
              </select>
              <button className={`${btn} bg-[#2B2824] text-white`} disabled={!email} onClick={addMember}>Assign</button>
            </div>
          )}
        </div>

        {canSubmit && (
          <div className={`${card} flex gap-2`}>
            <input className={`${input} flex-1`} placeholder="Change title" value={title} onChange={(e) => setTitle(e.target.value)} />
            <input className={`${input} flex-1`} placeholder="Parts (comma separated, e.g. ORB-1042)" value={parts} onChange={(e) => setParts(e.target.value)} />
            <button className={`${btn} bg-[#C66A4E] text-white`} disabled={!title} onClick={submit}>Submit change</button>
          </div>
        )}

        {changes.length === 0 && <p className="text-sm text-[#A89D91]">No changes submitted yet.</p>}
        {changes.map((c) => (
          <ChangeCard key={c.id} change={c} base={base} canReview={canReview} onDone={refresh} />
        ))}
      </div>
    </div>
  );
}
