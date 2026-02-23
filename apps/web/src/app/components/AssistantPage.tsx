import { Send, Sparkles, FileText, Search, Code, Lightbulb } from 'lucide-react';
import { TopBar } from './TopBar';
import { useState } from 'react';

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
  role: 'user' | 'assistant';
  content: string;
}

export function AssistantPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');

  const handleSend = () => {
    if (input.trim()) {
      setMessages([...messages, { role: 'user', content: input }]);
      setInput('');
      
      // Simulate assistant response
      setTimeout(() => {
        setMessages(prev => [...prev, { 
          role: 'assistant', 
          content: 'I can help you analyze engineering files and extract structured metadata. What would you like to know?' 
        }]);
      }, 1000);
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">
      <TopBar 
        title="Assistant" 
        subtitle="Ask questions about your engineering files, extract metadata, and generate insights."
      />
      
      <div className="flex-1 overflow-auto flex flex-col">
        {messages.length === 0 ? (
          /* Empty State */
          <div className="flex-1 flex items-center justify-center px-8">
            <div className="max-w-3xl w-full">
              {/* Header */}
              <div className="text-center mb-12">
                <div className="inline-flex items-center justify-center w-14 h-14 bg-[#F4F4F4] rounded-xl mb-4">
                  <Sparkles className="w-7 h-7 text-[#111111]" strokeWidth={1.5} />
                </div>
                <h2 className="text-[#111111] mb-2">How can I help you today?</h2>
                <p className="text-[#6B7280] text-sm">
                  I can analyze CAD files, extract metadata, and help you understand your engineering data.
                </p>
              </div>

              {/* Suggested Prompts */}
              <div className="grid grid-cols-2 gap-3">
                {suggestedPrompts.map((prompt) => (
                  <button
                    key={prompt.title}
                    onClick={() => setInput(prompt.title)}
                    className="flex items-start gap-3 p-4 bg-white border border-[#E6E6E6] rounded-xl hover:bg-[#FAFAFA] transition-colors text-left"
                  >
                    <div className="mt-0.5">
                      <prompt.icon className="w-[18px] h-[18px] text-[#6B7280]" strokeWidth={1.5} />
                    </div>
                    <div>
                      <h4 className="text-[#111111] text-[13px] mb-1">{prompt.title}</h4>
                      <p className="text-[#6B7280] text-[12px] leading-relaxed">{prompt.description}</p>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          /* Conversation */
          <div className="flex-1 px-8 py-6">
            <div className="max-w-3xl mx-auto space-y-6">
              {messages.map((message, index) => (
                <div
                  key={index}
                  className={`flex gap-4 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  {message.role === 'assistant' && (
                    <div className="w-8 h-8 bg-[#F4F4F4] rounded-lg flex items-center justify-center flex-shrink-0">
                      <Sparkles className="w-4 h-4 text-[#111111]" strokeWidth={1.5} />
                    </div>
                  )}
                  <div
                    className={`max-w-[70%] px-4 py-3 rounded-xl ${
                      message.role === 'user'
                        ? 'bg-[#111111] text-white'
                        : 'bg-white border border-[#E6E6E6] text-[#111111]'
                    }`}
                  >
                    <p className="text-[14px] leading-relaxed">{message.content}</p>
                  </div>
                  {message.role === 'user' && (
                    <div className="w-8 h-8 bg-[#E6E6E6] rounded-lg flex items-center justify-center flex-shrink-0">
                      <span className="text-[#111111] text-sm font-medium">U</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Input Area */}
        <div className="border-t border-[#E6E6E6] bg-white px-8 py-4">
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
                  className="w-full px-4 py-3 bg-white border border-[#E6E6E6] rounded-xl text-sm placeholder:text-[#6B7280] focus:outline-none focus:border-[#111111] transition-colors resize-none"
                  style={{ minHeight: '44px', maxHeight: '120px' }}
                />
              </div>
              <button
                onClick={handleSend}
                disabled={!input.trim()}
                className="w-11 h-11 flex items-center justify-center bg-[#111111] text-white rounded-xl hover:bg-[#2A2A2A] disabled:bg-[#E6E6E6] disabled:text-[#6B7280] transition-colors flex-shrink-0"
              >
                <Send className="w-[18px] h-[18px]" strokeWidth={1.5} />
              </button>
            </div>
            <p className="text-[#6B7280] text-[11px] mt-2 text-center">
              Press Enter to send, Shift + Enter for new line
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
