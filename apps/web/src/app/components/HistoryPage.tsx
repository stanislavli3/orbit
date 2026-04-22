import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router';
import { Search, FileText, Upload, Download, CheckCircle2, AlertCircle, Clock, MessageSquare, MoreVertical, Inbox } from 'lucide-react';
import { TopBar } from './TopBar';
import { useApiClient } from '../../api/client';
import type { HistoryEvent } from '../../api/types';

type ActivityFilter = 'all' | 'upload' | 'export' | 'chat';

const typeIcons = {
  upload: Upload,
  export: Download,
  chat: MessageSquare,
};

const typeLabels = {
  upload: 'File uploaded',
  export: 'JSON export',
  chat: 'New chat',
};

const statusConfig: Record<string, { icon: typeof CheckCircle2; color: string; bgColor: string; label: string }> = {
  completed: {
    icon: CheckCircle2,
    color: 'text-[#8B7F73]',
    bgColor: 'bg-[#F2EDE3]',
    label: 'Completed',
  },
  processed: {
    icon: CheckCircle2,
    color: 'text-[#8B7F73]',
    bgColor: 'bg-[#F2EDE3]',
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
    color: 'text-[#8B7F73]',
    bgColor: 'bg-[#F2EDE3]',
    label: 'Processing',
  },
  uploaded: {
    icon: Clock,
    color: 'text-[#8B7F73]',
    bgColor: 'bg-[#F2EDE3]',
    label: 'Uploaded',
  },
};

function formatTimestamp(iso: string): string {
  const date = new Date(iso);
  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const itemDate = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const diffDays = Math.round((todayStart.getTime() - itemDate.getTime()) / (1000 * 60 * 60 * 24));

  const timeStr = date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });

  if (diffDays === 0) return `Today at ${timeStr}`;
  if (diffDays === 1) return `Yesterday at ${timeStr}`;
  return date.toLocaleDateString([], { month: 'short', day: 'numeric' }) + ` at ${timeStr}`;
}

const periodLabels: Record<string, string> = {
  today: 'Today',
  last7days: 'Last 7 days',
  older: 'Older',
};

