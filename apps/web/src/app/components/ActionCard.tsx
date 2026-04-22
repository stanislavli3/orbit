import { LucideIcon, ChevronRight } from 'lucide-react';

interface ActionCardProps {
  icon: LucideIcon;
  title: string;
  description: string;
  onClick?: () => void;
  disabled?: boolean;
}

export function ActionCard({ icon: Icon, title, description, onClick, disabled }: ActionCardProps) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="group flex items-center gap-4 p-5 bg-white border border-[#E8E0D3] rounded-xl hover:border-[#C4B8A8] hover:shadow-[0_4px_16px_rgba(0,0,0,0.06)] transition-all duration-200 text-left w-full disabled:opacity-40 disabled:cursor-not-allowed"
    >
      <div className="w-10 h-10 bg-[#F2EDE3] rounded-xl flex items-center justify-center flex-shrink-0 group-hover:bg-[#ECECEC] group-disabled:group-hover:bg-[#F2EDE3] transition-colors">
        <Icon className="w-5 h-5 text-[#2B2824]" strokeWidth={1.5} />
      </div>
      <div className="flex-1 min-w-0">
        <h3 className="text-[#2B2824] text-[13px] font-semibold mb-0.5">{title}</h3>
        <p className="text-[#A89D91] text-[12px] leading-relaxed">{description}</p>
      </div>
      <ChevronRight className="w-4 h-4 text-[#D1D5DB] group-hover:text-[#A89D91] transition-colors flex-shrink-0" strokeWidth={1.5} />
    </button>
  );
}
