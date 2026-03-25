import { Search, FolderPlus, Database, Folder } from 'lucide-react';
import { TopBar } from './TopBar';
import { ActionCard } from './ActionCard';
import { ProjectCard } from './ProjectCard';
import { Link } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { useApiClient } from '../../api/client';
import type { Project } from '../../api/types';

function SkeletonCard() {
  return (
    <div className="bg-white border border-[#E6E6E6] rounded-xl p-5 animate-pulse">
      <div className="w-10 h-10 bg-[#F4F4F4] rounded-lg mb-4" />
      <div className="h-4 bg-[#F4F4F4] rounded w-3/4 mb-2" />
      <div className="h-3 bg-[#F4F4F4] rounded w-1/2" />
    </div>
  );
}

export function VaultPage() {
  const apiFetch = useApiClient();

  const { data: projects, isLoading, isError } = useQuery<Project[]>({
    queryKey: ['projects'],
    queryFn: async () => {
      const res = await apiFetch('/api/projects/');
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      return res.json();
    },
  });

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
            />
            <ActionCard
              icon={Database}
              title="Create knowledge base"
              description="Organize a repository of engineering files for search and reuse."
            />
          </div>

          {/* Tabs and Search */}
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-6">
              <button className="text-[#111111] text-sm pb-2 border-b-2 border-[#111111]">
                All projects
              </button>
              <button className="text-[#6B7280] text-sm pb-2 border-b-2 border-transparent hover:text-[#111111] transition-colors">
                Your projects
              </button>
              <button className="text-[#6B7280] text-sm pb-2 border-b-2 border-transparent hover:text-[#111111] transition-colors">
                Shared with you
              </button>
            </div>

            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#6B7280]" />
              <input
                type="text"
                placeholder="Search"
                className="w-64 pl-9 pr-4 py-1.5 bg-white border border-[#E6E6E6] rounded-lg text-sm placeholder:text-[#6B7280] focus:outline-none focus:border-[#111111] transition-colors"
              />
            </div>
          </div>

          {/* Project Grid */}
          {isLoading && (
            <div className="grid grid-cols-4 gap-4">
              {Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)}
            </div>
          )}

          {isError && (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <p className="text-[#111111] font-medium mb-1">Failed to load projects</p>
              <p className="text-[#6B7280] text-sm">Check that the API server is running on port 8000.</p>
            </div>
          )}

          {projects && projects.length === 0 && (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <div className="w-12 h-12 bg-[#F4F4F4] rounded-xl flex items-center justify-center mb-4">
                <Folder className="w-6 h-6 text-[#6B7280]" strokeWidth={1.5} />
              </div>
              <p className="text-[#111111] font-medium mb-1">No projects yet</p>
              <p className="text-[#6B7280] text-sm">Create a project to get started.</p>
            </div>
          )}

          {projects && projects.length > 0 && (
            <div className="grid grid-cols-4 gap-4">
              {projects.map((project) => (
                <Link key={project.id} to={`/project/${project.id}`}>
                  <ProjectCard
                    name={project.name}
                    fileCount={project.file_count}
                  />
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
