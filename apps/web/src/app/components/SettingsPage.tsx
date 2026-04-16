import { useState, useRef, useCallback } from 'react';
import { useUser, useClerk } from '@clerk/clerk-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { LogOut, Ban, Plus, Pencil, Trash2, Upload, X, Search, Mail, MessageSquare } from 'lucide-react';
import { TopBar } from './TopBar';
import { useApiClient } from '../../api/client';
import type { TeamContact } from '../../api/types';
import { toast } from 'sonner';

interface HealthResponse {
  status: string;
  anthropic: boolean;
}

function StatusBadge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className={`inline-block w-2.5 h-2.5 rounded-full ${ok ? 'bg-green-500' : 'bg-red-500'}`} />
      <span className="text-sm text-[#111111]">{label}</span>
      <span className={`text-xs font-medium ${ok ? 'text-green-600' : 'text-red-600'}`}>
        {ok ? 'Configured' : 'Not configured'}
      </span>
    </div>
  );
}

function ReadOnlyInput({ value }: { value: string }) {
  return (
    <input
      value={value}
      readOnly
      className="w-72 px-3 py-2 border border-[#E6E6E6] rounded-lg text-sm text-[#6B7280] bg-[#F9F9F9] cursor-default focus:outline-none"
    />
  );
}

function FieldRow({ label, description, children }: { label: string; description: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-8 py-5 border-b border-[#F4F4F4] last:border-0">
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-[#111111]">{label}</p>
        <p className="text-xs text-[#6B7280] mt-0.5">{description}</p>
      </div>
      <div className="shrink-0 flex items-center">{children}</div>
    </div>
  );
}

// ── Tag chip input ────────────────────────────────────────────────────────────
function TagInput({ tags, onChange }: { tags: string[]; onChange: (tags: string[]) => void }) {
  const [input, setInput] = useState('');

  function add() {
    const v = input.trim();
    if (v && !tags.includes(v)) onChange([...tags, v]);
    setInput('');
  }

  return (
    <div className="flex flex-wrap gap-1.5 items-center w-full min-h-[38px] px-2 py-1.5 border border-[#E6E6E6] rounded-lg focus-within:border-[#111111] transition-colors bg-white">
      {tags.map((t) => (
        <span key={t} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[#F4F4F4] text-xs text-[#111111]">
          {t}
          <button type="button" onClick={() => onChange(tags.filter((x) => x !== t))} className="hover:text-red-500">
            <X className="w-3 h-3" />
          </button>
        </span>
      ))}
      <input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); add(); } }}
        onBlur={add}
        placeholder={tags.length === 0 ? 'Type and press Enter…' : ''}
        className="flex-1 min-w-[120px] text-sm text-[#111111] placeholder:text-[#9CA3AF] focus:outline-none bg-transparent"
      />
    </div>
  );
}

// ── Contact modal (add / edit) ────────────────────────────────────────────────
interface ContactModalProps {
  contact?: TeamContact | null;
  onClose: () => void;
  onSave: (data: Partial<TeamContact>) => Promise<void>;
}

