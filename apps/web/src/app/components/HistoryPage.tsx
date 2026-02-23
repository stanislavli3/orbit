import { Search, Filter, FileText, Upload, CheckCircle2, AlertCircle, Clock, Download, MoreVertical } from 'lucide-react';
import { TopBar } from './TopBar';

interface HistoryItem {
  id: string;
  type: 'extraction' | 'upload' | 'export';
  title: string;
  project: string;
  status: 'completed' | 'failed' | 'processing';
  timestamp: string;
  fileCount?: number;
  user: string;
}

const historyData: HistoryItem[] = [
  {
    id: '1',
    type: 'extraction',
    title: 'Metadata extraction completed',
    project: 'Gearbox Assembly',
    status: 'completed',
    timestamp: '2 hours ago',
    fileCount: 47,
    user: 'Sarah Chen',
  },
  {
    id: '2',
    type: 'upload',
    title: 'Files uploaded',
    project: 'Pump Housing Rev B',
    status: 'processing',
    timestamp: '3 hours ago',
    fileCount: 23,
    user: 'Marcus Williams',
  },
  {
    id: '3',
    type: 'export',
    title: 'JSON profiles exported',
    project: 'Sheet Metal Brackets',
    status: 'completed',
    timestamp: 'Today at 9:34 AM',
    fileCount: 156,
    user: 'You',
  },
  {
    id: '4',
    type: 'extraction',
    title: 'Metadata extraction failed',
    project: 'Test Fixtures',
    status: 'failed',
    timestamp: 'Yesterday at 4:22 PM',
    fileCount: 12,
    user: 'You',
  },
  {
    id: '5',
    type: 'upload',
    title: 'Files uploaded',
    project: 'Fastener Library',
    status: 'completed',
    timestamp: 'Yesterday at 2:15 PM',
    fileCount: 892,
    user: 'David Park',
  },
  {
    id: '6',
    type: 'extraction',
    title: 'Metadata extraction completed',
    project: 'Supplier Drawings',
    status: 'completed',
    timestamp: 'Feb 15 at 11:03 AM',
    fileCount: 67,
    user: 'Sarah Chen',
  },
  {
    id: '7',
    type: 'export',
    title: 'JSON profiles exported',
    project: 'Gearbox Assembly',
    status: 'completed',
    timestamp: 'Feb 15 at 9:45 AM',
    fileCount: 47,
    user: 'Marcus Williams',
  },
  {
    id: '8',
    type: 'upload',
    title: 'Files uploaded',
    project: 'Sheet Metal Brackets',
    status: 'completed',
    timestamp: 'Feb 14 at 3:30 PM',
    fileCount: 156,
    user: 'You',
  },
];

const typeIcons = {
  extraction: FileText,
  upload: Upload,
  export: Download,
};

const statusConfig = {
  completed: {
    icon: CheckCircle2,
    color: 'text-[#6B7280]',
    bgColor: 'bg-[#F4F4F4]',
    label: 'Completed',
  },
  failed: {
    icon: AlertCircle,
    color: 'text-[#DC2626]',
    bgColor: 'bg-[#FEF2F2]',
    label: 'Failed',
  },
  processing: {
    icon: Clock,
    color: 'text-[#6B7280]',
    bgColor: 'bg-[#F4F4F4]',
    label: 'Processing',
  },
};

