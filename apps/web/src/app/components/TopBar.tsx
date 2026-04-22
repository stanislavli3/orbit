import { Search } from 'lucide-react';
import type { ReactNode } from 'react';

interface TopBarProps {
  title: string;
  subtitle: string;
  eyebrow?: ReactNode;
}

function SquiggleUnderline({ color = '#C66A4E', width = 180 }: { color?: string; width?: number }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 220 12"
      className="mt-1 -ml-[2px] h-[10px] -rotate-[0.5deg] block"
      style={{ width }}
      fill="none"
      preserveAspectRatio="none"
    >
      <path
        d="M2 7 Q 22 2, 44 6 T 88 5 Q 112 9, 136 4 T 180 6 Q 200 3, 218 7"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function TopBar({ title, subtitle, eyebrow }: TopBarProps) {
  return (
    <div className="border-b border-[#E8E0D3] bg-[#FFFCF7] px-8 pt-6 pb-5">
      <div className="flex items-end justify-between gap-6">
        <div className="min-w-0">
          {eyebrow && (
            <div className="text-[11px] uppercase tracking-[0.18em] text-[#A89D91] mb-1.5 font-medium">
              {eyebrow}
            </div>
          )}
          <h1 className="font-display text-[28px] leading-[1.15] text-[#2B2824] tracking-tight font-medium">
            {title}
          </h1>
          <SquiggleUnderline />
          <p className="text-[#8B7F73] text-sm mt-2 max-w-[720px]">{subtitle}</p>
        </div>
        <div className="relative shrink-0">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#A89D91]" />
          <input
            type="text"
            placeholder="Search"
            className="w-72 pl-9 pr-4 py-2 bg-[#FAF7F2] border border-[#E8E0D3] rounded-lg text-sm placeholder:text-[#A89D91] focus:outline-none focus:border-[#2B2824] focus:bg-white transition-colors"
          />
        </div>
      </div>
    </div>
  );
}
