import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Trash2, FolderOpen, ShieldCheck } from 'lucide-react';
import { toast } from 'sonner';
import { useApiClient } from '../../api/client';
import type { SupplierSetting, WorkspaceSourceKind, WorkspaceSourcesOverview } from '../../api/types';

function Toggle({ on, onClick, label }: { on: boolean; onClick: () => void; label: string }) {
  return (
    <button type="button" aria-label={label} aria-pressed={on} onClick={onClick}
      className={`relative w-10 h-5 rounded-full transition-colors shrink-0 ${on ? 'bg-[#2B2824]' : 'bg-[#D1D5DB]'}`}>
      <span className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${on ? 'translate-x-5' : 'translate-x-0.5'}`} />
    </button>
  );
}

/** Settings -> Workspace sources (SCRUM-52): folders, systems, cost imports and the AVL. */
export function WorkspaceSourcesSection() {
  const apiFetch = useApiClient();
  const qc = useQueryClient();
  const [kind, setKind] = useState<WorkspaceSourceKind>('local_folder');
  const [name, setName] = useState('');
  const [location, setLocation] = useState('');
  const [supplierFilter, setSupplierFilter] = useState('');

  const { data: overview } = useQuery<WorkspaceSourcesOverview>({
    queryKey: ['workspace-sources'],
    queryFn: async () => {
      const res = await apiFetch('/api/parts/sources/');
      if (!res.ok) throw new Error('Failed to load sources');
      return res.json();
    },
  });

  const { data: suppliers = [] } = useQuery<SupplierSetting[]>({
    queryKey: ['supplier-settings'],
    queryFn: async () => {
      const res = await apiFetch('/api/parts/suppliers/');
      if (!res.ok) throw new Error('Failed to load suppliers');
      return res.json();
    },
  });

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ['workspace-sources'] });
    void qc.invalidateQueries({ queryKey: ['supplier-settings'] });
  };

  const addSource = useMutation({
    mutationFn: async () => {
      const res = await apiFetch('/api/parts/sources/', {
        method: 'POST',
        body: JSON.stringify({ kind, name: name.trim(), location: location.trim() }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? data.name?.[0] ?? 'Could not add source');
    },
    onSuccess: () => { toast.success('Source added.'); setName(''); setLocation(''); refresh(); },
    onError: (e: Error) => toast.error(e.message),
  });

  const patchSource = useMutation({
    mutationFn: async ({ id, enabled }: { id: number; enabled: boolean }) => {
      const res = await apiFetch(`/api/parts/sources/${id}/`, { method: 'PATCH', body: JSON.stringify({ enabled }) });
      if (!res.ok) throw new Error('Could not update source');
    },
    onSuccess: refresh,
    onError: (e: Error) => toast.error(e.message),
  });

  const deleteSource = useMutation({
    mutationFn: async (id: number) => {
      const res = await apiFetch(`/api/parts/sources/${id}/`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Could not remove source');
    },
    onSuccess: refresh,
    onError: (e: Error) => toast.error(e.message),
  });

  const patchSupplier = useMutation({
    mutationFn: async ({ id, is_approved }: { id: number; is_approved: boolean }) => {
      const res = await apiFetch(`/api/parts/suppliers/${id}/`, { method: 'PATCH', body: JSON.stringify({ is_approved }) });
      if (!res.ok) throw new Error('Could not update supplier');
    },
    onSuccess: refresh,
    onError: (e: Error) => toast.error(e.message),
  });

  const kinds = overview?.kinds ?? [];
  const kindLabel = (k: string) => kinds.find((x) => x.value === k)?.label ?? k;
  const shownSuppliers = suppliers.filter((s) => s.name.toLowerCase().includes(supplierFilter.toLowerCase()));

  return (
    <section className="px-8 pt-6 pb-2">
      <div className="mb-4">
        <h2 className="text-[#2B2824] font-semibold text-base">Workspace sources</h2>
        <p className="text-[#8B7F73] text-sm mt-0.5">Which folders, systems and supplier lists Orbit reads from. Disabled sources are ignored.</p>
      </div>

      <div className="rounded-xl border border-[#E8E0D3] divide-y divide-[#F2EDE3]">
        {(overview?.sources ?? []).length === 0 && (
          <p className="px-4 py-4 text-sm text-[#A89D91]">No sources configured yet. Add a folder or system below.</p>
        )}
        {(overview?.sources ?? []).map((s) => (
          <div key={s.id} className="flex items-center gap-3 px-4 py-3">
            <FolderOpen className="w-4 h-4 text-[#A89D91] shrink-0" />
            <div className="flex-1 min-w-0">
              <p className={`text-sm font-medium ${s.enabled ? 'text-[#2B2824]' : 'text-[#A89D91] line-through'}`}>{s.name}</p>
              <p className="text-xs text-[#8B7F73] truncate">{kindLabel(s.kind)}{s.location ? ` · ${s.location}` : ''}</p>
            </div>
            <Toggle on={s.enabled} label={`${s.enabled ? 'Disable' : 'Enable'} ${s.name}`}
              onClick={() => patchSource.mutate({ id: s.id, enabled: !s.enabled })} />
            <button onClick={() => deleteSource.mutate(s.id)} aria-label={`Remove ${s.name}`}
              className="p-1.5 rounded hover:bg-[#FEF2F2] text-[#A89D91] hover:text-red-600">
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        ))}
        <form className="flex flex-wrap items-center gap-2 px-4 py-3 bg-[#FFFCF7]"
          onSubmit={(e) => { e.preventDefault(); if (name.trim()) addSource.mutate(); }}>
          <select value={kind} onChange={(e) => setKind(e.target.value as WorkspaceSourceKind)}
            className="px-2 py-2 border border-[#E8E0D3] rounded-lg text-sm bg-white">
            {kinds.map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}
          </select>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Name, e.g. Drawings share"
            className="flex-1 min-w-[160px] px-3 py-2 border border-[#E8E0D3] rounded-lg text-sm focus:outline-none focus:border-[#2B2824]" />
          <input value={location} onChange={(e) => setLocation(e.target.value)} placeholder="Path, folder id or URL"
            className="flex-1 min-w-[160px] px-3 py-2 border border-[#E8E0D3] rounded-lg text-sm focus:outline-none focus:border-[#2B2824]" />
          <button type="submit" disabled={!name.trim() || addSource.isPending}
            className="flex items-center gap-1.5 px-3 py-2 text-sm bg-[#2B2824] text-white rounded-lg disabled:opacity-50">
            <Plus className="w-4 h-4" /> Add
          </button>
        </form>
      </div>

      <h3 className="text-sm font-semibold text-[#2B2824] mt-6 mb-2">Cost-history imports</h3>
      {(overview?.cost_imports ?? []).length === 0 ? (
        <p className="text-sm text-[#A89D91]">No cost spreadsheets imported yet (Estimate page → Import costs).</p>
      ) : (
        <ul className="text-sm text-[#2B2824] space-y-1">
          {overview!.cost_imports.map((b) => (
            <li key={b.id}>{b.filename} <span className="text-xs text-[#8B7F73]">· {b.imported_rows} rows · {new Date(b.created_at).toLocaleDateString()}</span></li>
          ))}
        </ul>
      )}

      <div className="flex items-center justify-between mt-6 mb-2">
        <h3 className="text-sm font-semibold text-[#2B2824] flex items-center gap-1.5">
          <ShieldCheck className="w-4 h-4" /> Approved vendor list
          <span className="text-xs font-normal text-[#8B7F73]">
            ({overview?.supplier_counts.approved ?? 0} of {overview?.supplier_counts.total ?? 0} approved)
          </span>
        </h3>
        <input value={supplierFilter} onChange={(e) => setSupplierFilter(e.target.value)} placeholder="Filter suppliers…"
          className="w-48 px-3 py-1.5 border border-[#E8E0D3] rounded-lg text-sm focus:outline-none focus:border-[#2B2824]" />
      </div>
      {suppliers.length === 0 ? (
        <p className="text-sm text-[#A89D91]">Suppliers appear here once quotes or cost imports mention them.</p>
      ) : (
        <div className="rounded-xl border border-[#E8E0D3] divide-y divide-[#F2EDE3] max-h-80 overflow-y-auto">
          {shownSuppliers.map((s) => (
            <div key={s.id} className="flex items-center gap-3 px-4 py-2.5">
              <div className="flex-1 min-w-0">
                <p className="text-sm text-[#2B2824]">{s.name}</p>
                {(s.certifications || s.approval_note) && (
                  <p className="text-xs text-[#8B7F73] truncate">{[s.certifications, s.approval_note].filter(Boolean).join(' · ')}</p>
                )}
              </div>
              <span className={`text-xs ${s.is_approved ? 'text-green-600' : 'text-[#A89D91]'}`}>{s.is_approved ? 'Approved' : 'Not approved'}</span>
              <Toggle on={s.is_approved} label={`${s.is_approved ? 'Unapprove' : 'Approve'} ${s.name}`}
                onClick={() => patchSupplier.mutate({ id: s.id, is_approved: !s.is_approved })} />
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