export function HistoryPage() {
  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">
      <TopBar 
        title="History" 
        subtitle="Track all extraction runs, uploads, and system activities across your workspace."
      />
      
      <div className="flex-1 overflow-auto">
        <div className="max-w-[1400px] mx-auto px-8 py-8">
          {/* Filters and Search */}
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <button className="flex items-center gap-2 px-4 py-2 bg-white border border-[#E6E6E6] rounded-lg hover:bg-[#FAFAFA] transition-colors">
                <Filter className="w-4 h-4 text-[#6B7280]" strokeWidth={1.5} />
                <span className="text-sm text-[#111111]">Filter</span>
              </button>
              
              <div className="flex items-center gap-2">
                <button className="px-3 py-2 text-sm text-[#111111] bg-[#E6E6E6] rounded-lg">
                  All activity
                </button>
                <button className="px-3 py-2 text-sm text-[#6B7280] hover:text-[#111111] hover:bg-[#F4F4F4] rounded-lg transition-colors">
                  Extractions
                </button>
                <button className="px-3 py-2 text-sm text-[#6B7280] hover:text-[#111111] hover:bg-[#F4F4F4] rounded-lg transition-colors">
                  Uploads
                </button>
                <button className="px-3 py-2 text-sm text-[#6B7280] hover:text-[#111111] hover:bg-[#F4F4F4] rounded-lg transition-colors">
                  Exports
                </button>
              </div>
            </div>
            
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#6B7280]" />
              <input
                type="text"
                placeholder="Search history"
                className="w-64 pl-9 pr-4 py-2 bg-white border border-[#E6E6E6] rounded-lg text-sm placeholder:text-[#6B7280] focus:outline-none focus:border-[#111111] transition-colors"
              />
            </div>
          </div>

          {/* History List */}
          <div className="bg-white border border-[#E6E6E6] rounded-xl overflow-hidden">
            {/* Table Header */}
            <div className="grid grid-cols-12 gap-4 px-6 py-3 border-b border-[#E6E6E6] bg-[#FAFAFA]">
              <div className="col-span-5">
                <span className="text-[#6B7280] text-[12px] font-medium uppercase tracking-wide">Activity</span>
              </div>
              <div className="col-span-2">
                <span className="text-[#6B7280] text-[12px] font-medium uppercase tracking-wide">Project</span>
              </div>
              <div className="col-span-2">
                <span className="text-[#6B7280] text-[12px] font-medium uppercase tracking-wide">Status</span>
              </div>
              <div className="col-span-2">
                <span className="text-[#6B7280] text-[12px] font-medium uppercase tracking-wide">User</span>
              </div>
              <div className="col-span-1 flex justify-end">
                <span className="text-[#6B7280] text-[12px] font-medium uppercase tracking-wide">Actions</span>
              </div>
            </div>

            {/* Table Rows */}
            {historyData.map((item) => {
              const TypeIcon = typeIcons[item.type];
              const StatusIcon = statusConfig[item.status].icon;
              
              return (
                <div
                  key={item.id}
                  className="grid grid-cols-12 gap-4 px-6 py-4 border-b border-[#E6E6E6] last:border-b-0 hover:bg-[#FAFAFA] transition-colors group"
                >
                  {/* Activity */}
                  <div className="col-span-5 flex items-center gap-3">
                    <div className="w-9 h-9 bg-[#F4F4F4] rounded-lg flex items-center justify-center flex-shrink-0">
                      <TypeIcon className="w-[18px] h-[18px] text-[#6B7280]" strokeWidth={1.5} />
                    </div>
                    <div className="min-w-0">
                      <p className="text-[#111111] text-sm mb-0.5">{item.title}</p>
                      <p className="text-[#6B7280] text-[12px]">
                        {item.fileCount} files · {item.timestamp}
                      </p>
                    </div>
                  </div>

                  {/* Project */}
                  <div className="col-span-2 flex items-center">
                    <span className="text-[#111111] text-sm truncate">{item.project}</span>
                  </div>

                  {/* Status */}
                  <div className="col-span-2 flex items-center">
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium ${statusConfig[item.status].bgColor} ${statusConfig[item.status].color}`}>
                      <StatusIcon className="w-3 h-3" strokeWidth={2} />
                      {statusConfig[item.status].label}
                    </span>
                  </div>

                  {/* User */}
                  <div className="col-span-2 flex items-center">
                    <span className="text-[#6B7280] text-sm">{item.user}</span>
                  </div>

                  {/* Actions */}
                  <div className="col-span-1 flex items-center justify-end">
                    <button className="w-8 h-8 flex items-center justify-center hover:bg-[#E6E6E6] rounded-lg transition-colors opacity-0 group-hover:opacity-100">
                      <MoreVertical className="w-4 h-4 text-[#6B7280]" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between mt-6">
            <p className="text-[#6B7280] text-sm">
              Showing 8 of 247 activities
            </p>
            <div className="flex items-center gap-2">
              <button className="px-3 py-2 text-sm text-[#6B7280] hover:text-[#111111] hover:bg-white border border-[#E6E6E6] rounded-lg transition-colors disabled:opacity-50" disabled>
                Previous
              </button>
              <button className="px-3 py-2 text-sm text-[#111111] bg-white border border-[#E6E6E6] rounded-lg">
                1
              </button>
              <button className="px-3 py-2 text-sm text-[#6B7280] hover:text-[#111111] hover:bg-white border border-transparent rounded-lg transition-colors">
                2
              </button>
              <button className="px-3 py-2 text-sm text-[#6B7280] hover:text-[#111111] hover:bg-white border border-transparent rounded-lg transition-colors">
                3
              </button>
              <span className="px-2 text-[#6B7280]">...</span>
              <button className="px-3 py-2 text-sm text-[#6B7280] hover:text-[#111111] hover:bg-white border border-transparent rounded-lg transition-colors">
                31
              </button>
              <button className="px-3 py-2 text-sm text-[#6B7280] hover:text-[#111111] hover:bg-white border border-[#E6E6E6] rounded-lg transition-colors">
                Next
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
