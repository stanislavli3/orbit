import { Zap } from 'lucide-react';
import type { GalvanicReport } from '../../api/types';

const METHOD: Record<GalvanicReport['method'], string> = {
  placement_distance: 'parts placed near each other in the STEP assembly',
  assembly_structure: 'parts under the same parent subassembly',
  same_bom: 'flat BOM, every pair treated as touching',
};

export function GalvanicFlags({ report }: { report: GalvanicReport }) {
  return (
    <section className="bg-white border border-[#E8E0D3] rounded-xl p-4 break-inside-avoid">
      <h2 className="text-sm font-medium text-[#2B2824] mb-1 flex items-center gap-1.5">
        <Zap className="w-4 h-4 text-amber-600" /> Material pairs that may corrode ({report.flags.length})
      </h2>
      <p className="text-xs text-[#A89D91] mb-2">
        Galvanic check, {report.environment} environment (flag above {report.threshold_v.toFixed(2)} V) · contact = {METHOD[report.method]}
      </p>
      {report.flags.length === 0 && <p className="text-xs text-[#A89D91]">No dissimilar-metal pairs above the threshold.</p>}
      <ul className="space-y-3">
        {report.flags.map((f, i) => (
          <li key={i} className={`text-sm border-l-2 pl-3 ${f.severity === 'high' ? 'border-red-500' : 'border-amber-400'}`}>
            <div className="text-[#2B2824]">
              <span className={`text-xs uppercase font-semibold mr-2 ${f.severity === 'high' ? 'text-red-600' : 'text-amber-700'}`}>{f.severity}</span>
              <span className="font-medium">{f.parts.join(' ↔ ')}</span> — {f.title}
            </div>
            <div className="text-xs text-[#5A524A]">{f.detail}</div>
            <ul className="text-xs text-[#5A524A] list-disc ml-4 mt-1">
              {f.mitigations.map((m) => <li key={m}>{m}</li>)}
            </ul>
          </li>
        ))}
      </ul>
      <p className="text-[11px] text-[#A89D91] mt-2">{report.note}</p>
    </section>
  );
}
