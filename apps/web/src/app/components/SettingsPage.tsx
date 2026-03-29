import { useState } from 'react';
import { useUser, useClerk } from '@clerk/clerk-react';
import { useQuery } from '@tanstack/react-query';
import { LogOut, Ban } from 'lucide-react';
import { TopBar } from './TopBar';
import { useApiClient } from '../../api/client';

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
