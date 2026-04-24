import { useState } from "react";
import { useClerk } from "@clerk/clerk-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useApiClient } from "../../api/client";
import type { Project, BomResearchRun, ChatSessionSummary } from "../../api/types";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "./ui/dialog";
import {
  Bot,
  PlayCircle,
  Workflow,
  History,
  Library,
  Settings,
  Search,
  ChevronDown,
  ChevronLeft,
  User,
  LogOut,
  Clock,
  Star,
  FolderOpen,
  Plus,
  Filter,
  Archive,
  FileText,
  BarChart2,
  CheckCircle,
  Database,
  BookOpen,
  Layers,
  Zap,
  Wrench,
  Loader2,
  MessageSquare,
} from "lucide-react";
import { useLocation, useNavigate } from "react-router";

const softSpringEasing = "cubic-bezier(0.25, 1.1, 0.4, 1)";

const pathToSection: Record<string, string> = {
  "/": "assistant",
  "/assistant": "assistant",
  "/vault": "vault",
  "/extraction-runs": "extraction-runs",
  "/bom": "bom",
  "/workflows": "workflows",
  "/history": "history",
  "/library": "library",
  "/settings": "settings",
};

function OrbitLogo() {
  return (
    <div
      className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0 rotate-[-3deg]"
      style={{ background: '#2B2824', boxShadow: '0 2px 6px rgba(74, 58, 38, 0.18)' }}
    >
      <span
        className="font-display text-[17px] text-[#FAF7F2] leading-none"
        style={{ fontVariationSettings: "'opsz' 72" }}
      >
        O
      </span>
    </div>
  );
}

function SearchContainer({
  isCollapsed = false,
  value,
  onChange,
}: {
  isCollapsed?: boolean;
  value?: string;
  onChange?: (v: string) => void;
}) {
  const [internalValue, setInternalValue] = useState("");
  const searchValue = value !== undefined ? value : internalValue;
  const handleChange = (v: string) => {
    if (onChange) onChange(v);
    else setInternalValue(v);
  };

  return (
    <div
      className={`relative shrink-0 transition-all duration-500 ${
        isCollapsed ? "w-full flex justify-center" : "w-full"
      }`}
      style={{ transitionTimingFunction: softSpringEasing }}
    >
      <div
        className={`bg-[#EEE6D8] h-10 relative rounded-lg flex items-center transition-all duration-500 ${
          isCollapsed ? "w-10 min-w-10 justify-center" : "w-full"
        }`}
        style={{ transitionTimingFunction: softSpringEasing }}
      >
        <div
          className={`flex items-center justify-center shrink-0 transition-all duration-500 ${
            isCollapsed ? "p-1" : "px-1"
          }`}
          style={{ transitionTimingFunction: softSpringEasing }}
        >
          <div className="size-8 flex items-center justify-center">
            <Search size={16} className="text-[#8B7F73]" />
          </div>
        </div>
        <div
          className={`flex-1 min-h-px min-w-px relative transition-opacity duration-500 overflow-hidden ${
            isCollapsed ? "opacity-0 w-0" : "opacity-100"
          }`}
          style={{ transitionTimingFunction: softSpringEasing }}
        >
          <div className="flex flex-col justify-center relative size-full">
            <div className="flex flex-col gap-2 items-start justify-center pl-0 pr-2 py-1 relative w-full">
              <input
                type="text"
                placeholder="Search..."
                value={searchValue}
                onChange={(e) => handleChange(e.target.value)}
                className="w-full bg-transparent border-none outline-none text-sm text-[#2B2824] placeholder:text-[#A89D91] leading-5"
                tabIndex={isCollapsed ? -1 : 0}
              />
            </div>
          </div>
        </div>
        <div
          aria-hidden="true"
          className="absolute border border-[#E8E0D3] border-solid inset-0 pointer-events-none rounded-lg"
        />
      </div>
    </div>
  );
}

interface SubItem {
  label: string;
  path?: string;
}

interface MenuItem {
  icon: React.ReactNode;
  label: string;
  path?: string;
  onClick?: () => void;
  hasDropdown?: boolean;
  isActive?: boolean;
  children?: SubItem[];
}

interface MenuSection {
  title: string;
  items: MenuItem[];
}

interface SidebarContent {
  title: string;
  sections: MenuSection[];
}

