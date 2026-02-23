import { useState } from 'react';
import { ArrowLeft, Upload, FileText, Download, Folder, MoreVertical, File, CheckCircle2 } from 'lucide-react';
import { Link, useParams } from 'react-router';

const projectData: Record<string, {
  name: string;
  fileCount: number;
  status: string;
  files: Array<{
    id: string;
    name: string;
    type: string;
    size: string;
    uploaded: string;
    status: 'extracted' | 'pending' | 'failed';
  }>;
  profiles: Array<{
    id: string;
    partNumber: string;
    name: string;
    category: string;
    material?: string;
    dimensions?: string;
    extracted: string;
  }>;
}> = {
  'gearbox-assembly': {
    name: 'Gearbox Assembly',
    fileCount: 47,
    status: 'Extracted',
    files: [
      { id: '1', name: 'gearbox-housing.dwg', type: 'DWG', size: '2.4 MB', uploaded: '2 hours ago', status: 'extracted' },
      { id: '2', name: 'shaft-assembly.sldprt', type: 'SLDPRT', size: '1.8 MB', uploaded: '2 hours ago', status: 'extracted' },
      { id: '3', name: 'bearing-spec.pdf', type: 'PDF', size: '856 KB', uploaded: '2 hours ago', status: 'extracted' },
      { id: '4', name: 'gear-teeth-detail.dwg', type: 'DWG', size: '1.2 MB', uploaded: '2 hours ago', status: 'extracted' },
      { id: '5', name: 'cover-plate.step', type: 'STEP', size: '3.1 MB', uploaded: '2 hours ago', status: 'pending' },
      { id: '6', name: 'seal-assembly.sldasm', type: 'SLDASM', size: '945 KB', uploaded: '2 hours ago', status: 'extracted' },
    ],
    profiles: [
      { 
        id: '1', 
        partNumber: 'GB-1001-A', 
        name: 'Gearbox Housing', 
        category: 'Housing',
        material: 'Aluminum 6061-T6',
        dimensions: '240 × 180 × 120 mm',
        extracted: '2 hours ago'
      },
      { 
        id: '2', 
        partNumber: 'GB-2045', 
        name: 'Main Shaft', 
        category: 'Shaft',
        material: 'Steel 4140',
        dimensions: 'Ø32 × 200 mm',
        extracted: '2 hours ago'
      },
      { 
        id: '3', 
        partNumber: 'GB-3012', 
        name: 'Input Gear', 
        category: 'Gear',
        material: 'Steel 8620',
        dimensions: 'Ø85 × 25 mm',
        extracted: '2 hours ago'
      },
      { 
        id: '4', 
        partNumber: 'GB-4008', 
        name: 'Cover Plate', 
        category: 'Cover',
        material: 'Aluminum 6061-T6',
        dimensions: '250 × 190 × 8 mm',
        extracted: '2 hours ago'
      },
      { 
        id: '5', 
        partNumber: 'GB-5002', 
        name: 'Bearing Retainer', 
        category: 'Fastener',
        material: 'Steel 1018',
        dimensions: 'Ø45 × 12 mm',
        extracted: '2 hours ago'
      },
    ],
  },
};

