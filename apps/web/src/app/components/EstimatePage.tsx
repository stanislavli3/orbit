import { TopBar } from './TopBar';
import { CostImportCard } from './CostImportCard';

export function EstimatePage() {
  return (
    <div className="flex-1 flex flex-col h-full bg-[#F9F9F9]">
      <TopBar title="Estimates" subtitle="Estimate new parts from what similar parts cost on past programs." />
      <div className="flex-1 overflow-y-auto px-8 py-8 space-y-6 max-w-5xl">
        <CostImportCard />
      </div>
    </div>
  );
}