function MenuItemRow({
  item,
  isExpanded,
  onToggle,
  onItemClick,
  isCollapsed,
}: {
  item: MenuItem;
  isExpanded?: boolean;
  onToggle?: () => void;
  onItemClick?: () => void;
  isCollapsed?: boolean;
}) {
  const handleClick = () => {
    if (item.hasDropdown && onToggle) {
      onToggle();
    } else if (onItemClick) {
      onItemClick();
    }
  };

  return (
    <div
      className={`relative shrink-0 transition-all duration-500 ${
        isCollapsed ? "w-full flex justify-center" : "w-full"
      }`}
      style={{ transitionTimingFunction: softSpringEasing }}
    >
      <div
        className={`select-none rounded-lg cursor-pointer transition-all duration-500 flex items-center relative my-0.5 ${
          item.isActive ? "bg-[#E8E0D3]" : "hover:bg-[#E8E0D3]"
        } ${
          isCollapsed
            ? "w-10 min-w-10 h-10 justify-center p-4"
            : "w-full h-10 px-4 py-2"
        }`}
        style={{ transitionTimingFunction: softSpringEasing }}
        onClick={handleClick}
        title={isCollapsed ? item.label : undefined}
      >
        <div className="flex items-center justify-center shrink-0">
          {item.icon}
        </div>
        <div
          className={`flex-1 min-h-px min-w-px relative transition-opacity duration-500 overflow-hidden ${
            isCollapsed ? "opacity-0 w-0" : "opacity-100 ml-3"
          }`}
          style={{ transitionTimingFunction: softSpringEasing }}
        >
          <div className="text-sm text-[#2B2824] truncate">{item.label}</div>
        </div>
        {item.hasDropdown && (
          <div
            className={`flex items-center justify-center shrink-0 transition-opacity duration-500 ${
              isCollapsed ? "opacity-0 w-0" : "opacity-100 ml-2"
            }`}
            style={{ transitionTimingFunction: softSpringEasing }}
          >
            <ChevronDown
              size={16}
              className="text-[#8B7F73] transition-transform duration-500"
              style={{
                transitionTimingFunction: softSpringEasing,
                transform: isExpanded ? "rotate(180deg)" : "rotate(0deg)",
              }}
            />
          </div>
        )}
      </div>
    </div>
  );
}

function SubMenuItemRow({
  item,
  onItemClick,
}: {
  item: SubItem;
  onItemClick?: () => void;
}) {
  return (
    <div className="select-none w-full pl-9 pr-1 py-[1px]">
      <div
        className="h-10 w-full rounded-lg cursor-pointer transition-colors hover:bg-[#E8E0D3] flex items-center px-3 py-1"
        onClick={onItemClick}
      >
        <div className="flex-1 min-w-0">
          <div className="text-sm text-[#8B7F73] truncate">{item.label}</div>
        </div>
      </div>
    </div>
  );
}

