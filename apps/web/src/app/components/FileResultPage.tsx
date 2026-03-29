import { Link, useParams } from 'react-router';
import { ArrowLeft } from 'lucide-react';

export function FileResultPage() {
  const { id, fileId } = useParams<{ id: string; fileId: string }>();
  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-[#F7F7F7]">
      <div className="border-b border-[#E6E6E6] bg-white px-8 py-5 flex items-center gap-3">
        <Link
          to={`/project/${id}`}
          className="w-8 h-8 flex items-center justify-center hover:bg-[#F4F4F4] rounded-lg transition-colors"
        >
          <ArrowLeft className="w-[18px] h-[18px] text-[#6B7280]" />
        </Link>
        <div>
          <h1 className="text-[#111111] mb-1 text-lg">File result</h1>
          <p className="text-[#6B7280] text-sm">Project {id} · File {fileId}</p>
        </div>
      </div>
      <div className="flex-1 flex items-center justify-center px-8">
        <div className="text-center max-w-md">
          <p className="text-[#111111] font-medium mb-2">Result view coming soon</p>
          <p className="text-[#6B7280] text-sm">
            Extraction details for this file will appear here once the result UI is built.
          </p>
        </div>
      </div>
    </div>
  );
}
