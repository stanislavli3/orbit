import { Download, AlertTriangle } from 'lucide-react';
import type { EngineeringProfile } from '../../api/types';

interface Props {
  profile: EngineeringProfile;
  fileName: string;
  onDownload: () => void;
}

function ConfidencePip({ value }: { value: number }) {
  const color =
    value >= 0.85 ? '#10B981' : value >= 0.6 ? '#F59E0B' : '#EF4444';
  return (
    <span className="flex items-center gap-1 tabular-nums text-[11px] font-medium" style={{ color }}>
      <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: color }} />
      {value.toFixed(2)}
    </span>
  );
}

interface FieldRowProps {
  label: string;
  value: React.ReactNode;
  confidence?: number | null;
}

function FieldRow({ label, value, confidence }: FieldRowProps) {
  return (
    <div className="flex items-center justify-between gap-3 py-2.5 border-b border-[#F3F4F6] last:border-0">
      <span className="text-[11px] font-semibold uppercase tracking-widest text-[#A89D91] w-24 flex-shrink-0">
        {label}
      </span>
      <span className="flex-1 text-[13px] text-[#2B2824] font-medium">{value ?? '—'}</span>
      {confidence != null && <ConfidencePip value={confidence} />}
    </div>
  );
}

export function EngineeringProfileCard({ profile, fileName, onDownload }: Props) {
  const hasProvenance =
    profile.provenance.sources.length > 0 || profile.provenance.warnings.length > 0;

  return (
    <div className="rounded-2xl border border-[#E8E0D3] bg-white overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-[#EEE6D8] bg-[#FFFCF7]">
        <div>
          <p className="text-base font-semibold text-[#2B2824] leading-none">
            {profile.part_number ?? fileName.replace(/\.[^.]+$/, '')}
          </p>
          {profile.part_number && (
            <p className="text-[11px] text-[#A89D91] mt-1">{fileName}</p>
          )}
        </div>
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-[#ECFDF5] text-[#065F46] border border-emerald-100">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
          Extracted
        </span>
      </div>

      {/* Fields */}
      <div className="px-5 py-1">
        <FieldRow label="Name" value={profile.name} />
        <FieldRow
          label="Material"
          value={profile.material?.value}
          confidence={profile.material?.confidence ?? null}
        />
        <FieldRow label="Category" value={profile.category} />
        <FieldRow label="Dimensions" value={profile.dimensions} />
        <FieldRow label="Revision" value={profile.revision} />
        <FieldRow
          label="Volume"
          value={profile.volume?.value}
          confidence={profile.volume?.confidence ?? null}
        />
      </div>

      {/* Provenance */}
      {hasProvenance && (
        <div className="px-5 pt-3 pb-4 border-t border-[#EEE6D8] bg-[#FFFCF7]">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-[#A89D91] mb-2">
            Provenance
          </p>
          {profile.provenance.sources.length > 0 && (
            <p className="text-[12px] text-[#8B7F73] mb-2">
              <span className="font-medium text-[#4A4038]">Sources: </span>
              {profile.provenance.sources.join(', ')}
            </p>
          )}
          {profile.provenance.warnings.map((w, i) => (
            <div key={i} className="flex items-start gap-1.5 text-[12px] text-[#92400E] mt-1">
              <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5 text-amber-500" strokeWidth={2} />
              {w}
            </div>
          ))}
        </div>
      )}

      {/* Footer */}
      <div className="flex justify-end px-5 py-3 border-t border-[#EEE6D8]">
        <button
          onClick={onDownload}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#E8E0D3] text-[12px] font-medium text-[#4A4038] hover:border-[#2B2824] hover:text-[#2B2824] transition-colors"
        >
          <Download className="w-3.5 h-3.5" strokeWidth={1.5} />
          Download JSON
        </button>
      </div>
    </div>
  );
}