function MenuSectionRow({
  section,
  expandedItems,
  onToggleExpanded,
  isCollapsed,
  onNavigate,
}: {
  section: MenuSection;
  expandedItems: Set<string>;
  onToggleExpanded: (key: string) => void;
  isCollapsed?: boolean;
  onNavigate: (path: string) => void;
}) {
  return (
    <div className="flex flex-col items-start justify-stretch p-0 relative shrink-0 w-full">
      <div
        className={`relative shrink-0 w-full transition-all duration-500 overflow-hidden ${
          isCollapsed ? "h-0 opacity-0" : "h-10 opacity-100"
        }`}
        style={{ transitionTimingFunction: softSpringEasing }}
      >
        <div className="flex flex-col justify-center h-full">
          <div className="flex flex-col h-10 items-start justify-center px-4 relative w-full">
            <div className="text-xs text-[#A89D91] whitespace-nowrap uppercase tracking-wide">
              {section.title}
            </div>
          </div>
        </div>
      </div>
      {section.items.map((item, index) => {
        const itemKey = `${section.title}-${index}`;
        const isExpanded = expandedItems.has(itemKey);
        return (
          <div key={itemKey} className="w-full flex flex-col">
            <MenuItemRow
              item={item}
              isExpanded={isExpanded}
              onToggle={() => onToggleExpanded(itemKey)}
              onItemClick={() => {
                if (item.onClick) item.onClick();
                else if (item.path) onNavigate(item.path);
              }}
              isCollapsed={isCollapsed}
            />
            {isExpanded && item.children && !isCollapsed && (
              <div className="flex flex-col gap-1 mb-2">
                {item.children.length === 0 ? (
                  <div className="select-none w-full pl-9 pr-1 py-[1px]">
                    <div className="h-10 w-full flex items-center px-3 py-1">
                      <div className="text-sm text-[#C4B8A8] italic">No items yet</div>
                    </div>
                  </div>
                ) : (
                  item.children.map((child, childIndex) => (
                    <SubMenuItemRow
                      key={`${itemKey}-${childIndex}`}
                      item={child}
                      onItemClick={() =>
                        child.path && onNavigate(child.path)
                      }
                    />
                  ))
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function getSidebarContent(
  activeSection: string,
  projects?: Project[],
  handlers?: { onNewProject?: () => void; onNewConversation?: () => void },
  bomRuns?: BomResearchRun[],
  chatSessions?: ChatSessionSummary[],
  searchQuery?: string,
): SidebarContent {
  const ic = "text-[#8B7F73]";

  const contentMap: Record<string, SidebarContent> = {
    assistant: (() => {
      const today = new Date().toDateString();
      const query = (searchQuery ?? "").toLowerCase();
      const filtered = (chatSessions ?? []).filter(
        (s) => !query || s.title.toLowerCase().includes(query)
      );
      const todaySessions = filtered.filter(
        (s) => new Date(s.created_at).toDateString() === today
      );
      const starredSessions = filtered.filter((s) => s.is_starred);
      const toSubItem = (s: ChatSessionSummary): SubItem => ({
        label: s.title,
        path: `/assistant?session=${s.session_id}`,
      });

      const allSection = filtered.length > 0
        ? {
            title: "All Conversations",
            items: filtered.map((s) => ({
              icon: <MessageSquare size={16} className={ic} />,
              label: s.title,
              path: `/assistant?session=${s.session_id}`,
            })),
          }
        : null;

      return {
        title: "Assistant",
        sections: [
          {
            title: "Start",
            items: [
              {
                icon: <Plus size={16} className={ic} />,
                label: "New conversation",
                onClick: handlers?.onNewConversation,
              },
            ],
          },
          {
            title: "Recent",
            items: [
              {
                icon: <Clock size={16} className={ic} />,
                label: "Today's chats",
                hasDropdown: true,
                children: todaySessions.map(toSubItem),
              },
              {
                icon: <Star size={16} className={ic} />,
                label: "Starred conversations",
                hasDropdown: true,
                children: starredSessions.map(toSubItem),
              },
            ],
          },
          ...(allSection ? [allSection] : []),
        ],
      };
    })(),
    vault: {
      title: "Projects",
      sections: [
        {
          title: "Quick Actions",
          items: [
            {
              icon: <Plus size={16} className={ic} />,
              label: "New project",
              onClick: handlers?.onNewProject,
            },
          ],
        },
        {
          title: "Projects",
          items: [
            {
              icon: <FolderOpen size={16} className={ic} />,
              label: "Active projects",
              hasDropdown: true,
              children: projects?.map((p) => ({
                label: p.name,
                path: `/project/${p.id}`,
              })) ?? [],
            },
          ],
        },
      ],
    },
    "extraction-runs": {
      title: "Extraction Runs",
      sections: [
        {
          title: "Quick Actions",
          items: [
            {
              icon: <PlayCircle size={16} className={ic} />,
              label: "New run",
              path: "/extraction-runs",
            },
          ],
        },
        {
          title: "Status",
          items: [
            {
              icon: <Zap size={16} className={ic} />,
              label: "Active runs",
              path: "/extraction-runs?status=active",
            },
            {
              icon: <CheckCircle size={16} className={ic} />,
              label: "Completed",
              path: "/extraction-runs?status=extracted",
            },
            {
              icon: <Archive size={16} className={ic} />,
              label: "Failed",
              path: "/extraction-runs?status=failed",
            },
          ],
        },
      ],
    },
    bom: (() => {
      const projectName = (id: number) =>
        projects?.find((p) => p.id === id)?.name ?? `Project #${id}`;
      const isActive = (s: BomResearchRun["status"]) =>
        s === "researching" || s === "generating_report" || s === "awaiting_team_input" || s === "gathering_inputs";
      const statusIcon = (s: BomResearchRun["status"]): React.ReactNode => {
        if (s === "researching" || s === "generating_report") {
          return <Loader2 size={16} className="text-blue-500 animate-spin" />;
        }
        if (s === "awaiting_team_input") return <Clock size={16} className="text-amber-500" />;
        if (s === "gathering_inputs") return <Clock size={16} className={ic} />;
        if (s === "completed") return <CheckCircle size={16} className="text-emerald-600" />;
        if (s === "failed") return <Archive size={16} className="text-red-500" />;
        return <Clock size={16} className={ic} />;
      };
      const sorted = (bomRuns ?? [])
        .slice()
        .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
      const active = sorted.filter((r) => isActive(r.status));
      const recent = sorted.filter((r) => r.status === "completed").slice(0, 5);

      return {
        title: "BOM Agent",
        sections: [
          {
            title: "Quick Actions",
            items: [
              {
                icon: <Plus size={16} className={ic} />,
                label: "New BOM Run",
                path: "/vault",
              },
              {
                icon: <Wrench size={16} className={ic} />,
                label: "All runs",
                path: "/bom",
              },
            ],
          },
          {
            title: `Active${active.length ? ` (${active.length})` : ""}`,
            items: active.length === 0
              ? [{ icon: <Clock size={16} className={ic} />, label: "No active runs" }]
              : active.map((r) => ({
                  icon: statusIcon(r.status),
                  label: `Run #${r.id} — ${projectName(r.project)}`,
                  path: `/bom/${r.id}`,
                })),
          },
          {
            title: "Recent",
            items: recent.length === 0
              ? [{ icon: <CheckCircle size={16} className={ic} />, label: "No completed runs yet" }]
              : recent.map((r) => ({
                  icon: statusIcon(r.status),
                  label: `Run #${r.id} — ${projectName(r.project)}`,
                  path: `/bom/${r.id}`,
                })),
          },
        ],
      };
    })(),
    workflows: {
      title: "Workflows",
      sections: [
        {
          title: "Quick Actions",
          items: [
            {
              icon: <Plus size={16} className={ic} />,
              label: "New workflow",
              path: "/workflows",
            },
          ],
        },
        {
          title: "My Workflows",
          items: [
            {
              icon: <Workflow size={16} className={ic} />,
              label: "Active",
            },
            {
              icon: <Layers size={16} className={ic} />,
              label: "Templates",
            },
          ],
        },
      ],
    },
    history: {
      title: "History",
      sections: [
        {
          title: "Sessions",
          items: [
            {
              icon: <Clock size={16} className={ic} />,
              label: "Today",
            },
            {
              icon: <BarChart2 size={16} className={ic} />,
              label: "Last 7 days",
            },
            {
              icon: <Archive size={16} className={ic} />,
              label: "Older",
            },
          ],
        },
      ],
    },
    library: {
      title: "Knowledge Base",
      sections: [
        {
          title: "Quick Actions",
          items: [
            {
              icon: <Plus size={16} className={ic} />,
              label: "Add document",
              path: "/library?upload=1",
            },
            {
              icon: <Filter size={16} className={ic} />,
              label: "Filter",
              path: "/library?filter=1",
            },
          ],
        },
        {
          title: "Documents",
          items: [
            {
              icon: <FileText size={16} className={ic} />,
              label: "Recent documents",
              path: "/library?view=recent",
            },
            {
              icon: <Database size={16} className={ic} />,
              label: "All documents",
              path: "/library?view=all",
            },
          ],
        },
      ],
    },
    settings: {
      title: "Settings",
      sections: [
        {
          title: "Account",
          items: [
            {
              icon: <User size={16} className={ic} />,
              label: "Profile",
            },
            {
              icon: <Settings size={16} className={ic} />,
              label: "Preferences",
            },
          ],
        },
        {
          title: "Workspace",
          items: [
            {
              icon: <Database size={16} className={ic} />,
              label: "Integrations",
            },
            {
              icon: <BookOpen size={16} className={ic} />,
              label: "API & Keys",
            },
          ],
        },
      ],
    },
  };

  return contentMap[activeSection] || contentMap.assistant;
}

function IconNavButton({
  children,
  isActive = false,
  onClick,
  title,
}: {
  children: React.ReactNode;
  isActive?: boolean;
  onClick?: () => void;
  title?: string;
}) {
  return (
    <div
      className={`flex flex-row items-center justify-center rounded-lg shrink-0 size-10 min-w-10 cursor-pointer transition-colors duration-500 ${
        isActive
          ? "bg-[#E8E0D3] text-[#2B2824]"
          : "hover:bg-[#E8E0D3] text-[#8B7F73] hover:text-[#2B2824]"
      }`}
      style={{ transitionTimingFunction: softSpringEasing }}
      onClick={onClick}
      title={title}
    >
      {children}
    </div>
  );
}

const iconNavItems = [
  { id: "assistant", icon: <Bot size={16} />, label: "Assistant", path: "/assistant" },
  { id: "vault", icon: <FolderOpen size={16} />, label: "Projects", path: "/vault" },
  { id: "extraction-runs", icon: <PlayCircle size={16} />, label: "Extraction Runs", path: "/extraction-runs" },
  { id: "bom", icon: <Wrench size={16} />, label: "BOM Agent", path: "/bom" },
  { id: "workflows", icon: <Workflow size={16} />, label: "Workflows", path: "/workflows" },
  { id: "history", icon: <History size={16} />, label: "History", path: "/history" },
  { id: "library", icon: <Library size={16} />, label: "Knowledge Base", path: "/library" },
];

function IconNavigation({ activeSection }: { activeSection: string }) {
  const navigate = useNavigate();
  const { signOut } = useClerk();
  const [showSignOut, setShowSignOut] = useState(false);

  const handleSignOut = async () => {
    setShowSignOut(false);
    await signOut();
    navigate('/signin');
  };

  return (
    <div className="bg-[#F2EDE3] flex flex-col gap-2 h-full items-center justify-start overflow-visible p-3 relative shrink-0 w-16 border-r border-[#E8E0D3] z-50">
      {/* Logo */}
      <div className="mb-2 size-10 flex items-center justify-center">
        <OrbitLogo />
      </div>

      {/* Navigation Icons */}
      <div className="flex flex-col gap-2 w-full items-center">
        {iconNavItems.map((item) => (
          <IconNavButton
            key={item.id}
            isActive={activeSection === item.id}
            onClick={() => navigate(item.path)}
            title={item.label}
          >
            {item.icon}
          </IconNavButton>
        ))}
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Bottom: Settings + Avatar */}
      <div className="flex flex-col gap-2 w-full items-center">
        <IconNavButton
          isActive={activeSection === "settings"}
          onClick={() => navigate("/settings")}
          title="Settings"
        >
          <Settings size={16} />
        </IconNavButton>

        {/* Avatar with sign-out popover */}
        <div className="relative">
          {showSignOut && (
            <>
              {/* Backdrop to close on outside click */}
              <div
                className="fixed inset-0 z-10"
                onClick={() => setShowSignOut(false)}
              />
              {/* Popover */}
              <div className="absolute bottom-0 left-full ml-2 z-20 bg-white border border-[#E8E0D3] rounded-lg shadow-[0_4px_16px_rgba(0,0,0,0.10)] overflow-hidden w-36">
                <button
                  onClick={handleSignOut}
                  className="w-full flex items-center gap-2.5 px-3 py-2.5 text-sm text-[#2B2824] hover:bg-[#FAF7F2] transition-colors duration-100"
                >
                  <LogOut size={14} className="text-[#8B7F73] shrink-0" />
                  Sign out
                </button>
              </div>
            </>
          )}
          <button
            onClick={() => setShowSignOut((v) => !v)}
            title="Account"
            className={`size-8 rounded-full flex items-center justify-center border transition-all duration-150 ${
              showSignOut
                ? 'bg-[#2B2824] border-[#2B2824]'
                : 'bg-[#E8E0D3] border-[#D1D1D1] hover:bg-[#D9D9D9] hover:border-[#BEBEBE]'
            }`}
          >
            <User size={14} className={showSignOut ? 'text-white' : 'text-[#8B7F73]'} />
          </button>
        </div>
      </div>
    </div>
  );
}

function SectionTitle({
  title,
  onToggleCollapse,
  isCollapsed,
}: {
  title: string;
  onToggleCollapse: () => void;
  isCollapsed: boolean;
}) {
  if (isCollapsed) {
    return (
      <div
        className="relative shrink-0 w-full flex justify-center transition-all duration-500"
        style={{ transitionTimingFunction: softSpringEasing }}
      >
        <button
          onClick={onToggleCollapse}
          className="flex flex-row items-center justify-center rounded-lg cursor-pointer transition-all duration-500 hover:bg-[#E8E0D3] text-[#8B7F73] hover:text-[#2B2824] size-10 min-w-10"
          style={{ transitionTimingFunction: softSpringEasing }}
        >
          <ChevronLeft
            size={16}
            className="transition-transform duration-500"
            style={{
              transitionTimingFunction: softSpringEasing,
              transform: "rotate(180deg)",
            }}
          />
        </button>
      </div>
    );
  }

  return (
    <div
      className="relative shrink-0 w-full overflow-hidden transition-all duration-500"
      style={{ transitionTimingFunction: softSpringEasing }}
    >
      <div className="flex flex-row items-center justify-between h-11">
        <div className="flex flex-col items-start px-2">
          <div className="font-display text-[19px] text-[#2B2824] whitespace-nowrap leading-[1.1] tracking-tight font-medium">
            {title}
          </div>
          <svg aria-hidden="true" viewBox="0 0 160 10" className="h-[7px] w-[70px] mt-0.5 -rotate-[1deg] block" fill="none" preserveAspectRatio="none">
            <path d="M2 5 Q 20 1, 38 5 T 76 4 Q 100 8, 124 3 T 158 5" stroke="#C66A4E" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </div>
        <div className="flex items-center justify-center pr-1">
          <button
            onClick={onToggleCollapse}
            className="flex flex-row items-center justify-center rounded-lg cursor-pointer transition-all duration-500 hover:bg-[#E8E0D3] text-[#8B7F73] hover:text-[#2B2824] size-10 min-w-10"
            style={{ transitionTimingFunction: softSpringEasing }}
          >
            <ChevronLeft
              size={16}
              className="transition-transform duration-500"
              style={{ transitionTimingFunction: softSpringEasing }}
            />
          </button>
        </div>
      </div>
    </div>
  );
}

function DetailSidebar({ activeSection }: { activeSection: string }) {
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set());
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const navigate = useNavigate();
  const apiFetch = useApiClient();
  const queryClient = useQueryClient();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [projectName, setProjectName] = useState("");
  const [projectDesc, setProjectDesc] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [createError, setCreateError] = useState("");

  const { data: projects } = useQuery<Project[]>({
    queryKey: ["projects"],
    queryFn: async () => {
      const res = await apiFetch("/api/projects/");
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      return res.json();
    },
    enabled: activeSection === "vault" || activeSection === "bom",
  });

  const { data: bomRuns } = useQuery<BomResearchRun[]>({
    queryKey: ["bom-runs", "all"],
    queryFn: async () => {
      const res = await apiFetch("/api/bom/runs/");
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      return res.json();
    },
    enabled: activeSection === "bom",
    refetchInterval: (query) => {
      const data = query.state.data as BomResearchRun[] | undefined;
      const anyActive = data?.some(
        (r) => r.status === "researching" || r.status === "generating_report" || r.status === "awaiting_team_input",
      );
      return anyActive ? 10_000 : false;
    },
  });

  const { data: chatSessions } = useQuery<ChatSessionSummary[]>({
    queryKey: ["chat-sessions"],
    queryFn: async () => {
      const res = await apiFetch("/api/assistant/sessions/");
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      return res.json();
    },
    enabled: activeSection === "assistant",
    refetchOnWindowFocus: true,
  });

  const handleCreateProject = async () => {
    if (!projectName.trim()) return;
    setSubmitting(true);
    setCreateError("");
    try {
      const res = await apiFetch("/api/projects/", {
        method: "POST",
        body: JSON.stringify({
          name: projectName.trim(),
          description: projectDesc.trim(),
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.name?.[0] ?? `Error ${res.status}`);
      }
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
      setDialogOpen(false);
      setProjectName("");
      setProjectDesc("");
    } catch (err) {
      setCreateError(
        err instanceof Error ? err.message : "Failed to create project"
      );
    } finally {
      setSubmitting(false);
    }
  };

  const content = getSidebarContent(
    activeSection,
    projects,
    {
      onNewProject: () => setDialogOpen(true),
      onNewConversation: () => navigate(`/assistant?t=${Date.now()}`),
    },
    bomRuns,
    chatSessions,
    searchQuery,
  );

  const toggleExpanded = (key: string) => {
    const next = new Set(expandedItems);
    if (next.has(key)) {
      next.delete(key);
    } else {
      next.add(key);
    }
    setExpandedItems(next);
  };

  return (
    <div
      className={`bg-[#FFFCF7] flex flex-col gap-4 h-full items-start justify-start overflow-visible relative shrink-0 transition-all duration-500 border-r border-[#E8E0D3] ${
        isCollapsed ? "w-16 min-w-16 px-3" : "w-72 p-4"
      }`}
      style={{ transitionTimingFunction: softSpringEasing }}
    >
      <SectionTitle
        title={content.title}
        onToggleCollapse={() => setIsCollapsed(!isCollapsed)}
        isCollapsed={isCollapsed}
      />
      <SearchContainer
        isCollapsed={isCollapsed}
        value={searchQuery}
        onChange={setSearchQuery}
      />

      <div
        className={`flex flex-col grow min-h-px min-w-10 p-0 relative shrink-0 w-full overflow-y-auto transition-all duration-500 ${
          isCollapsed
            ? "gap-2 items-center justify-start"
            : "gap-4 items-start justify-start"
        }`}
        style={{ transitionTimingFunction: softSpringEasing }}
      >
        {content.sections.map((section, index) => (
          <MenuSectionRow
            key={`${activeSection}-${index}`}
            section={section}
            expandedItems={expandedItems}
            onToggleExpanded={toggleExpanded}
            isCollapsed={isCollapsed}
            onNavigate={(path) => navigate(path)}
          />
        ))}
      </div>

      <Dialog
        open={dialogOpen}
        onOpenChange={(open) => {
          setDialogOpen(open);
          if (!open) {
            setProjectName("");
            setProjectDesc("");
            setCreateError("");
          }
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Create project</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            {createError && (
              <p className="text-sm text-[#DC2626] bg-[#FEF2F2] border border-[#FECACA] rounded-lg px-3 py-2">
                {createError}
              </p>
            )}
            <div className="space-y-1.5">
              <label className="text-[#4A4038] text-xs font-medium">Project name</label>
              <input
                type="text"
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleCreateProject()}
                placeholder="e.g. Gearbox Assembly Rev B"
                autoFocus
                className="w-full px-3 py-2.5 bg-white border border-[#E8E0D3] rounded-lg text-sm text-[#2B2824] placeholder:text-[#A89D91] focus:outline-none focus:border-[#2B2824] focus:ring-1 focus:ring-[#2B2824] transition-all"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-[#4A4038] text-xs font-medium">Description <span className="text-[#A89D91] font-normal">(optional)</span></label>
              <textarea
                value={projectDesc}
                onChange={(e) => setProjectDesc(e.target.value)}
                placeholder="What is this project about?"
                rows={3}
                className="w-full px-3 py-2.5 bg-white border border-[#E8E0D3] rounded-lg text-sm text-[#2B2824] placeholder:text-[#A89D91] focus:outline-none focus:border-[#2B2824] focus:ring-1 focus:ring-[#2B2824] transition-all resize-none"
              />
            </div>
          </div>
          <DialogFooter>
            <button
              onClick={() => setDialogOpen(false)}
              className="px-4 py-2 text-sm text-[#8B7F73] hover:text-[#2B2824] transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleCreateProject}
              disabled={!projectName.trim() || submitting}
              className="px-4 py-2 bg-[#2B2824] text-white text-sm font-medium rounded-lg hover:bg-[#3D3530] disabled:opacity-50 transition-colors"
            >
              {submitting ? "Creating..." : "Create"}
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export function AppSidebar() {
  const location = useLocation();

  const currentSection =
    pathToSection[location.pathname] ||
    (location.pathname.startsWith("/project/") ? "vault"
      : location.pathname.startsWith("/bom/") ? "bom"
      : "assistant");

  return (
    <div className="flex flex-row h-full">
      <IconNavigation activeSection={currentSection} />
      <DetailSidebar key={currentSection} activeSection={currentSection} />
    </div>
  );
}