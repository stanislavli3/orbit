import { Search, FolderPlus, Database } from 'lucide-react';
import { TopBar } from './TopBar';
import { ActionCard } from './ActionCard';
import { ProjectCard } from './ProjectCard';
import { Link } from 'react-router';

const projects = [
  { id: 'gearbox-assembly', name: 'Gearbox Assembly', fileCount: 47, status: 'Extracted' as const },
  { id: 'pump-housing', name: 'Pump Housing Rev B', fileCount: 23, status: 'Processing' as const },
  { id: 'sheet-metal', name: 'Sheet Metal Brackets', fileCount: 156 },
  { id: 'fastener-library', name: 'Fastener Library', fileCount: 892 },
  { id: 'test-fixtures', name: 'Test Fixtures', fileCount: 34 },
  { id: 'supplier-drawings', name: 'Supplier Drawings', fileCount: 67, status: 'Extracted' as const },
];

export function VaultPage() {
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
          <div className="grid grid-cols-4 gap-4">
            {projects.map((project) => (
              <Link key={project.id} to={`/project/${project.id}`}>
                <ProjectCard
                  name={project.name}
                  fileCount={project.fileCount}
                  status={project.status}
                />
              </Link>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}