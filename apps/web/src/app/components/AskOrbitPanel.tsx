import { useState } from 'react';
import { Link } from 'react-router';
import ReactMarkdown from 'react-markdown';
import { Loader2, Sparkles } from 'lucide-react';
import { useApiClient } from '../../api/client';
import type { AskResponse } from '../../api/types';

/** SCRUM-25: ask a question with this BOM (bomId) or one BOM row (rowId) as context. */
export function AskOrbitPanel({ bomId, rowId, placeholder }: { bomId?: number; rowId?: number; placeholder?: string }) {
  const apiFetch = useApiClient();
  const [question, setQuestion] = useState('');
  const [data, setData] = useState<AskResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function ask(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim()) return;
    setLoading(true);
    setError('');
    try {
      const res = await apiFetch('/api/assistant/ask/', {
        method: 'POST',
        body: JSON.stringify({ question, bom_id: bomId, row_id: rowId }),
      });
      if (!res.ok) throw new Error('Orbit could not answer that.');
      setData(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Orbit could not answer that.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-white border border-[#E8E0D3] rounded-xl p-4 space-y-3 text-sm">
      <form onSubmit={ask} className="flex items-center gap-2">
        <Sparkles className="w-4 h-4 text-[#8B7F73] shrink-0" />
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={placeholder ?? 'Ask Orbit about this…'}
          className="flex-1 px-3 py-1.5 rounded-lg border border-[#E8E0D3] focus:border-[#8B7F73] focus:outline-none"
        />
        <button
          type="submit"
          disabled={loading || !question.trim()}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#2B2824] text-white hover:opacity-90 disabled:opacity-50"
        >
          {loading && <Loader2 className="w-4 h-4 animate-spin" />}
          Ask Orbit
        </button>
      </form>
      {error && <p className="text-xs text-[#DC2626]">{error}</p>}
      {data && (
        <div className="space-y-2">
          <div className="prose prose-sm max-w-none text-[#2B2824]">
            <ReactMarkdown>{data.answer}</ReactMarkdown>
          </div>
          {data.mode === 'ai' && data.sources.length > 0 && (
            <ol className="text-xs text-[#8B7F73] space-y-0.5">
              {data.sources.map((s) => (
                <li key={s.n}>
                  [{s.n}] <Link to={s.link} className="hover:underline">{s.citation}</Link>
                </li>
              ))}
            </ol>
          )}
        </div>
      )}
    </div>
  );
}
