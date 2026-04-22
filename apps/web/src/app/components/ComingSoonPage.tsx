import { TopBar } from './TopBar';

interface ComingSoonPageProps {
  title: string;
  subtitle?: string;
  description?: string;
}

export function ComingSoonPage({ title, subtitle = '', description }: ComingSoonPageProps) {
  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">
      <TopBar title={title} subtitle={subtitle} />
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center max-w-sm">
          <div className="w-12 h-12 bg-[#F2EDE3] rounded-xl flex items-center justify-center mx-auto mb-4">
            <div className="w-5 h-5 rounded-full border-2 border-dashed border-[#D1D5DB]" />
          </div>
          <p className="text-[#2B2824] text-sm font-semibold mb-1">{title}</p>
          <p className="text-[#A89D91] text-sm">
            {description ?? 'This feature is coming soon.'}
          </p>
        </div>
      </div>
    </div>
  );
}
