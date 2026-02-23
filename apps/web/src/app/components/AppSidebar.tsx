import { 
  Bot, 
  Vault, 
  PlayCircle, 
  Workflow, 
  History, 
  Library, 
  Settings, 
  HelpCircle,
  Search,
  ChevronDown,
  PanelLeftClose
} from 'lucide-react';
import { Link, useLocation } from 'react-router';

const navItems = [
  { icon: Bot, label: 'Assistant', path: '/assistant' },
  { icon: Vault, label: 'Vault', path: '/vault' },
  { icon: PlayCircle, label: 'Extraction Runs', path: '/extraction-runs' },
  { icon: Workflow, label: 'Workflows', path: '/workflows' },
  { icon: History, label: 'History', path: '/history' },
  { icon: Library, label: 'Knowledge Base', path: '/library' },
  { icon: Settings, label: 'Settings', path: '/settings' },
];

export function AppSidebar() {
  const location = useLocation();
  
  return (
    <div className="w-60 h-full bg-[#F4F4F4] border-r border-[#E6E6E6] flex flex-col">
      {/* Workspace Selector */}
      <div className="px-4 py-4 border-b border-[#E6E6E6]">
        <div className="flex items-center justify-between mb-3">
          <button className="flex items-center gap-2 hover:bg-white/50 px-2 py-1.5 rounded-lg transition-colors">
            <div className="w-6 h-6 bg-[#111111] rounded flex items-center justify-center">
              <span className="text-white text-xs font-semibold">O</span>
            </div>
            <span className="text-[#111111] text-sm font-medium">Orbit</span>
            <ChevronDown className="w-4 h-4 text-[#6B7280]" />
          </button>
        </div>
        <div className="flex items-center gap-1">
          <button className="w-7 h-7 flex items-center justify-center hover:bg-white/50 rounded transition-colors">
            <Search className="w-4 h-4 text-[#6B7280]" />
          </button>
          <button className="w-7 h-7 flex items-center justify-center hover:bg-white/50 rounded transition-colors">
            <PanelLeftClose className="w-4 h-4 text-[#6B7280]" />
          </button>
        </div>
      </div>

      {/* Navigation Items */}
      <nav className="flex-1 px-3 py-2">
        {navItems.map((item) => {
          const isActive = location.pathname === item.path || (location.pathname === '/' && item.path === '/assistant');
          
          return (
            <Link
              key={item.label}
              to={item.path}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
                isActive
                  ? 'bg-[#E6E6E6] text-[#111111]'
                  : 'text-[#6B7280] hover:bg-white/50 hover:text-[#111111]'
              }`}
            >
              <item.icon className="w-[18px] h-[18px]" />
              <span className="text-sm">{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Help Button */}
      <div className="px-3 py-3 border-t border-[#E6E6E6]">
        <button className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-[#6B7280] hover:bg-white/50 hover:text-[#111111] transition-colors">
          <HelpCircle className="w-[18px] h-[18px]" />
          <span className="text-sm">Help</span>
        </button>
      </div>
    </div>
  );
}