import { Send, Sparkles, FileText, Search, Code, Lightbulb } from 'lucide-react';
import { TopBar } from './TopBar';
import { useState, useRef, useEffect, useCallback } from 'react';

const suggestedPrompts = [
  {
    icon: FileText,
    title: 'Summarize this project',
    description: 'Get a plain-English overview of all uploaded files',
    color: 'bg-blue-50 text-blue-600',
  },
  {
    icon: Search,
    title: 'Find similar parts',
    description: 'Search for components matching a specification',
    color: 'bg-violet-50 text-violet-600',
  },
  {
    icon: Code,
    title: 'Generate JSON profile',
    description: 'Create a canonical profile from engineering files',
    color: 'bg-emerald-50 text-emerald-600',
  },
  {
    icon: Lightbulb,
    title: 'Identify design patterns',
    description: 'Discover common elements across your projects',
    color: 'bg-amber-50 text-amber-600',
  },
];

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 px-1 py-0.5">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="w-1.5 h-1.5 bg-[#9CA3AF] rounded-full inline-block"
          style={{ animation: `bounce 1.2s ease-in-out ${i * 0.2}s infinite` }}
        />
      ))}
      <style>{`
        @keyframes bounce {
          0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
          30% { transform: translateY(-4px); opacity: 1; }
        }
      `}</style>
    </div>
  );
}

export function AssistantPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading, scrollToBottom]);

  const autoResize = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 120) + 'px';
  }, []);

  const handleSend = useCallback(() => {
    const text = input.trim();
    if (!text || loading) return;
    setMessages(prev => [...prev, { role: 'user', content: text }]);
    setInput('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
    setLoading(true);
    setTimeout(() => {
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content:
            'I can analyze your engineering files and extract structured metadata. Connect me to a project and I\'ll help you understand dimensions, materials, schemas, and design intent across your CAD library.',
        },
      ]);
      setLoading(false);
    }, 1200);
  }, [input, loading]);

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">
      <TopBar
        title="Assistant"
        subtitle="Ask questions about your engineering files, extract metadata, and generate insights."
      />

      <div className="flex-1 overflow-auto flex flex-col min-h-0">
        {messages.length === 0 ? (
          /* Empty State */
          <div className="flex-1 flex items-center justify-center px-8">
            <div className="max-w-2xl w-full">
              <div className="text-center mb-10">
                <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl mb-5 relative">
                  <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-[#EBEBEB] to-[#E0E0E0] shadow-sm" />
                  <div className="absolute inset-0.5 rounded-[14px] bg-gradient-to-br from-white to-[#F4F4F4]" />
                  <Sparkles className="w-7 h-7 text-[#111111] relative z-10" strokeWidth={1.5} />
                </div>
                <h2 className="text-[#111111] text-[20px] font-semibold mb-2">How can I help?</h2>
                <p className="text-[#9CA3AF] text-[13px] leading-relaxed max-w-sm mx-auto">
                  Analyze CAD files, extract metadata, and surface insights from your engineering data.
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3">
                {suggestedPrompts.map((prompt) => (
                  <button
                    key={prompt.title}
                    onClick={() => {
                      setInput(prompt.title);
                      textareaRef.current?.focus();
                    }}
                    className="flex items-start gap-3.5 p-4 bg-white border border-[#E6E6E6] rounded-xl hover:border-[#C4C4C4] hover:shadow-sm transition-all text-left group"
                  >
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5 ${prompt.color}`}>
                      <prompt.icon className="w-4 h-4" strokeWidth={1.5} />
                    </div>
                    <div>
                      <h4 className="text-[#111111] text-[13px] font-medium mb-0.5 group-hover:text-[#111111]">{prompt.title}</h4>
                      <p className="text-[#9CA3AF] text-[11px] leading-relaxed">{prompt.description}</p>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          /* Conversation */
          <div className="flex-1 px-8 py-6 overflow-auto">
            <div className="max-w-2xl mx-auto space-y-5">
              {messages.map((message, index) => (
                <div
                  key={index}
                  className={`flex gap-3 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  {message.role === 'assistant' && (
                    <div className="w-7 h-7 bg-[#111111] rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
                      <Sparkles className="w-3.5 h-3.5 text-white" strokeWidth={1.5} />
                    </div>
                  )}
                  <div
                    className={`max-w-[78%] px-4 py-3 rounded-2xl text-[13px] leading-relaxed ${
                      message.role === 'user'
                        ? 'bg-[#111111] text-white rounded-br-sm'
                        : 'bg-white border border-[#E6E6E6] text-[#111111] rounded-bl-sm shadow-sm'
                    }`}
                  >
                    {message.content}
                  </div>
                  {message.role === 'user' && (
                    <div className="w-7 h-7 bg-[#F4F4F4] border border-[#E6E6E6] rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
                      <span className="text-[#6B7280] text-[11px] font-semibold">U</span>
                    </div>
                  )}
                </div>
              ))}

              {loading && (
                <div className="flex gap-3 justify-start">
                  <div className="w-7 h-7 bg-[#111111] rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
                    <Sparkles className="w-3.5 h-3.5 text-white" strokeWidth={1.5} />
                  </div>
                  <div className="bg-white border border-[#E6E6E6] rounded-2xl rounded-bl-sm shadow-sm px-4 py-3.5">
                    <TypingIndicator />
                  </div>
                </div>
              )}

              <div ref={bottomRef} />
            </div>
          </div>
        )}

        {/* Input Area */}
        <div className="border-t border-[#E6E6E6] bg-white px-8 py-4 flex-shrink-0">
          <div className="max-w-2xl mx-auto">
            <div className="flex items-end gap-2.5 bg-white border border-[#E6E6E6] rounded-xl px-4 py-3 focus-within:border-[#C4C4C4] focus-within:shadow-sm transition-all">
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => { setInput(e.target.value); autoResize(); }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                placeholder="Ask about your engineering files…"
                rows={1}
                className="flex-1 bg-transparent text-[13px] text-[#111111] placeholder:text-[#9CA3AF] focus:outline-none resize-none leading-relaxed"
                style={{ minHeight: '20px', maxHeight: '120px' }}
              />
              <button
                onClick={handleSend}
                disabled={!input.trim() || loading}
                className="w-8 h-8 flex items-center justify-center bg-[#111111] text-white rounded-lg hover:bg-[#2A2A2A] disabled:bg-[#F4F4F4] disabled:text-[#C4C4C4] transition-all flex-shrink-0"
              >
                <Send className="w-3.5 h-3.5" strokeWidth={1.5} />
              </button>
            </div>
            <p className="text-[#C4C4C4] text-[10px] mt-1.5 text-center">
              Enter to send · Shift+Enter for new line
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