function ContactModal({ contact, onClose, onSave }: ContactModalProps) {
  const [form, setForm] = useState({
    full_name: contact?.full_name ?? '',
    email: contact?.email ?? '',
    role: contact?.role ?? '',
    department: contact?.department ?? '',
    expertise_tags: contact?.expertise_tags ?? [] as string[],
    slack_handle: contact?.slack_handle ?? '',
    preferred_channel: (contact?.preferred_channel ?? 'email') as 'email' | 'slack',
    notes: contact?.notes ?? '',
    allow_automated: contact?.allow_automated ?? true,
  });
  const [saving, setSaving] = useState(false);

  function set(key: string, value: unknown) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await onSave(form);
      onClose();
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#F4F4F4]">
          <h3 className="text-base font-semibold text-[#111111]">{contact ? 'Edit contact' : 'Add contact'}</h3>
          <button onClick={onClose} className="text-[#9CA3AF] hover:text-[#111111] transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-4 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-[#6B7280] mb-1">Full name *</label>
              <input required value={form.full_name} onChange={(e) => set('full_name', e.target.value)}
                className="w-full px-3 py-2 border border-[#E6E6E6] rounded-lg text-sm focus:outline-none focus:border-[#111111]" />
            </div>
            <div>
              <label className="block text-xs font-medium text-[#6B7280] mb-1">Email *</label>
              <input required type="email" value={form.email} onChange={(e) => set('email', e.target.value)}
                className="w-full px-3 py-2 border border-[#E6E6E6] rounded-lg text-sm focus:outline-none focus:border-[#111111]" />
            </div>
            <div>
              <label className="block text-xs font-medium text-[#6B7280] mb-1">Role *</label>
              <input required value={form.role} onChange={(e) => set('role', e.target.value)}
                className="w-full px-3 py-2 border border-[#E6E6E6] rounded-lg text-sm focus:outline-none focus:border-[#111111]" />
            </div>
            <div>
              <label className="block text-xs font-medium text-[#6B7280] mb-1">Department</label>
              <input value={form.department} onChange={(e) => set('department', e.target.value)}
                className="w-full px-3 py-2 border border-[#E6E6E6] rounded-lg text-sm focus:outline-none focus:border-[#111111]" />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-[#6B7280] mb-1">Expertise tags</label>
            <TagInput tags={form.expertise_tags} onChange={(t) => set('expertise_tags', t)} />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-[#6B7280] mb-1">Slack handle</label>
              <input value={form.slack_handle} onChange={(e) => set('slack_handle', e.target.value)}
                placeholder="@handle"
                className="w-full px-3 py-2 border border-[#E6E6E6] rounded-lg text-sm focus:outline-none focus:border-[#111111]" />
            </div>
            <div>
              <label className="block text-xs font-medium text-[#6B7280] mb-1">Preferred channel</label>
              <div className="flex gap-2 mt-1">
                {(['email', 'slack'] as const).map((ch) => (
                  <button key={ch} type="button"
                    onClick={() => set('preferred_channel', ch)}
                    className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg border text-sm transition-colors ${form.preferred_channel === ch ? 'border-[#111111] bg-[#111111] text-white' : 'border-[#E6E6E6] text-[#6B7280] hover:border-[#111111]'}`}>
                    {ch === 'email' ? <Mail className="w-3.5 h-3.5" /> : <MessageSquare className="w-3.5 h-3.5" />}
                    {ch.charAt(0).toUpperCase() + ch.slice(1)}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-[#6B7280] mb-1">Notes</label>
            <textarea value={form.notes} onChange={(e) => set('notes', e.target.value)} rows={2}
              className="w-full px-3 py-2 border border-[#E6E6E6] rounded-lg text-sm focus:outline-none focus:border-[#111111] resize-none" />
          </div>

          <div className="flex items-center justify-between py-2 border-t border-[#F4F4F4]">
            <div>
              <p className="text-sm font-medium text-[#111111]">Allow automated emails</p>
              <p className="text-xs text-[#6B7280]">BOM agent may contact this person automatically.</p>
            </div>
            <button type="button" onClick={() => set('allow_automated', !form.allow_automated)}
              className={`relative w-10 h-5 rounded-full transition-colors ${form.allow_automated ? 'bg-[#111111]' : 'bg-[#D1D5DB]'}`}>
              <span className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${form.allow_automated ? 'translate-x-5' : 'translate-x-0.5'}`} />
            </button>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose}
              className="px-4 py-2 text-sm border border-[#E6E6E6] rounded-lg hover:bg-[#F4F4F4] transition-colors">
              Cancel
            </button>
            <button type="submit" disabled={saving}
              className="px-4 py-2 text-sm bg-[#111111] text-white rounded-lg hover:bg-[#333333] disabled:opacity-50 transition-colors">
              {saving ? 'Saving…' : contact ? 'Save changes' : 'Add contact'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── CSV import modal ──────────────────────────────────────────────────────────
interface CsvRow { full_name: string; email: string; role: string; department: string; expertise_tags: string[] }
interface CsvError { row: number; errors: string[]; data: { name: string; email: string } }

function CsvImportModal({ onClose, onImported }: { onClose: () => void; onImported: () => void }) {
  const apiFetch = useApiClient();
  const [preview, setPreview] = useState<CsvRow[] | null>(null);
  const [csvErrors, setCsvErrors] = useState<CsvError[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  async function handleFile(f: File) {
    setFile(f);
    const fd = new FormData();
    fd.append('file', f);
    const res = await apiFetch('/api/team/contacts/import/?preview=true', { method: 'POST', body: fd });
    const data = await res.json();
    if (!res.ok) { toast.error(data.detail ?? 'Preview failed'); return; }
    setPreview(data.preview);
    setCsvErrors(data.errors ?? []);
  }

  async function handleConfirm() {
    if (!file) return;
    setImporting(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await apiFetch('/api/team/contacts/import/', { method: 'POST', body: fd });
      const data = await res.json();
      if (!res.ok) { toast.error(data.detail ?? 'Import failed'); return; }
      toast.success(`Imported ${data.created_count} contact${data.created_count !== 1 ? 's' : ''}${data.skipped_count ? `, skipped ${data.skipped_count} duplicates` : ''}.`);
      onImported();
      onClose();
    } finally {
      setImporting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl mx-4 max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#F4F4F4]">
          <h3 className="text-base font-semibold text-[#111111]">Import contacts from CSV</h3>
          <button onClick={onClose} className="text-[#9CA3AF] hover:text-[#111111]"><X className="w-5 h-5" /></button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {!preview ? (
            <div
              onClick={() => fileRef.current?.click()}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) handleFile(f); }}
              className="border-2 border-dashed border-[#E6E6E6] rounded-lg p-10 text-center cursor-pointer hover:border-[#111111] transition-colors">
              <Upload className="w-8 h-8 mx-auto text-[#9CA3AF] mb-2" />
              <p className="text-sm text-[#111111] font-medium">Drop a CSV file here, or click to browse</p>
              <p className="text-xs text-[#9CA3AF] mt-1">Required columns: Name, Email, Role. Optional: Department, Tags</p>
              <input ref={fileRef} type="file" accept=".csv" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }} />
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between">
                <p className="text-sm text-[#111111]"><span className="font-medium">{preview.length}</span> rows ready to import{csvErrors.length > 0 && <span className="text-red-600 ml-2">· {csvErrors.length} with errors (will be skipped)</span>}</p>
                <button onClick={() => { setPreview(null); setCsvErrors([]); setFile(null); }} className="text-xs text-[#6B7280] hover:text-[#111111]">Change file</button>
              </div>

              {csvErrors.length > 0 && (
                <div className="rounded-lg bg-red-50 border border-red-200 p-3 space-y-1">
                  {csvErrors.map((e) => (
                    <p key={e.row} className="text-xs text-red-700">Row {e.row} ({e.data.email || e.data.name || '—'}): {e.errors.join(', ')}</p>
                  ))}
                </div>
              )}

              <div className="rounded-lg border border-[#E6E6E6] overflow-hidden">
                <table className="w-full text-xs">
                  <thead className="bg-[#F9F9F9]">
                    <tr>
                      {['Name', 'Email', 'Role', 'Dept', 'Tags'].map((h) => (
                        <th key={h} className="px-3 py-2 text-left font-medium text-[#6B7280]">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {preview.map((r, i) => (
                      <tr key={i} className="border-t border-[#F4F4F4]">
                        <td className="px-3 py-2 text-[#111111]">{r.full_name}</td>
                        <td className="px-3 py-2 text-[#6B7280]">{r.email}</td>
                        <td className="px-3 py-2 text-[#6B7280]">{r.role}</td>
                        <td className="px-3 py-2 text-[#6B7280]">{r.department}</td>
                        <td className="px-3 py-2">
                          <div className="flex flex-wrap gap-1">
                            {r.expertise_tags.map((t) => (
                              <span key={t} className="px-1.5 py-0.5 rounded-full bg-[#F4F4F4] text-[10px]">{t}</span>
                            ))}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>

        {preview && (
          <div className="flex justify-end gap-2 px-6 py-4 border-t border-[#F4F4F4]">
            <button onClick={onClose} className="px-4 py-2 text-sm border border-[#E6E6E6] rounded-lg hover:bg-[#F4F4F4]">Cancel</button>
            <button onClick={handleConfirm} disabled={importing || preview.length === 0}
              className="px-4 py-2 text-sm bg-[#111111] text-white rounded-lg hover:bg-[#333333] disabled:opacity-50">
              {importing ? 'Importing…' : `Import ${preview.length} contact${preview.length !== 1 ? 's' : ''}`}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Delete confirm dialog ─────────────────────────────────────────────────────
function DeleteConfirmDialog({ name, onConfirm, onCancel }: { name: string; onConfirm: () => void; onCancel: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-sm mx-4 p-6">
        <h3 className="text-base font-semibold text-[#111111] mb-1">Remove contact</h3>
        <p className="text-sm text-[#6B7280]">Remove <span className="font-medium text-[#111111]">{name}</span> from your team directory? This cannot be undone.</p>
        <div className="flex justify-end gap-2 mt-5">
          <button onClick={onCancel} className="px-4 py-2 text-sm border border-[#E6E6E6] rounded-lg hover:bg-[#F4F4F4]">Cancel</button>
          <button onClick={onConfirm} className="px-4 py-2 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700">Remove</button>
        </div>
      </div>
    </div>
  );
}

// ── Team contacts section ─────────────────────────────────────────────────────
function TeamContactsSection() {
  const apiFetch = useApiClient();
  const qc = useQueryClient();
  const [search, setSearch] = useState('');
  const [showAdd, setShowAdd] = useState(false);
  const [editing, setEditing] = useState<TeamContact | null>(null);
  const [deleting, setDeleting] = useState<TeamContact | null>(null);
  const [showImport, setShowImport] = useState(false);

  const { data: contacts = [], isLoading } = useQuery<TeamContact[]>({
    queryKey: ['team-contacts', search],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (search) params.set('search', search);
      const res = await apiFetch(`/api/team/contacts/?${params}`);
      if (!res.ok) throw new Error('Failed to load contacts');
      return res.json();
    },
  });

  const invalidate = useCallback(() => qc.invalidateQueries({ queryKey: ['team-contacts'] }), [qc]);

  const createMutation = useMutation({
    mutationFn: async (data: Partial<TeamContact>) => {
      const res = await apiFetch('/api/team/contacts/', { method: 'POST', body: JSON.stringify(data) });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.email?.[0] ?? err.detail ?? 'Failed to add contact');
      }
    },
    onSuccess: () => { toast.success('Contact added.'); invalidate(); },
    onError: (e: Error) => toast.error(e.message),
  });

  const updateMutation = useMutation({
    mutationFn: async ({ id, data }: { id: number; data: Partial<TeamContact> }) => {
      const res = await apiFetch(`/api/team/contacts/${id}/`, { method: 'PATCH', body: JSON.stringify(data) });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.email?.[0] ?? err.detail ?? 'Failed to update contact');
      }
    },
    onSuccess: () => { toast.success('Contact updated.'); invalidate(); },
    onError: (e: Error) => toast.error(e.message),
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      const res = await apiFetch(`/api/team/contacts/${id}/`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Failed to delete contact');
    },
    onSuccess: () => { toast.success('Contact removed.'); invalidate(); setDeleting(null); },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <section className="px-8 pt-6 pb-2">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h2 className="text-[#111111] font-semibold text-base">Team</h2>
          <p className="text-[#6B7280] text-sm mt-0.5">Colleagues the BOM agent can contact for missing specs.</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setShowImport(true)}
            className="flex items-center gap-1.5 px-3 py-2 text-sm border border-[#E6E6E6] rounded-lg hover:bg-[#F4F4F4] transition-colors">
            <Upload className="w-4 h-4" />
            Import CSV
          </button>
          <button onClick={() => setShowAdd(true)}
            className="flex items-center gap-1.5 px-3 py-2 text-sm bg-[#111111] text-white rounded-lg hover:bg-[#333333] transition-colors">
            <Plus className="w-4 h-4" />
            Add contact
          </button>
        </div>
      </div>

      {/* Search */}
      <div className="relative mb-4">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#9CA3AF]" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by name, role, or tag…"
          className="w-full pl-9 pr-3 py-2 border border-[#E6E6E6] rounded-lg text-sm focus:outline-none focus:border-[#111111] transition-colors"
        />
      </div>

      {/* Table */}
      {isLoading ? (
        <p className="text-sm text-[#9CA3AF] py-4 text-center">Loading…</p>
      ) : contacts.length === 0 ? (
        <div className="text-center py-12 border border-dashed border-[#E6E6E6] rounded-xl">
          <p className="text-sm font-medium text-[#111111]">
            {search ? 'No contacts match your search.' : 'Add your first team member to unlock automated BOM research emails'}
          </p>
          {!search && (
            <button onClick={() => setShowAdd(true)}
              className="mt-3 text-sm text-[#111111] underline underline-offset-2 hover:opacity-70 transition-opacity">
              Add a contact
            </button>
          )}
        </div>
      ) : (
        <div className="rounded-xl border border-[#E6E6E6] overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-[#F9F9F9] border-b border-[#E6E6E6]">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-[#6B7280] text-xs">Name</th>
                <th className="px-4 py-3 text-left font-medium text-[#6B7280] text-xs">Role</th>
                <th className="px-4 py-3 text-left font-medium text-[#6B7280] text-xs">Expertise</th>
                <th className="px-4 py-3 text-left font-medium text-[#6B7280] text-xs">Channel</th>
                <th className="px-4 py-3 text-left font-medium text-[#6B7280] text-xs">Auto</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {contacts.map((c) => (
                <tr key={c.id} className="border-t border-[#F4F4F4] hover:bg-[#FAFAFA] transition-colors">
                  <td className="px-4 py-3">
                    <p className="font-medium text-[#111111]">{c.full_name}</p>
                    <p className="text-xs text-[#9CA3AF]">{c.email}</p>
                  </td>
                  <td className="px-4 py-3 text-[#6B7280]">
                    <p>{c.role}</p>
                    {c.department && <p className="text-xs text-[#9CA3AF]">{c.department}</p>}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {c.expertise_tags.map((t) => (
                        <span key={t} className="px-2 py-0.5 rounded-full bg-[#F4F4F4] text-[#6B7280] text-[11px]">{t}</span>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center gap-1 text-xs text-[#6B7280]">
                      {c.preferred_channel === 'slack'
                        ? <><MessageSquare className="w-3.5 h-3.5" /> Slack</>
                        : <><Mail className="w-3.5 h-3.5" /> Email</>}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-block w-2 h-2 rounded-full ${c.allow_automated ? 'bg-green-500' : 'bg-[#D1D5DB]'}`} />
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1 justify-end">
                      <button onClick={() => setEditing(c)}
                        className="p-1.5 rounded hover:bg-[#F4F4F4] text-[#9CA3AF] hover:text-[#111111] transition-colors">
                        <Pencil className="w-3.5 h-3.5" />
                      </button>
                      <button onClick={() => setDeleting(c)}
                        className="p-1.5 rounded hover:bg-[#FEF2F2] text-[#9CA3AF] hover:text-red-600 transition-colors">
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

      {/* Modals */}
      {showAdd && (
        <ContactModal
          onClose={() => setShowAdd(false)}
          onSave={(data) => createMutation.mutateAsync(data)}
        />
      )}
      {editing && (
        <ContactModal
          contact={editing}
          onClose={() => setEditing(null)}
          onSave={(data) => updateMutation.mutateAsync({ id: editing.id, data })}
        />
      )}
      {deleting && (
        <DeleteConfirmDialog
          name={deleting.full_name}
          onConfirm={() => deleteMutation.mutate(deleting.id)}
          onCancel={() => setDeleting(null)}
        />
      )}
      {showImport && (
        <CsvImportModal onClose={() => setShowImport(false)} onImported={invalidate} />
      )}
    </section>
  );
}

export function SettingsPage() {
  const { user } = useUser();
  const { signOut } = useClerk();
  const apiFetch = useApiClient();

  const meta = (user?.unsafeMetadata ?? {}) as Record<string, string>;

  // Profile state
  const [firstName, setFirstName] = useState(user?.firstName ?? '');
  const [lastName, setLastName] = useState(user?.lastName ?? '');
  const [role, setRole] = useState(meta.role ?? '');
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [profileSuccess, setProfileSuccess] = useState(false);

  // Workspace state
  const [workspaceName, setWorkspaceName] = useState(meta.workspaceName ?? '');
  const [workspaceSlug, setWorkspaceSlug] = useState(meta.workspaceSlug ?? '');
  const [defaultPermissions, setDefaultPermissions] = useState(meta.defaultPermissions ?? 'private');
  const [workspaceSaving, setWorkspaceSaving] = useState(false);
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);
  const [workspaceSuccess, setWorkspaceSuccess] = useState(false);

  const { data: health } = useQuery<HealthResponse>({
    queryKey: ['health'],
    queryFn: async () => {
      const res = await apiFetch('/api/health/');
      if (!res.ok) throw new Error('Health check failed');
      return res.json();
    },
  });

  async function handleSaveProfile() {
    if (!user) return;
    setProfileSaving(true);
    setProfileError(null);
    setProfileSuccess(false);
    try {
      await user.update({
        firstName,
        lastName,
        unsafeMetadata: { ...meta, role },
      });
      setProfileSuccess(true);
      setTimeout(() => setProfileSuccess(false), 2000);
    } catch {
      setProfileError('Failed to save. Please try again.');
    } finally {
      setProfileSaving(false);
    }
  }

  async function handleSaveWorkspace() {
    if (!user) return;
    setWorkspaceSaving(true);
    setWorkspaceError(null);
    setWorkspaceSuccess(false);
    try {
      await user.update({
        unsafeMetadata: { ...meta, workspaceName, workspaceSlug, defaultPermissions },
      });
      setWorkspaceSuccess(true);
      setTimeout(() => setWorkspaceSuccess(false), 2000);
    } catch {
      setWorkspaceError('Failed to save. Please try again.');
    } finally {
      setWorkspaceSaving(false);
    }
  }

  const email = user?.primaryEmailAddress?.emailAddress ?? '';

  return (
    <div className="flex-1 flex flex-col h-full bg-[#F9F9F9]">
      <TopBar title="Settings" subtitle="Manage your account, workspace, and preferences." />

      <div className="flex-1 overflow-y-auto px-8 py-8">
        <div className="divide-y divide-[#D1D1D1]">

          {/* ── Profile ─────────────────────────────────────────── */}
          <section className="px-8 pt-6 pb-2">
            <div className="flex items-start justify-between mb-2">
              <div>
                <h2 className="text-[#111111] font-semibold text-base">Profile</h2>
                <p className="text-[#6B7280] text-sm mt-0.5">Manage your personal information and account details.</p>
              </div>
              <div className="flex items-center gap-2">
                {profileError && <p className="text-xs text-red-600">{profileError}</p>}
                <button
                  onClick={handleSaveProfile}
                  disabled={profileSaving}
                  className="px-4 py-2 bg-[#111111] text-white text-sm rounded-lg hover:bg-[#333333] disabled:opacity-50 transition-colors"
                >
                  {profileSaving ? 'Saving…' : profileSuccess ? 'Saved!' : 'Save'}
                </button>
              </div>
            </div>

            <FieldRow label="Full name" description="Your name as it appears across Orbit.">
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  placeholder="First"
                  className="w-36 px-3 py-2 border border-[#E6E6E6] rounded-lg text-sm text-[#111111] placeholder:text-[#9CA3AF] focus:outline-none focus:border-[#111111] transition-colors"
                />
                <input
                  type="text"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  placeholder="Last"
                  className="w-36 px-3 py-2 border border-[#E6E6E6] rounded-lg text-sm text-[#111111] placeholder:text-[#9CA3AF] focus:outline-none focus:border-[#111111] transition-colors"
                />
              </div>
            </FieldRow>

            <FieldRow label="Email address" description="Your primary contact email.">
              <ReadOnlyInput value={email} />
            </FieldRow>

            <FieldRow label="Role" description="Your role in the organization.">
              <input
                type="text"
                value={role}
                onChange={(e) => setRole(e.target.value)}
                placeholder="e.g. Engineering Manager"
                className="w-72 px-3 py-2 border border-[#E6E6E6] rounded-lg text-sm text-[#111111] placeholder:text-[#9CA3AF] focus:outline-none focus:border-[#111111] transition-colors"
              />
            </FieldRow>
          </section>

          {/* ── Workspace ────────────────────────────────────────── */}
          <section className="px-8 pt-6 pb-2">
            <div className="flex items-start justify-between mb-2">
              <div>
                <h2 className="text-[#111111] font-semibold text-base">Workspace</h2>
                <p className="text-[#6B7280] text-sm mt-0.5">Configure workspace settings and permissions.</p>
              </div>
              <div className="flex items-center gap-2">
                {workspaceError && <p className="text-xs text-red-600">{workspaceError}</p>}
                <button
                  onClick={handleSaveWorkspace}
                  disabled={workspaceSaving}
                  className="px-4 py-2 bg-[#111111] text-white text-sm rounded-lg hover:bg-[#333333] disabled:opacity-50 transition-colors"
                >
                  {workspaceSaving ? 'Saving…' : workspaceSuccess ? 'Saved!' : 'Save'}
                </button>
              </div>
            </div>

            <FieldRow label="Workspace name" description="The name of your workspace.">
              <input
                type="text"
                value={workspaceName}
                onChange={(e) => setWorkspaceName(e.target.value)}
                placeholder="e.g. Orbit"
                className="w-72 px-3 py-2 border border-[#E6E6E6] rounded-lg text-sm text-[#111111] placeholder:text-[#9CA3AF] focus:outline-none focus:border-[#111111] transition-colors"
              />
            </FieldRow>

            <FieldRow label="Workspace URL" description="Custom URL for your workspace.">
              <div className="flex items-center border border-[#E6E6E6] rounded-lg overflow-hidden focus-within:border-[#111111] transition-colors">
                <span className="px-3 py-2 text-sm text-[#9CA3AF] bg-[#F9F9F9] border-r border-[#E6E6E6] select-none">
                  orbit.app/
                </span>
                <input
                  type="text"
                  value={workspaceSlug}
                  onChange={(e) => setWorkspaceSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''))}
                  placeholder="your-workspace"
                  className="w-48 px-3 py-2 text-sm text-[#111111] placeholder:text-[#9CA3AF] focus:outline-none bg-white"
                />
              </div>
            </FieldRow>

            <FieldRow label="Default file permissions" description="Who can access newly uploaded files.">
              <select
                value={defaultPermissions}
                onChange={(e) => setDefaultPermissions(e.target.value)}
                className="w-72 px-3 py-2 border border-[#E6E6E6] rounded-lg text-sm text-[#111111] focus:outline-none focus:border-[#111111] transition-colors bg-white appearance-none cursor-pointer"
              >
                <option value="private">Private — only you</option>
                <option value="team">Team — all workspace members</option>
                <option value="public">Public — anyone with the link</option>
              </select>
            </FieldRow>
          </section>

          {/* ── API & Integrations ───────────────────────────────── */}
          <section className="px-8 pt-6 pb-2">
            <h2 className="text-[#111111] font-semibold text-base mb-0.5">API & Integrations</h2>
            <p className="text-[#6B7280] text-sm mb-2">Status of external services connected to Orbit.</p>

            <FieldRow label="Anthropic AI" description="Powers metadata extraction and the assistant.">
              {health ? (
                <StatusBadge ok={health.anthropic} label="Anthropic AI" />
              ) : (
                <span className="text-xs text-[#9CA3AF]">Checking…</span>
              )}
            </FieldRow>

            <FieldRow label="Clerk Auth" description="Handles authentication and user sessions.">
              <StatusBadge ok={!!user} label="Clerk Auth" />
            </FieldRow>
          </section>

          {/* ── Team Contacts ────────────────────────────────────── */}
          <TeamContactsSection />

          {/* ── Danger Zone ──────────────────────────────────────── */}
          <section className="px-8 pt-6 pb-2">
            <h2 className="text-red-600 font-semibold text-base mb-0.5">Danger Zone</h2>
            <p className="text-[#6B7280] text-sm mb-2">Irreversible actions for your account.</p>

            <FieldRow label="Sign out" description="End your current session on this device.">
              <button
                onClick={() => signOut({ redirectUrl: '/signin' })}
                className="flex items-center gap-2 px-4 py-2 border border-[#E6E6E6] text-[#111111] text-sm rounded-lg hover:bg-[#F4F4F4] transition-colors"
              >
                <LogOut className="w-4 h-4" />
                Sign out
              </button>
            </FieldRow>

            <FieldRow label="Delete account" description="Permanently remove your account and all data.">
              <div title="Contact support to delete your account">
                <button
                  disabled
                  className="flex items-center gap-2 px-4 py-2 border border-[#E6E6E6] text-[#9CA3AF] text-sm rounded-lg cursor-not-allowed"
                >
                  <Ban className="w-4 h-4" />
                  Delete account
                </button>
              </div>
            </FieldRow>
          </section>

        </div>
      </div>
    </div>
  );
}
