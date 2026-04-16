import { useState, useRef, useCallback } from 'react';
import { Upload, Trash2, Download, BookOpen, X, Loader2, FileText, CheckCircle2 } from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useApiClient } from '../../api/client';
import type { LibraryDocument, LibraryDocType } from '../../api/types';
import { toast } from 'sonner';
import { TopBar } from './TopBar';

// ── Constants ─────────────────────────────────────────────────────────────────

const DOC_TYPES: { value: LibraryDocType; label: string; description: string }[] = [
  { value: 'avl', label: 'Approved Vendor List', description: 'Filter supplier search to approved vendors only' },
  { value: 'material-spec', label: 'Material Specification', description: 'Cross-reference material grades & properties' },
  { value: 'compliance', label: 'Compliance Document', description: 'Verify RoHS / REACH / ITAR per supplier' },
  { value: 'previous-bom', label: 'Previous BOM', description: 'Baseline pricing & delta analysis' },
  { value: 'scorecard', label: 'Supplier Scorecard', description: 'Rank suppliers by historical performance' },
  { value: 'standard', label: 'Design Standard', description: 'Check parts against internal design standards' },
  { value: 'preferred-materials', label: 'Preferred Materials', description: 'Auto-suggest materials before falling back to web' },
];

const TYPE_COLORS: Record<LibraryDocType, string> = {
  'avl': 'bg-blue-50 text-blue-700 border-blue-200',
  'material-spec': 'bg-purple-50 text-purple-700 border-purple-200',
  'compliance': 'bg-orange-50 text-orange-700 border-orange-200',
  'previous-bom': 'bg-emerald-50 text-emerald-700 border-emerald-200',
  'scorecard': 'bg-yellow-50 text-yellow-700 border-yellow-200',
  'standard': 'bg-gray-50 text-gray-700 border-gray-200',
  'preferred-materials': 'bg-pink-50 text-pink-700 border-pink-200',
};

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function TypeTag({ docType }: { docType: LibraryDocType | '' }) {
  if (!docType) {
    return <span className="px-2 py-0.5 text-[11px] rounded-full border border-dashed border-[#D1D5DB] text-[#9CA3AF]">Untagged</span>;
  }
  const label = DOC_TYPES.find((t) => t.value === docType)?.label ?? docType;
  return (
    <span className={`px-2 py-0.5 text-[11px] rounded-full border font-medium ${TYPE_COLORS[docType] ?? 'bg-[#F4F4F4] text-[#6B7280] border-[#E6E6E6]'}`}>
      {label}
    </span>
  );
}

// ── Type-tag picker modal ─────────────────────────────────────────────────────

