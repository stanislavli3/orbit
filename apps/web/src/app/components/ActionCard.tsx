import { LucideIcon } from 'lucide-react';

interface ActionCardProps {
  icon: LucideIcon;
  title: string;
  description: string;
  onClick?: () => void;
}

export function ActionCard({ icon: Icon, title, description, onClick }: ActionCardProps) {
  return (
    <button onClick={onClick} className="flex items-start gap-4 p-5 bg-white border border-[#E6E6E6] rounded-xl hover:bg-[#FAFAFA] transition-colors text-left w-full">
      <div className="mt-0.5">
        <Icon className="w-5 h-5 text-[#111111]" strokeWidth={1.5} />
      </div>
      <div className="flex-1">
        <h3 className="text-[#111111] mb-1">{title}</h3>
        <p className="text-[#6B7280] text-[13px] leading-relaxed">{description}</p>
      </div>
    </button>
  );
}
