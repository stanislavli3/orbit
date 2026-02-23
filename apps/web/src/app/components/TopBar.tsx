import { Search } from 'lucide-react';

interface TopBarProps {
  title: string;
  subtitle: string;
}

export function TopBar({ title, subtitle }: TopBarProps) {
  return (
    <div className="border-b border-[#E6E6E6] bg-white px-8 py-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[#111111] mb-1">{title}</h1>
          <p className="text-[#6B7280] text-sm">{subtitle}</p>
        </div>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#6B7280]" />
          <input
            type="text"
            placeholder="Search"
            className="w-72 pl-9 pr-4 py-2 bg-white border border-[#E6E6E6] rounded-lg text-sm placeholder:text-[#6B7280] focus:outline-none focus:border-[#111111] transition-colors"
          />
        </div>
      </div>
    </div>
  );
}
