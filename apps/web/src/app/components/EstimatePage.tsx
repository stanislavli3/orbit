import { TopBar } from './TopBar';
import { CostImportCard } from './CostImportCard';
import { QuickEstimateCard } from './QuickEstimateCard';

export function EstimatePage() {
  return (
    <div className="flex-1 flex flex-col h-full bg-[#F9F9F9]">
      <TopBar title="Estimates" subtitle="Estimate new parts from what similar parts cost on past programs." />
      <div className="flex-1 overflow-y-auto px-8 py-8 space-y-6 max-w-5xl">
        <QuickEstimateCard />
        <CostImportCard />
        <CostImportCard
          endpoint="/api/parts/spend-imports/"
          queryKey="spend-imports"
          title="Import supplier spend / invoices"
          hint="CSV or Excel with supplier, part number or description, quantity, unit price, date and invoice/PO ref. Sample: samples/supplier_spend_sample.csv"
        />
      </div>
    </div>
  );
}