export function HistoryPage() {
  const [searchParams] = useSearchParams();
  const [activityFilter, setActivityFilter] = useState<ActivityFilter>('all');
  const [search, setSearch] = useState('');
  const apiFetch = useApiClient();

  const period = searchParams.get('period') ?? '';

  const { data: events = [], isLoading, isError } = useQuery<HistoryEvent[]>({
    queryKey: ['history', period],
    queryFn: async () => {
      const url = period ? `/api/history/?period=${period}` : '/api/history/';
      const res = await apiFetch(url);
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
  });

  const filtered = events.filter((e) => {
    if (activityFilter !== 'all' && e.type !== activityFilter) return false;
    if (search) {
      const q = search.toLowerCase();
      if (!e.title.toLowerCase().includes(q) && !e.project.toLowerCase().includes(q) && !e.detail.toLowerCase().includes(q)) return false;
    }
    return true;
  });

  const periodLabel = period ? periodLabels[period] : null;

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">
      <TopBar
        title="History"
        subtitle="Track all file uploads, JSON exports, and chat sessions across your workspace."
      />

      <div className="flex-1 overflow-auto">
        <div className="max-w-[1400px] mx-auto px-8 py-8">
          {/* Filters and Search */}
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                {(['all', 'upload', 'export', 'chat'] as ActivityFilter[]).map((f) => (
                  <button
                    key={f}
                    onClick={() => setActivityFilter(f)}
                    className={`px-3 py-2 text-sm rounded-lg transition-colors ${
                      activityFilter === f
                        ? 'text-[#2B2824] bg-[#E8E0D3]'
                        : 'text-[#8B7F73] hover:text-[#2B2824] hover:bg-[#F2EDE3]'
                    }`}
                  >
                    {f === 'all' ? 'All activity' : f === 'upload' ? 'Uploads' : f === 'export' ? 'Exports' : 'Chats'}
                  </button>
                ))}
              </div>

              {periodLabel && (
                <span className="text-xs text-[#8B7F73] bg-[#F2EDE3] border border-[#E8E0D3] px-2.5 py-1 rounded-full">
                  {periodLabel}
                </span>
              )}
            </div>

            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#8B7F73]" />
              <input
                type="text"
                placeholder="Search history"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-64 pl-9 pr-4 py-2 bg-white border border-[#E8E0D3] rounded-lg text-sm placeholder:text-[#8B7F73] focus:outline-none focus:border-[#2B2824] transition-colors"
              />
            </div>
          </div>

          {/* History List */}
          <div className="bg-white border border-[#E8E0D3] rounded-xl overflow-hidden">
            {/* Table Header */}
            <div className="grid grid-cols-12 gap-4 px-6 py-3 border-b border-[#E8E0D3] bg-[#FFFCF7]">
              <div className="col-span-5">
                <span className="text-[#8B7F73] text-[12px] font-medium uppercase tracking-wide">Activity</span>
              </div>
              <div className="col-span-2">
                <span className="text-[#8B7F73] text-[12px] font-medium uppercase tracking-wide">Project</span>
              </div>
              <div className="col-span-2">
                <span className="text-[#8B7F73] text-[12px] font-medium uppercase tracking-wide">Status</span>
              </div>
              <div className="col-span-2">
                <span className="text-[#8B7F73] text-[12px] font-medium uppercase tracking-wide">Type</span>
              </div>
              <div className="col-span-1 flex justify-end">
                <span className="text-[#8B7F73] text-[12px] font-medium uppercase tracking-wide">Actions</span>
              </div>
            </div>

            {isLoading && (
              <div className="flex items-center justify-center py-16 text-[#8B7F73] text-sm">
                Loading...
              </div>
            )}

            {isError && (
              <div className="flex items-center justify-center py-16 text-[#DC2626] text-sm">
                Failed to load history.
              </div>
            )}

            {!isLoading && !isError && filtered.length === 0 && (
              <div className="flex flex-col items-center justify-center py-16 gap-3">
                <div className="w-10 h-10 bg-[#F2EDE3] rounded-lg flex items-center justify-center">
                  <Inbox className="w-5 h-5 text-[#A89D91]" strokeWidth={1.5} />
                </div>
                <p className="text-[#8B7F73] text-sm">No activity found</p>
              </div>
            )}

            {!isLoading && !isError && filtered.map((item) => {
              const TypeIcon = typeIcons[item.type] ?? FileText;
              const statusKey = item.status in statusConfig ? item.status : 'completed';
              const sc = statusConfig[statusKey];
              const StatusIcon = sc.icon;

              return (
                <div
                  key={item.id}
                  className="grid grid-cols-12 gap-4 px-6 py-4 border-b border-[#E8E0D3] last:border-b-0 hover:bg-[#FFFCF7] transition-colors group"
                >
                  {/* Activity */}
                  <div className="col-span-5 flex items-center gap-3">
                    <div className="w-9 h-9 bg-[#F2EDE3] rounded-lg flex items-center justify-center flex-shrink-0">
                      <TypeIcon className="w-[18px] h-[18px] text-[#8B7F73]" strokeWidth={1.5} />
                    </div>
                    <div className="min-w-0">
                      <p className="text-[#2B2824] text-sm mb-0.5">{item.title}</p>
                      <p className="text-[#8B7F73] text-[12px] truncate">
                        {item.detail} · {formatTimestamp(item.created_at)}
                      </p>
                    </div>
                  </div>

                  {/* Project */}
                  <div className="col-span-2 flex items-center">
                    <span className="text-[#2B2824] text-sm truncate">{item.project}</span>
                  </div>

                  {/* Status */}
                  <div className="col-span-2 flex items-center">
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium ${sc.bgColor} ${sc.color}`}>
                      <StatusIcon className="w-3 h-3" strokeWidth={2} />
                      {sc.label}
                    </span>
                  </div>

                  {/* Type */}
                  <div className="col-span-2 flex items-center">
                    <span className="text-[#8B7F73] text-sm">{typeLabels[item.type]}</span>
                  </div>

                  {/* Actions */}
                  <div className="col-span-1 flex items-center justify-end">
                    <button className="w-8 h-8 flex items-center justify-center hover:bg-[#E8E0D3] rounded-lg transition-colors opacity-0 group-hover:opacity-100">
                      <MoreVertical className="w-4 h-4 text-[#8B7F73]" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          {!isLoading && !isError && filtered.length > 0 && (
            <div className="mt-6">
              <p className="text-[#8B7F73] text-sm">
                Showing {filtered.length} {filtered.length === 1 ? 'activity' : 'activities'}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
