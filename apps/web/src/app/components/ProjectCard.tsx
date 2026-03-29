import { MoreVertical, Pencil, Trash2 } from 'lucide-react';
import { Popover, PopoverContent, PopoverTrigger } from './ui/popover';

interface ProjectCardProps {
  name: string;
  fileCount: number;
  description?: string;
  fileTypes?: string[];
  onRename?: () => void;
  onDelete?: () => void;
}

const FILE_TAG_STYLE: Record<string, { bg: string; text: string; label: string }> = {
  step: { bg: 'bg-blue-50',    text: 'text-blue-600',    label: 'STP' },
  stp:  { bg: 'bg-blue-50',    text: 'text-blue-600',    label: 'STP' },
  pdf:  { bg: 'bg-red-50',     text: 'text-red-500',     label: 'PDF' },
  dwg:  { bg: 'bg-amber-50',   text: 'text-amber-600',   label: 'DWG' },
  dxf:  { bg: 'bg-amber-50',   text: 'text-amber-600',   label: 'DXF' },
  iges: { bg: 'bg-emerald-50', text: 'text-emerald-600', label: 'IGS' },
  igs:  { bg: 'bg-emerald-50', text: 'text-emerald-600', label: 'IGS' },
};

const ACCENTS = [
  { bar: '#93C5FD', light: '#EFF6FF' },
  { bar: '#FCD34D', light: '#FFFBEB' },
  { bar: '#6EE7B7', light: '#ECFDF5' },
  { bar: '#C4B5FD', light: '#F5F3FF' },
  { bar: '#FCA5A5', light: '#FEF2F2' },
];

function nameHash(s: string): number {
  let h = 5381;
  for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) & 0xffffffff;
  return Math.abs(h);
}

function FileTypeTag({ ext }: { ext: string }) {
  const s = FILE_TAG_STYLE[ext.toLowerCase()];
  if (!s) return null;
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-bold tracking-wider ${s.bg} ${s.text}`}>
      {s.label}
    </span>
  );
}

export function ProjectCard({ name, fileCount, description, fileTypes, onRename, onDelete }: ProjectCardProps) {
  const accent = ACCENTS[nameHash(name) % ACCENTS.length];
  const uniqueTypes = [...new Set((fileTypes ?? []).map(t => t.toLowerCase()))].slice(0, 4);

  return (
    <div className="bg-white border border-[#E6E6E6] rounded-xl overflow-hidden hover:border-[#C4C4C4] hover:shadow-[0_8px_24px_rgba(0,0,0,0.07)] hover:-translate-y-0.5 transition-all duration-200 group cursor-pointer">
      {/* Card art */}
      <div
        className="h-[96px] relative overflow-hidden flex items-center justify-center"
        style={{ background: `linear-gradient(135deg, ${accent.light} 0%, #F5F5F5 100%)` }}
      >
        <div
          className="absolute inset-0 opacity-25"
          style={{
            backgroundImage: 'radial-gradient(circle, #9CA3AF 1px, transparent 1px)',
            backgroundSize: '14px 14px',
          }}
        />
        <div
          className="absolute left-0 top-0 bottom-0 w-[3px]"
          style={{ background: accent.bar }}
        />
        <div className="relative z-10 flex items-end gap-1.5">
          {[...Array(Math.min(Math.max(fileCount, 1), 3))].map((_, i) => (
            <div
              key={i}
              className="bg-white border border-[#E6E6E6] rounded-lg shadow-sm flex-shrink-0 p-1 pt-1.5"
              style={{
                width: 30 - i * 4,
                height: 38 - i * 5,
                transform: `rotate(${(i - 1) * 5}deg) translateY(${i * 2}px)`,
                opacity: 1 - i * 0.2,
              }}
            >
              <div className="space-y-0.5">
                <div className="h-0.5 rounded-full" style={{ background: accent.bar, width: '60%', opacity: 0.7 }} />
                <div className="h-0.5 bg-[#E0E0E0] rounded-full w-4/5" />
                <div className="h-0.5 bg-[#E0E0E0] rounded-full w-1/2" />
              </div>
            </div>
          ))}
        </div>

        <Popover>
          <PopoverTrigger asChild>
            <button
              onClick={e => e.stopPropagation()}
              className="absolute top-2.5 right-2.5 w-7 h-7 flex items-center justify-center bg-white/80 backdrop-blur-sm border border-[#E6E6E6] rounded-lg shadow-sm opacity-0 group-hover:opacity-100 transition-all hover:bg-white"
            >
              <MoreVertical className="w-3.5 h-3.5 text-[#6B7280]" strokeWidth={2} />
            </button>
          </PopoverTrigger>
          <PopoverContent
            align="end"
            sideOffset={6}
            className="w-36 p-1"
            onClick={e => e.stopPropagation()}
          >
            <button
              onClick={e => { e.stopPropagation(); onRename?.(); }}
              className="w-full flex items-center gap-2 px-2.5 py-1.5 text-[13px] text-[#374151] rounded hover:bg-[#F4F4F4] transition-colors"
            >
              <Pencil className="w-3.5 h-3.5" strokeWidth={1.75} />
              Rename
            </button>
            <button
              onClick={e => { e.stopPropagation(); onDelete?.(); }}
              className="w-full flex items-center gap-2 px-2.5 py-1.5 text-[13px] text-[#DC2626] rounded hover:bg-[#FEF2F2] transition-colors"
            >
              <Trash2 className="w-3.5 h-3.5" strokeWidth={1.75} />
              Delete
            </button>
          </PopoverContent>
        </Popover>
      </div>

      {/* Card body */}
      <div className="px-4 pt-3.5 pb-4">
        <h3 className="text-[#111111] text-[13px] font-semibold leading-tight truncate mb-1">
          {name}
        </h3>
        {description ? (
          <p className="text-[#9CA3AF] text-[11px] leading-relaxed line-clamp-1 mb-3">{description}</p>
        ) : (
          <div className="mb-3" />
        )}
        <div className="flex items-center justify-between">
          <span className="text-[11px] text-[#9CA3AF] tabular-nums">
            {fileCount} {fileCount === 1 ? 'file' : 'files'}
          </span>
          {uniqueTypes.length > 0 ? (
            <div className="flex items-center gap-1">
              {uniqueTypes.map(t => <FileTypeTag key={t} ext={t} />)}
            </div>
          ) : fileCount > 0 ? (
            <div className="flex items-center gap-1">
              {Array.from({ length: Math.min(fileCount, 4) }).map((_, i) => (
                <div
                  key={i}
                  className="w-1.5 h-1.5 rounded-full"
                  style={{ background: accent.bar, opacity: 1 - i * 0.2 }}
                />
              ))}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