function TagPickerModal({
  title,
  current,
  onSelect,
  onClose,
  uploading,
}: {
  title: string;
  current?: LibraryDocType | '';
  onSelect: (t: LibraryDocType) => void;
  onClose: () => void;
  uploading?: boolean;
}) {
  const [selected, setSelected] = useState<LibraryDocType | ''>(current ?? '');

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4">
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#F4F4F4]">
          <h3 className="text-base font-semibold text-[#111111]">{title}</h3>
          <button onClick={onClose} className="text-[#9CA3AF] hover:text-[#111111]"><X className="w-5 h-5" /></button>
        </div>
        <div className="px-4 py-3 space-y-1.5 max-h-96 overflow-y-auto">
          {DOC_TYPES.map((t) => (
            <button
              key={t.value}
              onClick={() => setSelected(t.value)}
              className={`w-full text-left px-4 py-3 rounded-lg border transition-colors ${
                selected === t.value
                  ? 'border-[#111111] bg-[#FAFAFA]'
                  : 'border-transparent hover:bg-[#F9F9F9]'
              }`}
            >
              <div className="flex items-start gap-3">
                <span className={`mt-0.5 w-4 h-4 rounded-full border-2 flex-shrink-0 flex items-center justify-center ${selected === t.value ? 'border-[#111111] bg-[#111111]' : 'border-[#D1D5DB]'}`}>
                  {selected === t.value && <span className="w-1.5 h-1.5 rounded-full bg-white" />}
                </span>
                <div>
                  <p className="text-sm font-medium text-[#111111]">{t.label}</p>
                  <p className="text-xs text-[#6B7280] mt-0.5">{t.description}</p>
                </div>
              </div>
            </button>
          ))}
        </div>
        <div className="flex justify-end gap-2 px-6 py-4 border-t border-[#F4F4F4]">
          <button onClick={onClose} className="px-4 py-2 text-sm border border-[#E6E6E6] rounded-lg hover:bg-[#F4F4F4]">Cancel</button>
          <button
            onClick={() => selected && onSelect(selected as LibraryDocType)}
            disabled={!selected || uploading}
            className="px-4 py-2 text-sm bg-[#111111] text-white rounded-lg hover:bg-[#333333] disabled:opacity-50 flex items-center gap-1.5"
          >
            {uploading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            Confirm
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Delete confirmation ───────────────────────────────────────────────────────

function DeleteConfirm({ name, onConfirm, onCancel }: { name: string; onConfirm: () => void; onCancel: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-sm mx-4 p-6">
        <h3 className="text-base font-semibold text-[#111111] mb-1">Remove document</h3>
        <p className="text-sm text-[#6B7280]">Remove <span className="font-medium text-[#111111]">{name}</span> from the Library? BOM runs that used it will not be affected.</p>
        <div className="flex justify-end gap-2 mt-5">
          <button onClick={onCancel} className="px-4 py-2 text-sm border border-[#E6E6E6] rounded-lg hover:bg-[#F4F4F4]">Cancel</button>
          <button onClick={onConfirm} className="px-4 py-2 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700">Remove</button>
        </div>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function LibraryPage() {
  const apiFetch = useApiClient();
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  // Upload flow state
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [deleting, setDeleting] = useState<LibraryDocument | null>(null);

  // Retag flow (PATCH doc_type)
  const [retagDoc, setRetagDoc] = useState<LibraryDocument | null>(null);
  const [retagging, setRetagging] = useState(false);

  const invalidate = useCallback(() => qc.invalidateQueries({ queryKey: ['library'] }), [qc]);

  const { data: docs = [], isLoading } = useQuery<LibraryDocument[]>({
    queryKey: ['library'],
    queryFn: async () => {
      const res = await apiFetch('/api/library/documents/');
      if (!res.ok) throw new Error('Failed to load library');
      return res.json();
    },
  });

  async function handleFileSelected(file: File) {
    setPendingFile(file);
  }

  async function handleConfirmUpload(docType: LibraryDocType) {
    if (!pendingFile) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append('file', pendingFile);
      fd.append('doc_type', docType);
      const res = await apiFetch('/api/library/documents/', { method: 'POST', body: fd });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail ?? 'Upload failed');
      }
      toast.success(`"${pendingFile.name}" added to Library.`);
      invalidate();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : 'Upload failed');
    } finally {
      setUploading(false);
      setPendingFile(null);
      if (fileRef.current) fileRef.current.value = '';
    }
  }

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      const res = await apiFetch(`/api/library/documents/${id}/`, { method: 'DELETE' });
      if (!res.ok && res.status !== 204) throw new Error('Delete failed');
    },
    onSuccess: () => { toast.success('Document removed.'); invalidate(); setDeleting(null); },
    onError: () => toast.error('Failed to remove document.'),
  });

  async function handleRetag(docType: LibraryDocType) {
    if (!retagDoc) return;
    setRetagging(true);
    try {
      const res = await apiFetch(`/api/library/documents/${retagDoc.id}/`, {
        method: 'PATCH',
        body: JSON.stringify({ doc_type: docType }),
      });
      if (!res.ok) throw new Error('Failed to update tag');
      toast.success('Document type updated.');
      invalidate();
    } catch {
      toast.error('Failed to update document type.');
    } finally {
      setRetagging(false);
      setRetagDoc(null);
    }
  }

  async function handleDownload(doc: LibraryDocument) {
    try {
      const res = await apiFetch(`/api/library/documents/${doc.id}/download/`);
      if (!res.ok) throw new Error('Download failed');
      const data = await res.json();
      if (data?.url) window.open(data.url, '_blank', 'noopener');
    } catch {
      toast.error('Download failed');
    }
  }

  return (
    <div className="flex-1 flex flex-col h-full bg-[#F9F9F9]">
      <TopBar title="Library" subtitle="Workspace reference documents used by the BOM research agent." />

      <div className="flex-1 overflow-y-auto px-8 py-8">
        {/* Upload zone */}
        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            const f = e.dataTransfer.files[0];
            if (f) handleFileSelected(f);
          }}
          onClick={() => fileRef.current?.click()}
          className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors mb-8 ${
            dragging ? 'border-[#111111] bg-[#F4F4F4]' : 'border-[#E6E6E6] hover:border-[#111111] bg-white'
          }`}
        >
          <Upload className="w-8 h-8 mx-auto text-[#9CA3AF] mb-2" />
          <p className="text-sm font-medium text-[#111111]">Drop a reference document here, or click to browse</p>
          <p className="text-xs text-[#9CA3AF] mt-1">Supported: .xlsx · .csv · .pdf · .docx</p>
          <input
            ref={fileRef}
            type="file"
            accept=".xlsx,.csv,.pdf,.docx,text/csv"
            className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFileSelected(f); }}
          />
        </div>

        {/* Document list */}
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-6 h-6 animate-spin text-[#9CA3AF]" />
          </div>
        ) : docs.length === 0 ? (
          <div className="text-center py-16 border border-dashed border-[#E6E6E6] rounded-xl bg-white">
            <BookOpen className="w-10 h-10 mx-auto text-[#D1D5DB] mb-3" />
            <p className="text-sm font-medium text-[#111111]">Your Library is empty</p>
            <p className="text-xs text-[#6B7280] mt-1 max-w-sm mx-auto">
              Add your AVL, material specs, compliance docs, and supplier scorecards. The BOM agent will reference them automatically before searching the web.
            </p>
          </div>
        ) : (
          <div className="bg-white border border-[#E6E6E6] rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-[#F9F9F9] border-b border-[#E6E6E6]">
                <tr>
                  <th className="px-5 py-3 text-left text-xs font-medium text-[#6B7280]">Document</th>
                  <th className="px-5 py-3 text-left text-xs font-medium text-[#6B7280]">Type</th>
                  <th className="px-5 py-3 text-left text-xs font-medium text-[#6B7280]">Uploaded</th>
                  <th className="px-5 py-3 text-left text-xs font-medium text-[#6B7280]">Size</th>
                  <th className="px-5 py-3 text-left text-xs font-medium text-[#6B7280]">BOM runs</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody>
                {docs.map((doc) => (
                  <tr key={doc.id} className="border-t border-[#F4F4F4] hover:bg-[#FAFAFA] transition-colors group">
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-2.5">
                        <FileText className="w-4 h-4 text-[#9CA3AF] flex-shrink-0" strokeWidth={1.5} />
                        <span className="font-medium text-[#111111] truncate max-w-xs">{doc.original_name}</span>
                        <span className="text-[11px] px-1.5 py-0.5 bg-[#F4F4F4] text-[#9CA3AF] rounded uppercase">
                          {doc.file_type}
                        </span>
                      </div>
                    </td>
                    <td className="px-5 py-3">
                      <button
                        onClick={() => setRetagDoc(doc)}
                        className="hover:opacity-70 transition-opacity"
                        title="Change document type"
                      >
                        <TypeTag docType={doc.doc_type} />
                      </button>
                    </td>
                    <td className="px-5 py-3 text-[#6B7280] text-xs">{formatDate(doc.uploaded_at)}</td>
                    <td className="px-5 py-3 text-[#6B7280] text-xs">{formatBytes(doc.file_size)}</td>
                    <td className="px-5 py-3">
                      {doc.bom_run_count > 0 ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 text-[11px] font-medium border border-emerald-200">
                          <CheckCircle2 className="w-3 h-3" />
                          Used by {doc.bom_run_count} run{doc.bom_run_count !== 1 ? 's' : ''}
                        </span>
                      ) : (
                        <span className="text-xs text-[#9CA3AF]">Not yet used</span>
                      )}
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-1 justify-end opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          onClick={() => handleDownload(doc)}
                          className="p-1.5 rounded hover:bg-[#F4F4F4] text-[#9CA3AF] hover:text-[#111111] transition-colors"
                          title="Download"
                        >
                          <Download className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => setDeleting(doc)}
                          className="p-1.5 rounded hover:bg-[#FEF2F2] text-[#9CA3AF] hover:text-red-600 transition-colors"
                          title="Remove"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Type-tag modal for new uploads */}
      {pendingFile && (
        <TagPickerModal
          title={`Tag "${pendingFile.name}"`}
          onSelect={handleConfirmUpload}
          onClose={() => { setPendingFile(null); if (fileRef.current) fileRef.current.value = ''; }}
          uploading={uploading}
        />
      )}

      {/* Re-tag existing document */}
      {retagDoc && (
        <TagPickerModal
          title={`Change type for "${retagDoc.original_name}"`}
          current={retagDoc.doc_type}
          onSelect={handleRetag}
          onClose={() => setRetagDoc(null)}
          uploading={retagging}
        />
      )}

      {deleting && (
        <DeleteConfirm
          name={deleting.original_name}
          onConfirm={() => deleteMutation.mutate(deleting.id)}
          onCancel={() => setDeleting(null)}
        />
      )}
    </div>
  );
}
