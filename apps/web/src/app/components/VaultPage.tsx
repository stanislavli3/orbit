'use client';
import { useState } from 'react';
import { Search, FolderPlus, Database, Folder, X, Files, Users, MoreVertical, Pencil, Trash2 } from 'lucide-react';
import { TopBar } from './TopBar';
import { ActionCard } from './ActionCard';
import { ProjectCard } from './ProjectCard';
import { Link } from 'react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useApiClient } from '../../api/client';
import type { Project } from '../../api/types';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../components/ui/dialog';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '../components/ui/popover';
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogCancel,
  AlertDialogAction,
} from '../components/ui/alert-dialog';

type Tab = 'all' | 'yours' | 'shared';

function SkeletonCard() {
  return (
    <div className="bg-white border border-[#E6E6E6] rounded-xl overflow-hidden animate-pulse">
      <div className="h-28 bg-[#F4F4F4]" />
      <div className="p-4">
        <div className="h-3.5 bg-[#EBEBEB] rounded w-3/4 mb-2" />
        <div className="h-3 bg-[#EBEBEB] rounded w-1/2 mb-3" />
        <div className="h-3 bg-[#EBEBEB] rounded w-1/4" />
      </div>
    </div>
  );
}

export function VaultPage() {
  const apiFetch = useApiClient();
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [projectName, setProjectName] = useState('');
  const [projectDesc, setProjectDesc] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [createError, setCreateError] = useState('');
  const [search, setSearch] = useState('');
  const [tab, setTab] = useState<Tab>('all');

  // Rename state
  const [renameProject, setRenameProject] = useState<Project | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const [renameError, setRenameError] = useState('');
  const [renaming, setRenaming] = useState(false);

  // Delete state
  const [deleteProject, setDeleteProject] = useState<Project | null>(null);
  const [deleting, setDeleting] = useState(false);

  const { data: projects, isLoading, isError } = useQuery<Project[]>({
    queryKey: ['projects'],
    queryFn: async () => {
      const res = await apiFetch('/api/projects/');
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      return res.json();
    },
  });

  const handleRenameProject = async () => {
    if (!renameProject || !renameValue.trim()) return;
    setRenaming(true);
    setRenameError('');
    try {
      const res = await apiFetch(`/api/projects/${renameProject.id}/`, {
        method: 'PATCH',
        body: JSON.stringify({ name: renameValue.trim() }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.name?.[0] ?? `Error ${res.status}`);
      }
      await queryClient.invalidateQueries({ queryKey: ['projects'] });
      setRenameProject(null);
    } catch (err) {
      setRenameError(err instanceof Error ? err.message : 'Failed to rename project');
    } finally {
      setRenaming(false);
    }
  };

  const handleDeleteProject = async () => {
    if (!deleteProject) return;
    setDeleting(true);
    try {
      const res = await apiFetch(`/api/projects/${deleteProject.id}/`, { method: 'DELETE' });
      if (!res.ok) throw new Error(`Error ${res.status}`);
      await queryClient.invalidateQueries({ queryKey: ['projects'] });
      setDeleteProject(null);
    } finally {
      setDeleting(false);
    }
  };

  const handleCreateProject = async () => {
    if (!projectName.trim()) return;
    setSubmitting(true);
    setCreateError('');
    try {
      const res = await apiFetch('/api/projects/', {
        method: 'POST',
        body: JSON.stringify({ name: projectName.trim(), description: projectDesc.trim() }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.name?.[0] ?? `Error ${res.status}`);
      }
      await queryClient.invalidateQueries({ queryKey: ['projects'] });
      setDialogOpen(false);
      setProjectName('');
      setProjectDesc('');
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'Failed to create project');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">
      <TopBar
        title="Vault"
        subtitle="Upload, store, and analyze engineering files and their extracted profiles."
      />

      <div className="flex-1 overflow-auto">
        <div className="max-w-[1400px] mx-auto px-8 py-8">
          {/* Action Cards */}
          <div className="grid grid-cols-2 gap-4 mb-8">
            <ActionCard
              icon={FolderPlus}
              title="Create project"
              description="Upload a new collection of parts, drawings, and assemblies."
              onClick={() => setDialogOpen(true)}
            />
            <ActionCard
              icon={Database}
              title="Create knowledge base"
              description="Organize a repository of engineering files for search and reuse."
            />
          </div>

          {/* Stats bar */}
          {projects && projects.length > 0 && (() => {
            const totalFiles = projects.reduce((s, p) => s + p.file_count, 0);
            return (
              <div className="flex items-center gap-4 mb-6 px-0.5">
                <div className="flex items-center gap-1.5">
                  <Folder className="w-3.5 h-3.5 text-[#9CA3AF]" strokeWidth={1.5} />
                  <span className="text-[12px] text-[#6B7280]">
                    <span className="font-semibold text-[#111111]">{projects.length}</span>
                    {' '}{projects.length === 1 ? 'project' : 'projects'}
                  </span>
                </div>
                <div className="w-px h-3 bg-[#E6E6E6]" />
                <div className="flex items-center gap-1.5">
                  <Files className="w-3.5 h-3.5 text-[#9CA3AF]" strokeWidth={1.5} />
                  <span className="text-[12px] text-[#6B7280]">
                    <span className="font-semibold text-[#111111]">{totalFiles}</span>
                    {' '}{totalFiles === 1 ? 'file' : 'files'} total
                  </span>
                </div>
              </div>
            );
          })()}

          {/* Tabs and Search */}
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-6">
              {(['all', 'yours', 'shared'] as Tab[]).map((t) => {
                const labels: Record<Tab, string> = {
                  all: 'All projects',
                  yours: 'Your projects',
                  shared: 'Shared with you',
                };
                const active = tab === t;
                return (
                  <button
                    key={t}
                    onClick={() => setTab(t)}
                    className={`text-sm pb-2 border-b-2 transition-colors ${
                      active
                        ? 'text-[#111111] font-medium border-[#111111]'
                        : 'text-[#9CA3AF] font-normal border-transparent hover:text-[#6B7280]'
                    }`}
                  >
                    {labels[t]}
                  </button>
                );
              })}
            </div>

            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[#9CA3AF]" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search projects…"
                className="w-64 pl-9 pr-8 py-1.5 bg-white border border-[#E6E6E6] rounded-lg text-sm text-[#111111] placeholder:text-[#9CA3AF] focus:outline-none focus:border-[#C4C4C4] focus:shadow-sm transition-all"
              />
              {search && (
                <button
                  onClick={() => setSearch('')}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[#9CA3AF] hover:text-[#6B7280] transition-colors"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>

          {/* Project Grid */}
          {isLoading && (
            <div className="grid grid-cols-4 gap-4">
              {Array.from({ length: 8 }).map((_, i) => <SkeletonCard key={i} />)}
            </div>
          )}

          {isError && (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <div className="w-12 h-12 bg-[#FEF2F2] rounded-xl flex items-center justify-center mb-4">
                <Folder className="w-6 h-6 text-[#DC2626]" strokeWidth={1.5} />
              </div>
              <p className="text-[#111111] font-medium mb-1">Failed to load projects</p>
              <p className="text-[#6B7280] text-sm">Check that the API server is running on port 8000.</p>
            </div>
          )}

          {projects && (() => {
            if (tab === 'shared') {
              return (
                <div className="flex flex-col items-center justify-center py-24 text-center">
                  <div className="w-14 h-14 bg-[#F4F4F4] rounded-2xl flex items-center justify-center mb-4">
                    <Users className="w-7 h-7 text-[#9CA3AF]" strokeWidth={1.5} />
                  </div>
                  <p className="text-[#111111] font-medium mb-1">No shared projects yet</p>
                  <p className="text-[#9CA3AF] text-sm">Projects shared with you will appear here.</p>
                </div>
              );
            }

            const q = search.trim().toLowerCase();
            const filtered = q
              ? projects.filter(p =>
                  p.name.toLowerCase().includes(q) ||
                  (p.description ?? '').toLowerCase().includes(q)
                )
              : projects;

            if (projects.length === 0) {
              return (
                <div className="flex flex-col items-center justify-center py-24 text-center">
                  <div
                    onClick={() => setDialogOpen(true)}
                    className="w-20 h-20 border-2 border-dashed border-[#E6E6E6] rounded-2xl flex items-center justify-center mb-5 cursor-pointer hover:border-[#C4C4C4] hover:bg-[#FAFAFA] transition-all group/icon"
                  >
                    <Folder className="w-8 h-8 text-[#D1D5DB] group-hover/icon:text-[#9CA3AF] transition-colors" strokeWidth={1.5} />
                  </div>
                  <p className="text-[#111111] text-[14px] font-semibold mb-1.5">No projects yet</p>
                  <p className="text-[#9CA3AF] text-[13px] mb-5 max-w-xs">Create your first project to start uploading engineering files and extracting metadata.</p>
                  <button
                    onClick={() => setDialogOpen(true)}
                    className="px-4 py-2 bg-[#111111] text-white text-[13px] font-medium rounded-lg hover:bg-[#1F1F1F] transition-colors"
                  >
                    Create project
                  </button>
                </div>
              );
            }

            if (filtered.length === 0) {
              return (
                <div className="flex flex-col items-center justify-center py-24 text-center">
                  <div className="w-14 h-14 bg-[#F4F4F4] rounded-2xl flex items-center justify-center mb-4">
                    <Search className="w-7 h-7 text-[#9CA3AF]" strokeWidth={1.5} />
                  </div>
                  <p className="text-[#111111] font-medium mb-1">No results for "{search}"</p>
                  <button onClick={() => setSearch('')} className="text-[#6B7280] text-sm hover:text-[#111111] transition-colors">
                    Clear search
                  </button>
                </div>
              );
            }

            return (
              <div className="grid grid-cols-4 gap-4">
                {filtered.map((project) => (
                  <div key={project.id} className="relative group/card">
                    <Link to={`/project/${project.id}`}>
                      <ProjectCard
                        name={project.name}
                        fileCount={project.file_count}
                        description={project.description}
                      />
                    </Link>
                    <Popover>
                      <PopoverTrigger asChild>
                        <button
                          className="absolute top-2.5 right-2.5 z-10 opacity-0 group-hover/card:opacity-100 w-7 h-7 flex items-center justify-center rounded-md bg-white border border-[#E6E6E6] text-[#6B7280] hover:text-[#111111] hover:border-[#C4C4C4] transition-all shadow-sm"
                        >
                          <MoreVertical className="w-3.5 h-3.5" />
                        </button>
                      </PopoverTrigger>
                      <PopoverContent align="end" sideOffset={6} className="w-36 p-1">
                        <button
                          className="w-full flex items-center gap-2 px-2.5 py-1.5 text-[13px] text-[#111111] rounded hover:bg-[#F4F4F4] transition-colors"
                          onClick={() => {
                            setRenameProject(project);
                            setRenameValue(project.name);
                            setRenameError('');
                          }}
                        >
                          <Pencil className="w-3.5 h-3.5 text-[#6B7280]" />
                          Rename
                        </button>
                        <button
                          className="w-full flex items-center gap-2 px-2.5 py-1.5 text-[13px] text-[#DC2626] rounded hover:bg-[#FEF2F2] transition-colors"
                          onClick={() => setDeleteProject(project)}
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                          Delete
                        </button>
                      </PopoverContent>
                    </Popover>
                  </div>
                ))}
              </div>
            );
          })()}
        </div>
      </div>

      {/* Rename Dialog */}
      <Dialog
        open={!!renameProject}
        onOpenChange={(open) => { if (!open) setRenameProject(null); }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Rename project</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            {renameError && (
              <p className="text-sm text-[#DC2626] bg-[#FEF2F2] border border-[#FECACA] rounded-lg px-3 py-2">
                {renameError}
              </p>
            )}
            <div className="space-y-1.5">
              <label className="text-[#374151] text-xs font-medium">Project name</label>
              <input
                type="text"
                value={renameValue}
                onChange={(e) => setRenameValue(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleRenameProject()}
                autoFocus
                className="w-full px-3 py-2.5 bg-white border border-[#E6E6E6] rounded-lg text-sm text-[#111111] placeholder:text-[#9CA3AF] focus:outline-none focus:border-[#111111] focus:ring-1 focus:ring-[#111111] transition-all"
              />
            </div>
          </div>
          <DialogFooter>
            <button
              onClick={() => setRenameProject(null)}
              className="px-4 py-2 text-sm text-[#6B7280] hover:text-[#111111] transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleRenameProject}
              disabled={!renameValue.trim() || renaming}
              className="px-4 py-2 bg-[#111111] text-white text-sm font-medium rounded-lg hover:bg-[#1F1F1F] disabled:opacity-50 transition-colors"
            >
              {renaming ? 'Saving...' : 'Save'}
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirm Dialog */}
      <AlertDialog
        open={!!deleteProject}
        onOpenChange={(open) => { if (!open) setDeleteProject(null); }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete project?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete <strong>{deleteProject?.name}</strong> and all its files. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteProject}
              disabled={deleting}
              className="bg-[#DC2626] hover:bg-[#B91C1C] focus:ring-[#DC2626]"
            >
              {deleting ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Create Project Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Create project</DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-2">
            {createError && (
              <p className="text-sm text-[#DC2626] bg-[#FEF2F2] border border-[#FECACA] rounded-lg px-3 py-2">
                {createError}
              </p>
            )}
            <div className="space-y-1.5">
              <label className="text-[#374151] text-xs font-medium">Project name</label>
              <input
                type="text"
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleCreateProject()}
                placeholder="e.g. Gearbox Assembly Rev B"
                autoFocus
                className="w-full px-3 py-2.5 bg-white border border-[#E6E6E6] rounded-lg text-sm text-[#111111] placeholder:text-[#9CA3AF] focus:outline-none focus:border-[#111111] focus:ring-1 focus:ring-[#111111] transition-all"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-[#374151] text-xs font-medium">Description <span className="text-[#9CA3AF]">(optional)</span></label>
              <textarea
                value={projectDesc}
                onChange={(e) => setProjectDesc(e.target.value)}
                placeholder="What is this project for?"
                rows={3}
                className="w-full px-3 py-2.5 bg-white border border-[#E6E6E6] rounded-lg text-sm text-[#111111] placeholder:text-[#9CA3AF] focus:outline-none focus:border-[#111111] focus:ring-1 focus:ring-[#111111] transition-all resize-none"
              />
            </div>
          </div>

          <DialogFooter>
            <button
              onClick={() => setDialogOpen(false)}
              className="px-4 py-2 text-sm text-[#6B7280] hover:text-[#111111] transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleCreateProject}
              disabled={!projectName.trim() || submitting}
              className="px-4 py-2 bg-[#111111] text-white text-sm font-medium rounded-lg hover:bg-[#1F1F1F] disabled:opacity-50 transition-colors"
            >
              {submitting ? 'Creating...' : 'Create project'}
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