export function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [activeTab, setActiveTab] = useState<'vault' | 'library'>('vault');
  
  const project = id ? projectData[id] : null;
  
  if (!project) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-[#6B7280]">Project not found</p>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="border-b border-[#E6E6E6] bg-white px-8 py-5">
        <div className="flex items-center gap-3 mb-4">
          <Link 
            to="/vault"
            className="w-8 h-8 flex items-center justify-center hover:bg-[#F4F4F4] rounded-lg transition-colors"
          >
            <ArrowLeft className="w-[18px] h-[18px] text-[#6B7280]" />
          </Link>
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <h1 className="text-[#111111]">{project.name}</h1>
              <span className="px-2 py-0.5 bg-[#F4F4F4] text-[#111111] rounded-full text-[11px] font-medium">
                {project.status}
              </span>
            </div>
            <p className="text-[#6B7280] text-sm">
              {project.fileCount} files · Last updated 2 hours ago
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button className="px-4 py-2 bg-white border border-[#E6E6E6] rounded-lg hover:bg-[#FAFAFA] transition-colors text-sm text-[#111111]">
              <Download className="w-4 h-4 inline mr-2" strokeWidth={1.5} />
              Export
            </button>
            <button className="px-4 py-2 bg-[#111111] text-white rounded-lg hover:bg-[#2A2A2A] transition-colors text-sm">
              <Upload className="w-4 h-4 inline mr-2" strokeWidth={1.5} />
              Upload files
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex items-center gap-6 border-b border-[#E6E6E6] -mb-5">
          <button
            onClick={() => setActiveTab('vault')}
            className={`pb-4 border-b-2 transition-colors ${
              activeTab === 'vault'
                ? 'border-[#111111] text-[#111111]'
                : 'border-transparent text-[#6B7280] hover:text-[#111111]'
            }`}
          >
            <span className="text-sm flex items-center gap-2">
              <Folder className="w-4 h-4" strokeWidth={1.5} />
              Vault
            </span>
          </button>
          <button
            onClick={() => setActiveTab('library')}
            className={`pb-4 border-b-2 transition-colors ${
              activeTab === 'library'
                ? 'border-[#111111] text-[#111111]'
                : 'border-transparent text-[#6B7280] hover:text-[#111111]'
            }`}
          >
            <span className="text-sm flex items-center gap-2">
              <FileText className="w-4 h-4" strokeWidth={1.5} />
              Library
            </span>
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto bg-[#F7F7F7]">
        <div className="max-w-[1400px] mx-auto px-8 py-8">
          {activeTab === 'vault' ? (
            /* Vault - File List */
            <div className="bg-white border border-[#E6E6E6] rounded-xl overflow-hidden">
              {/* Table Header */}
              <div className="grid grid-cols-12 gap-4 px-6 py-3 border-b border-[#E6E6E6] bg-[#FAFAFA]">
                <div className="col-span-5">
                  <span className="text-[#6B7280] text-[12px] font-medium uppercase tracking-wide">Name</span>
                </div>
                <div className="col-span-2">
                  <span className="text-[#6B7280] text-[12px] font-medium uppercase tracking-wide">Type</span>
                </div>
                <div className="col-span-2">
                  <span className="text-[#6B7280] text-[12px] font-medium uppercase tracking-wide">Size</span>
                </div>
                <div className="col-span-2">
                  <span className="text-[#6B7280] text-[12px] font-medium uppercase tracking-wide">Status</span>
                </div>
                <div className="col-span-1 flex justify-end">
                  <span className="text-[#6B7280] text-[12px] font-medium uppercase tracking-wide">Actions</span>
                </div>
              </div>

              {/* File Rows */}
              {project.files.map((file) => (
                <div
                  key={file.id}
                  className="grid grid-cols-12 gap-4 px-6 py-4 border-b border-[#E6E6E6] last:border-b-0 hover:bg-[#FAFAFA] transition-colors group cursor-pointer"
                >
                  {/* Name */}
                  <div className="col-span-5 flex items-center gap-3">
                    <div className="w-9 h-9 bg-[#F4F4F4] rounded-lg flex items-center justify-center flex-shrink-0">
                      <File className="w-[18px] h-[18px] text-[#6B7280]" strokeWidth={1.5} />
                    </div>
                    <div className="min-w-0">
                      <p className="text-[#111111] text-sm mb-0.5 truncate">{file.name}</p>
                      <p className="text-[#6B7280] text-[12px]">Uploaded {file.uploaded}</p>
                    </div>
                  </div>

                  {/* Type */}
                  <div className="col-span-2 flex items-center">
                    <span className="px-2 py-1 bg-[#F4F4F4] text-[#6B7280] rounded text-[11px] font-medium">
                      {file.type}
                    </span>
                  </div>

                  {/* Size */}
                  <div className="col-span-2 flex items-center">
                    <span className="text-[#6B7280] text-sm">{file.size}</span>
                  </div>

                  {/* Status */}
                  <div className="col-span-2 flex items-center">
                    {file.status === 'extracted' ? (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-[#F4F4F4] text-[#6B7280]">
                        <CheckCircle2 className="w-3 h-3" strokeWidth={2} />
                        Extracted
                      </span>
                    ) : (
                      <span className="px-2.5 py-1 rounded-full text-[11px] font-medium bg-[#FEF2F2] text-[#DC2626]">
                        Pending
                      </span>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="col-span-1 flex items-center justify-end">
                    <button className="w-8 h-8 flex items-center justify-center hover:bg-[#E6E6E6] rounded-lg transition-colors opacity-0 group-hover:opacity-100">
                      <MoreVertical className="w-4 h-4 text-[#6B7280]" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            /* Library - Extracted Profiles */
            <div className="bg-white border border-[#E6E6E6] rounded-xl overflow-hidden">
              {/* Table Header */}
              <div className="grid grid-cols-12 gap-4 px-6 py-3 border-b border-[#E6E6E6] bg-[#FAFAFA]">
                <div className="col-span-2">
                  <span className="text-[#6B7280] text-[12px] font-medium uppercase tracking-wide">Part Number</span>
                </div>
                <div className="col-span-3">
                  <span className="text-[#6B7280] text-[12px] font-medium uppercase tracking-wide">Name</span>
                </div>
                <div className="col-span-2">
                  <span className="text-[#6B7280] text-[12px] font-medium uppercase tracking-wide">Category</span>
                </div>
                <div className="col-span-2">
                  <span className="text-[#6B7280] text-[12px] font-medium uppercase tracking-wide">Material</span>
                </div>
                <div className="col-span-2">
                  <span className="text-[#6B7280] text-[12px] font-medium uppercase tracking-wide">Dimensions</span>
                </div>
                <div className="col-span-1 flex justify-end">
                  <span className="text-[#6B7280] text-[12px] font-medium uppercase tracking-wide">Actions</span>
                </div>
              </div>

              {/* Profile Rows */}
              {project.profiles.map((profile) => (
                <div
                  key={profile.id}
                  className="grid grid-cols-12 gap-4 px-6 py-4 border-b border-[#E6E6E6] last:border-b-0 hover:bg-[#FAFAFA] transition-colors group cursor-pointer"
                >
                  {/* Part Number */}
                  <div className="col-span-2 flex items-center">
                    <span className="text-[#111111] text-sm font-medium font-mono">{profile.partNumber}</span>
                  </div>

                  {/* Name */}
                  <div className="col-span-3 flex items-center">
                    <span className="text-[#111111] text-sm">{profile.name}</span>
                  </div>

                  {/* Category */}
                  <div className="col-span-2 flex items-center">
                    <span className="px-2 py-1 bg-[#F4F4F4] text-[#6B7280] rounded text-[11px] font-medium">
                      {profile.category}
                    </span>
                  </div>

                  {/* Material */}
                  <div className="col-span-2 flex items-center">
                    <span className="text-[#6B7280] text-sm">{profile.material || '—'}</span>
                  </div>

                  {/* Dimensions */}
                  <div className="col-span-2 flex items-center">
                    <span className="text-[#6B7280] text-sm font-mono text-[13px]">{profile.dimensions || '—'}</span>
                  </div>

                  {/* Actions */}
                  <div className="col-span-1 flex items-center justify-end">
                    <button className="w-8 h-8 flex items-center justify-center hover:bg-[#E6E6E6] rounded-lg transition-colors opacity-0 group-hover:opacity-100">
                      <MoreVertical className="w-4 h-4 text-[#6B7280]" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
