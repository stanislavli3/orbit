import { Send, Sparkles, FileText, Search, Code, Lightbulb } from 'lucide-react';
import { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { TopBar } from './TopBar';
import { useApiClient } from '../../api/client';
import type { AssistantResponse, AssistantSourceFile, SessionMessagesResponse } from '../../api/types';

const suggestedPrompts = [
  {
    icon: FileText,
    title: 'Analyze drawing set',
    description: 'Extract metadata from uploaded CAD files and drawings',
  },
  {
    icon: Search,
    title: 'Search for similar parts',
    description: 'Find components with matching specifications',
  },
  {
    icon: Code,
    title: 'Generate JSON profile',
    description: 'Create canonical profiles from engineering files',
  },
  {
    icon: Lightbulb,
    title: 'Identify design patterns',
    description: 'Discover common elements across your projects',
  },
];

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: AssistantSourceFile[];
  isPending?: boolean;
}

const newId = (prefix: string) =>
  `${prefix}-${typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : Date.now()}`;

interface AssistantPageProps {
  initialSessionId?: string | null;
}

export function AssistantPage({ initialSessionId }: AssistantPageProps) {
  const apiFetch = useApiClient();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(initialSessionId ?? null);
  const [isLoadingMessages, setIsLoadingMessages] = useState(!!initialSessionId);

  useEffect(() => {
    if (!initialSessionId) return;
    setIsLoadingMessages(true);
    apiFetch(`/api/assistant/sessions/${initialSessionId}/messages/`)
      .then((r) => r.json())
      .then((data: SessionMessagesResponse) => {
        setMessages(
          data.messages.map((msg) => ({
            id: newId(msg.role === 'user' ? 'u' : 'a'),
            role: msg.role,
            content: msg.content,
            sources: [],
          }))
        );
      })
      .catch(() => {})
      .finally(() => setIsLoadingMessages(false));
  }, [initialSessionId]); // eslint-disable-line react-hooks/exhaustive-deps

  const buildSources = (payload: AssistantResponse): AssistantSourceFile[] => {
    if (payload.source_files?.length) return payload.source_files;
    if (payload.sources?.length) {
      return payload.sources.map((id) => ({ id, name: `File #${id}` }));
    }
    return [];
  };

  const replacePending = (
    pendingId: string,
    content: string,
    sources: AssistantSourceFile[],
    isError = false
  ) => {
    setMessages((prev) =>
      prev.map((msg) =>
        msg.id === pendingId ? { ...msg, content, sources, isPending: false, role: 'assistant' } : msg
      )
    );
    if (isError) {
      setError(content);
    }
  };

  const handleSend = async (customInput?: string) => {
    const text = (customInput ?? input).trim();
    if (!text || isSending) return;

    const userMessage: Message = { id: newId('u'), role: 'user', content: text };
    const pendingId = newId('a');

    setMessages((prev) => [
      ...prev,
      userMessage,
      { id: pendingId, role: 'assistant', content: '', isPending: true },
    ]);
    setInput('');
    setIsSending(true);
    setError(null);

    try {
      const response = await apiFetch('/api/assistant/chat/', {
        method: 'POST',
        body: JSON.stringify({
          message: text,
          ...(sessionId ? { session_id: sessionId } : {}),
        }),
      });

      const data = (await response.json()) as AssistantResponse;
      const sources = buildSources(data);

      if (!response.ok) {
        replacePending(pendingId, data.error || 'AI assistant is not configured.', sources, true);
        return;
      }

      if (!sessionId && data.session_id) {
        setSessionId(data.session_id);
      }

      replacePending(pendingId, data.response, sources);
    } catch {
      replacePending(pendingId, 'AI assistant is not configured.', [], true);
    } finally {
      setIsSending(false);
    }
  };

  if (isLoadingMessages) {
    return (
      <div className="flex-1 flex flex-col h-full overflow-hidden">
        <TopBar
          title="Assistant"
          subtitle="Ask questions about your engineering files, extract metadata, and generate insights."
        />
        <div className="flex-1 flex items-center justify-center">
          <div className="flex gap-1 text-[#8B7F73]">
            <span className="animate-pulse">•</span>
            <span className="animate-pulse" style={{ animationDelay: '0.1s' }}>•</span>
            <span className="animate-pulse" style={{ animationDelay: '0.2s' }}>•</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">
      <TopBar
        title="Assistant"
        subtitle="Ask questions about your engineering files, extract metadata, and generate insights."
      />

      <div className="flex-1 overflow-auto flex flex-col">
        {messages.length === 0 ? (
          <div className="flex-1 flex items-center justify-center px-8">
            <div className="max-w-3xl w-full">
              <div className="text-center mb-12">
                <div className="inline-flex items-center justify-center w-14 h-14 bg-[#F2EDE3] rounded-xl mb-4">
                  <Sparkles className="w-7 h-7 text-[#2B2824]" strokeWidth={1.5} />
                </div>
                <h2 className="text-[#2B2824] mb-2">How can I help you today?</h2>
                <p className="text-[#8B7F73] text-sm">
                  I can analyze CAD files, extract metadata, and help you understand your engineering data.
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3">
                {suggestedPrompts.map((prompt) => (
                  <button
                    key={prompt.title}
                    onClick={() => handleSend(prompt.title)}
                    className="flex items-start gap-3 p-4 bg-white border border-[#E8E0D3] rounded-xl hover:bg-[#FFFCF7] transition-colors text-left"
                  >
                    <div className="mt-0.5">
                      <prompt.icon className="w-[18px] h-[18px] text-[#8B7F73]" strokeWidth={1.5} />
                    </div>
                    <div>
                      <h4 className="text-[#2B2824] text-[13px] mb-1">{prompt.title}</h4>
                      <p className="text-[#8B7F73] text-[12px] leading-relaxed">{prompt.description}</p>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="flex-1 px-8 py-6">
            <div className="max-w-3xl mx-auto space-y-6">
              {error && (
                <div className="bg-[#FFF5F5] border border-[#FEE2E2] text-[#B91C1C] px-4 py-3 rounded-lg text-sm">
                  {error}
                </div>
              )}
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={`flex gap-4 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  {message.role === 'assistant' && (
                    <div className="w-8 h-8 bg-[#F2EDE3] rounded-lg flex items-center justify-center flex-shrink-0">
                      <Sparkles className="w-4 h-4 text-[#2B2824]" strokeWidth={1.5} />
                    </div>
                  )}
                  <div
                    className={`max-w-[70%] px-4 py-3 rounded-xl ${
                      message.role === 'user'
                        ? 'bg-[#2B2824] text-white'
                        : 'bg-white border border-[#E8E0D3] text-[#2B2824]'
                    }`}
                  >
                    {message.isPending ? (
                      <div className="flex gap-1 text-sm text-[#8B7F73]">
                        <span className="animate-pulse">•</span>
                        <span className="animate-pulse" style={{ animationDelay: '0.1s' }}>•</span>
                        <span className="animate-pulse" style={{ animationDelay: '0.2s' }}>•</span>
                      </div>
                    ) : (
                      <ReactMarkdown className="prose prose-sm max-w-none text-[14px] leading-relaxed">
                        {message.content}
                      </ReactMarkdown>
                    )}
                    {message.sources && message.sources.length > 0 && (
                      <div className="flex flex-wrap gap-2 mt-3">
                        {message.sources.map((source) => (
                          <span
                            key={source.id}
                            className="px-2 py-1 text-[11px] border border-[#E8E0D3] rounded-full bg-[#F9FAFB] text-[#2B2824]"
                          >
                            {source.name}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                  {message.role === 'user' && (
                    <div className="w-8 h-8 bg-[#E8E0D3] rounded-lg flex items-center justify-center flex-shrink-0">
                      <span className="text-[#2B2824] text-sm font-medium">U</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="border-t border-[#E8E0D3] bg-white px-8 py-4">
          <div className="max-w-3xl mx-auto">
            <div className="flex items-end gap-3">
              <div className="flex-1 relative">
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSend();
                    }
                  }}
                  placeholder="Ask about your engineering files..."
                  rows={1}
                  className="w-full px-4 py-3 bg-white border border-[#E8E0D3] rounded-xl text-sm placeholder:text-[#8B7F73] focus:outline-none focus:border-[#2B2824] transition-colors resize-none"
                  style={{ minHeight: '44px', maxHeight: '120px' }}
                />
              </div>
              <button
                onClick={() => handleSend()}
                disabled={!input.trim() || isSending}
                className="w-11 h-11 flex items-center justify-center bg-[#2B2824] text-white rounded-xl hover:bg-[#3D3530] disabled:bg-[#E8E0D3] disabled:text-[#8B7F73] transition-colors flex-shrink-0"
              >
                <Send className="w-[18px] h-[18px]" strokeWidth={1.5} />
              </button>
            </div>
            <p className="text-[#8B7F73] text-[11px] mt-2 text-center">
              Press Enter to send, Shift + Enter for new line
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
