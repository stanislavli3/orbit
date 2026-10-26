import { useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, CheckCircle2, FileSpreadsheet, Loader2 } from 'lucide-react';
import { useApiClient } from '../../api/client';
import type { CostImportBatch, CostImportReport } from '../../api/types';

/** Import historical part costs (SCRUM-58): validate first, show rejected rows, then import. */
export function CostImportCard() {
  const apiFetch = useApiClient();
  const qc = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [report, setReport] = useState<CostImportReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const { data: batches = [] } = useQuery<CostImportBatch[]>({
    queryKey: ['cost-imports'],
    queryFn: async () => {
      const res = await apiFetch('/api/parts/imports/');
      if (!res.ok) throw new Error('Failed to load imports');
      return res.json();
    },
  });

  async function send(selected: File, dryRun: boolean) {
    setBusy(true);
    setError('');
    const body = new FormData();
    body.append('file', selected);
    body.append('dry_run', String(dryRun));
    try {
      const res = await apiFetch('/api/parts/imports/', { method: 'POST', body });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? 'Import failed');
      setReport(data);
      if (!dryRun) qc.invalidateQueries({ queryKey: ['cost-imports'] });
    } catch (e) {
      setError((e as Error).message);
      setReport(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="bg-white border border-[#E8E0D3] rounded-xl p-5 space-y-4">
      <div className="flex items-center gap-3">
        <FileSpreadsheet className="w-5 h-5 text-[#8B7F73]" strokeWidth={1.5} />
        <div className="flex-1">
          <h2 className="text-sm font-medium text-[#2B2824]">Import historical part costs</h2>
          <p className="text-xs text-[#8B7F73]">
            CSV or Excel with part number, description, material, cost and model year or program.
          </p>
        </div>
        <input
          ref={inputRef}
          type="file"
          accept=".csv,.xlsx"
          className="hidden"
          onChange={(e) => {
            const selected = e.target.files?.[0];
            e.target.value = '';
            if (selected) {
              setFile(selected);
              send(selected, true);
            }
          }}
        />
        <button
          onClick={() => inputRef.current?.click()}
          disabled={busy}
          className="px-3 py-1.5 rounded-lg border border-[#E8E0D3] text-sm text-[#2B2824] hover:bg-[#FFFCF7] disabled:opacity-50"
        >
          Choose file
        </button>
      </div>

      {busy && <Loader2 className="w-4 h-4 animate-spin text-[#8B7F73]" />}
      {error && <p className="text-sm text-[#DC2626]">{error}</p>}

      {report && (
        <div className="space-y-3">
          <p className="text-sm text-[#2B2824]">
            <span className="font-medium">{report.filename}</span>:{' '}
            {report.dry_run
              ? `${report.valid_rows} of ${report.total_rows} rows are ready to import.`
              : `${report.imported_rows} rows imported.`}
            {report.rejected.length > 0 && ` ${report.rejected.length} rejected.`}
          </p>

          {report.rejected.length > 0 && (
            <div className="border border-amber-200 rounded-lg overflow-hidden">
              <table className="w-full text-xs">
                <thead className="bg-amber-50 text-amber-800">
                  <tr>
                    <th className="px-3 py-2 text-left w-16">Row</th>
                    <th className="px-3 py-2 text-left w-40">Part number</th>
                    <th className="px-3 py-2 text-left">Why it was rejected</th>
                  </tr>
                </thead>
                <tbody>
                  {report.rejected.map((r) => (
                    <tr key={r.row} className="border-t border-amber-100">
                      <td className="px-3 py-1.5 text-[#8B7F73]">{r.row}</td>
                      <td className="px-3 py-1.5 text-[#2B2824]">{r.values.part_number || '—'}</td>
                      <td className="px-3 py-1.5 text-amber-800">
                        <AlertTriangle className="inline w-3 h-3 mr-1" />
                        {r.errors.join('; ')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {report.dry_run && file && report.valid_rows > 0 && (
            <button
              onClick={() => send(file, false)}
              disabled={busy}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#2B2824] text-white text-sm hover:opacity-90 disabled:opacity-50"
            >
              <CheckCircle2 className="w-4 h-4" />
              Import {report.valid_rows} row{report.valid_rows !== 1 ? 's' : ''}
            </button>
          )}
        </div>
      )}

      {batches.length > 0 && (
        <div className="pt-2 border-t border-[#F2EDE3]">
          <p className="text-xs font-medium text-[#8B7F73] mb-1.5">Past imports</p>
          <ul className="space-y-1">
            {batches.slice(0, 5).map((b) => (
              <li key={b.id} className="text-xs text-[#2B2824]">
                {b.filename} · {b.imported_rows} imported
                {b.rejected_rows > 0 && `, ${b.rejected_rows} rejected`}
                {b.is_sample && <span className="ml-1.5 text-amber-700">SAMPLE DATA</span>}
                <span className="text-[#A89D91]"> · {new Date(b.created_at).toLocaleDateString()}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
