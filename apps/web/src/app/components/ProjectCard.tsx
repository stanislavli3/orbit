import { Folder, MoreVertical } from 'lucide-react';

interface ProjectCardProps {
  name: string;
  fileCount: number;
  status?: 'Processing' | 'Extracted' | 'Failed';
}

export function ProjectCard({ name, fileCount, status }: ProjectCardProps) {
  const statusColors = {
    Processing: 'bg-[#F4F4F4] text-[#6B7280]',
    Extracted: 'bg-[#F4F4F4] text-[#111111]',
    Failed: 'bg-[#FEF2F2] text-[#DC2626]',
  };

  return (
    <div className="bg-white border border-[#E6E6E6] rounded-xl p-5 hover:bg-[#FAFAFA] transition-colors group cursor-pointer">
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-2">
          <h3 className="text-[#111111] text-[15px]">{name}</h3>
          {status && (
            <span className={`px-2 py-0.5 rounded-full text-[11px] font-medium ${statusColors[status]}`}>
              {status}
            </span>
          )}
        </div>
        <button className="opacity-0 group-hover:opacity-100 transition-opacity p-1 hover:bg-[#E6E6E6] rounded">
          <MoreVertical className="w-4 h-4 text-[#6B7280]" />
        </button>
      </div>
      
      <div className="flex items-center justify-center py-6 mb-4">
        <Folder className="w-12 h-12 text-[#E6E6E6]" strokeWidth={1.5} />
      </div>
      
      <p className="text-[#6B7280] text-[13px]">
        {fileCount} files · Extracted profiles
      </p>
    </div>
  );
}
