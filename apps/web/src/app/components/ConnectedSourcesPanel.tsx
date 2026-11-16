import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { FolderOpen, HardDrive, Loader2, RefreshCw, Trash, Plus, AlertCircle } from 'lucide-react';
import { toast } from 'sonner';
import { useApiClient } from '../../api/client';
import type { ConnectedSource, ConnectorKind, ConnectorStatus } from '../../api/types';

const KIND_LABEL: Record<ConnectorKind, string> = {
  local_folder: 'Local folder',
  google_drive: 'Google Drive',
};

/** Connected sources: repositories Orbit indexes in place (SCRUM-50/78). */
export function ConnectedSourcesPanel({ projectId }: { projectId: string }) {
  const apiFetch = useApiClient();
  const queryClient = useQueryClient();
  const [kind, setKind] = useState<ConnectorKind>('local_folder');
  const [location, setLocation] = useState('');
  const [adding, setAdding] = useState(false);
  const [indexingId, setIndexingId] = useState<number | null>(null);

  const { data: status } = useQuery<ConnectorStatus>({
    queryKey: ['connector-status'],
    queryFn: async () => {
      const res = await apiFetch('/api/files/connectors/');
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
  });

  const { data: sources = [] } = useQuery<ConnectedSource[]>({
    queryKey: ['project-sources', projectId],
    queryFn: async () => {
      const res = await apiFetch(`/api/files/project/${projectId}/sources/`);
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
  });

  const kindStatus = status?.[kind];
  const notConfigured = kindStatus && !kindStatus.configured;

  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ['project-sources', projectId] });
    await queryClient.invalidateQueries({ queryKey: ['project-files', projectId] });
  };

  const indexNow = async (id: number) => {
    setIndexingId(id);
    try {
      const res = await apiFetch(`/api/files/sources/${id}/index/`, { method: 'POST' });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data?.error ?? `Indexing failed (${res.status})`);
      toast.success(`Indexed ${data.indexed} file(s)` + (data.failed ? `, ${data.failed} failed` : ''));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Indexing failed');
    } finally {
      setIndexingId(null);
      await refresh();
    }
  };

  const addSource = async () => {
    if (!location.trim()) return;
    setAdding(true);
    try {
      const config = kind === 'local_folder' ? { path: location.trim() } : { folder_id: location.trim() };
      const res = await apiFetch(`/api/files/project/${projectId}/sources/`, {
        method: 'POST',
        body: JSON.stringify({ kind, config }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data?.error ?? `Failed (${res.status})`);
      setLocation('');
      await refresh();
      await indexNow(data.id);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to add source');
    } finally {
      setAdding(false);
    }
  };

  const removeSource = async (s: ConnectedSource) => {
    if (!window.confirm(`Disconnect "${s.name}"? Indexed entries are removed from Orbit; the original files are not touched.`)) return;
    const res = await apiFetch(`/api/files/sources/${s.id}/`, { method: 'DELETE' });
    if (!res.ok && res.status !== 204) toast.error(`Failed (${res.status})`);
    await refresh();
  };

  return (
    <div className="bg-white border border-[#E8E0D3] rounded-xl mb-4 px-6 py-4">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-sm font-medium text-[#2B2824]">Connected sources</h3>
          <p className="text-[12px] text-[#8B7F73]">Index files where they already live. Nothing is copied; results link back to the original.</p>
        </div>
      </div>

      {sources.length > 0 && (
        <div className="mb-3 divide-y divide-[#EEE6D8] border border-[#EEE6D8] rounded-lg">
          {sources.map((s) => (
            <div key={s.id} className="flex items-center gap-3 px-3 py-2">
              {s.kind === 'google_drive'
                ? <HardDrive className="w-4 h-4 text-[#8B7F73]" strokeWidth={1.5} />
                : <FolderOpen className="w-4 h-4 text-[#8B7F73]" strokeWidth={1.5} />}
              <div className="min-w-0 flex-1">
                <p className="text-sm text-[#2B2824] truncate">{s.name} <span className="text-[11px] text-[#A89D91]">· {KIND_LABEL[s.kind]}</span></p>
                <p className="text-[11px] text-[#8B7F73] truncate" title={s.config.path ?? s.config.folder_id}>
                  {s.config.path ?? s.config.folder_id} ·{' '}
                  {s.last_indexed_at ? `${s.file_count} file(s), indexed ${new Date(s.last_indexed_at).toLocaleString()}` : 'Not indexed yet'}
                </p>
                {s.last_error && <p className="text-[11px] text-red-600 truncate">{s.last_error}</p>}
              </div>
              <button
                onClick={() => indexNow(s.id)}
                disabled={indexingId === s.id}
                className="px-2.5 py-1 text-[12px] border border-[#E8E0D3] rounded-md hover:bg-[#FAF7F2] flex items-center gap-1 disabled:opacity-60"
              >
                {indexingId === s.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />} Index now
              </button>
              <button onClick={() => removeSource(s)} className="p-1 text-[#8B7F73] hover:text-red-600" aria-label="Disconnect source">
                <Trash className="w-3.5 h-3.5" strokeWidth={1.5} />
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="flex items-center gap-2">
        <select
          value={kind}
          onChange={(e) => setKind(e.target.value as ConnectorKind)}
          className="text-sm border border-[#E8E0D3] rounded-lg px-2 py-1.5 bg-white"
        >
          <option value="local_folder">Local folder</option>
          <option value="google_drive">Google Drive folder</option>
        </select>
        <input
          value={location}
          onChange={(e) => setLocation(e.target.value)}
          disabled={!!notConfigured}
          placeholder={kind === 'local_folder' ? '/path/to/step-and-pdf-exports' : 'Drive folder URL or ID'}
          className="flex-1 text-sm border border-[#E8E0D3] rounded-lg px-3 py-1.5 disabled:bg-[#FAF7F2]"
        />
        <button
          onClick={addSource}
          disabled={adding || !location.trim() || !!notConfigured}
          className="px-3 py-1.5 bg-[#2B2824] text-white rounded-lg text-sm flex items-center gap-1 disabled:opacity-50"
        >
          {adding ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />} Connect
        </button>
      </div>
      {notConfigured && (
        <p className="mt-2 text-[12px] text-[#92400E] bg-amber-50 border border-amber-100 rounded px-2.5 py-1.5 flex items-center gap-1.5">
          <AlertCircle className="w-3.5 h-3.5" /> Not configured: {kindStatus.detail}
        </p>
      )}
    </div>
  );
}
