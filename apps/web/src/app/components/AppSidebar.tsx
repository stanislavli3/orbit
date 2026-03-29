import { useState } from "react";
import { useClerk } from "@clerk/clerk-react";
import {
  Bot,
  Vault,
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
} from "lucide-react";
import { useLocation, useNavigate } from "react-router";

const softSpringEasing = "cubic-bezier(0.25, 1.1, 0.4, 1)";

const pathToSection: Record<string, string> = {
  "/": "assistant",
  "/assistant": "assistant",
  "/vault": "vault",
  "/extraction-runs": "extraction-runs",
  "/workflows": "workflows",
  "/history": "history",
  "/library": "library",
  "/settings": "settings",
};

function OrbitLogo() {
  return (
    <div className="w-7 h-7 bg-[#111111] rounded-md flex items-center justify-center shrink-0">
      <span className="text-white text-xs font-bold">O</span>
    </div>
  );
}

function SearchContainer({ isCollapsed = false }: { isCollapsed?: boolean }) {
  const [searchValue, setSearchValue] = useState("");

  return (
    <div
      className={`relative shrink-0 transition-all duration-500 ${
        isCollapsed ? "w-full flex justify-center" : "w-full"
      }`}
      style={{ transitionTimingFunction: softSpringEasing }}
    >
      <div
        className={`bg-[#F0F0F0] h-10 relative rounded-lg flex items-center transition-all duration-500 ${
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
            <Search size={16} className="text-[#6B7280]" />
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
                onChange={(e) => setSearchValue(e.target.value)}
                className="w-full bg-transparent border-none outline-none text-sm text-[#111111] placeholder:text-[#9CA3AF] leading-5"
                tabIndex={isCollapsed ? -1 : 0}
              />
            </div>
          </div>
        </div>
        <div
          aria-hidden="true"
          className="absolute border border-[#E6E6E6] border-solid inset-0 pointer-events-none rounded-lg"
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
          item.isActive ? "bg-[#E6E6E6]" : "hover:bg-[#EBEBEB]"
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
          <div className="text-sm text-[#111111] truncate">{item.label}</div>
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
              className="text-[#6B7280] transition-transform duration-500"
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
        className="h-10 w-full rounded-lg cursor-pointer transition-colors hover:bg-[#EBEBEB] flex items-center px-3 py-1"
        onClick={onItemClick}
      >
        <div className="flex-1 min-w-0">
          <div className="text-sm text-[#6B7280] truncate">{item.label}</div>
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
            <div className="text-xs text-[#9CA3AF] whitespace-nowrap uppercase tracking-wide">
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
              onItemClick={() => item.path && onNavigate(item.path)}
              isCollapsed={isCollapsed}
            />
            {isExpanded && item.children && !isCollapsed && (
              <div className="flex flex-col gap-1 mb-2">
                {item.children.map((child, childIndex) => (
                  <SubMenuItemRow
                    key={`${itemKey}-${childIndex}`}
                    item={child}
                    onItemClick={() =>
                      child.path && onNavigate(child.path)
                    }
                  />
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function getSidebarContent(activeSection: string): SidebarContent {
  const ic = "text-[#6B7280]";

  const contentMap: Record<string, SidebarContent> = {
    assistant: {
      title: "Assistant",
      sections: [
        {
          title: "Start",
          items: [
            {
              icon: <Plus size={16} className={ic} />,
              label: "New conversation",
              path: "/assistant",
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
              children: [
                { label: "Contract analysis" },
                { label: "Data extraction" },
              ],
            },
            {
              icon: <Star size={16} className={ic} />,
              label: "Starred conversations",
            },
          ],
        },
      ],
    },
    vault: {
      title: "Vault",
      sections: [
        {
          title: "Quick Actions",
          items: [
            {
              icon: <Plus size={16} className={ic} />,
              label: "New project",
              path: "/vault",
            },
            {
              icon: <Filter size={16} className={ic} />,
              label: "Filter projects",
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
              children: [
                { label: "Contract review" },
                { label: "Financial analysis" },
              ],
            },
            {
              icon: <Archive size={16} className={ic} />,
              label: "Archived",
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
            },
            {
              icon: <CheckCircle size={16} className={ic} />,
              label: "Completed",
            },
            {
              icon: <Archive size={16} className={ic} />,
              label: "Archived",
            },
          ],
        },
      ],
    },
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
              hasDropdown: true,
              children: [
                { label: "Document processor" },
                { label: "Data extractor" },
              ],
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
              hasDropdown: true,
              children: [
                { label: "Contract analysis session" },
                { label: "Data extraction run" },
              ],
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
              path: "/library",
            },
            {
              icon: <Filter size={16} className={ic} />,
              label: "Filter",
            },
          ],
        },
        {
          title: "Documents",
          items: [
            {
              icon: <FileText size={16} className={ic} />,
              label: "Recent documents",
              hasDropdown: true,
              children: [
                { label: "Contracts" },
                { label: "Reports" },
                { label: "Templates" },
              ],
            },
            {
              icon: <Database size={16} className={ic} />,
              label: "All documents",
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
          ? "bg-[#E6E6E6] text-[#111111]"
          : "hover:bg-[#EBEBEB] text-[#6B7280] hover:text-[#111111]"
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
  { id: "vault", icon: <Vault size={16} />, label: "Vault", path: "/vault" },
  { id: "extraction-runs", icon: <PlayCircle size={16} />, label: "Extraction Runs", path: "/extraction-runs" },
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
    <div className="bg-[#F4F4F4] flex flex-col gap-2 h-full items-center justify-start overflow-visible p-3 relative shrink-0 w-16 border-r border-[#E6E6E6] z-50">
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
              <div className="absolute bottom-0 left-full ml-2 z-20 bg-white border border-[#E6E6E6] rounded-lg shadow-[0_4px_16px_rgba(0,0,0,0.10)] overflow-hidden w-36">
                <button
                  onClick={handleSignOut}
                  className="w-full flex items-center gap-2.5 px-3 py-2.5 text-sm text-[#111111] hover:bg-[#F7F7F7] transition-colors duration-100"
                >
                  <LogOut size={14} className="text-[#6B7280] shrink-0" />
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
                ? 'bg-[#111111] border-[#111111]'
                : 'bg-[#E6E6E6] border-[#D1D1D1] hover:bg-[#D9D9D9] hover:border-[#BEBEBE]'
            }`}
          >
            <User size={14} className={showSignOut ? 'text-white' : 'text-[#6B7280]'} />
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
          className="flex flex-row items-center justify-center rounded-lg cursor-pointer transition-all duration-500 hover:bg-[#EBEBEB] text-[#6B7280] hover:text-[#111111] size-10 min-w-10"
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
      <div className="flex flex-row items-center justify-between h-10">
        <div className="flex items-center px-2">
          <div className="font-semibold text-lg text-[#111111] whitespace-nowrap leading-7">
            {title}
          </div>
        </div>
        <div className="flex items-center justify-center pr-1">
          <button
            onClick={onToggleCollapse}
            className="flex flex-row items-center justify-center rounded-lg cursor-pointer transition-all duration-500 hover:bg-[#EBEBEB] text-[#6B7280] hover:text-[#111111] size-10 min-w-10"
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
  const navigate = useNavigate();
  const content = getSidebarContent(activeSection);

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
      className={`bg-white flex flex-col gap-4 h-full items-start justify-start overflow-visible relative shrink-0 transition-all duration-500 border-r border-[#E6E6E6] ${
        isCollapsed ? "w-16 min-w-16 px-3" : "w-72 p-4"
      }`}
      style={{ transitionTimingFunction: softSpringEasing }}
    >
      <SectionTitle
        title={content.title}
        onToggleCollapse={() => setIsCollapsed(!isCollapsed)}
        isCollapsed={isCollapsed}
      />
      <SearchContainer isCollapsed={isCollapsed} />

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
    </div>
  );
}

export function AppSidebar() {
  const location = useLocation();

  const currentSection =
    pathToSection[location.pathname] ||
    (location.pathname.startsWith("/project/") ? "vault" : "assistant");

  return (
    <div className="flex flex-row h-full">
      <IconNavigation activeSection={currentSection} />
      <DetailSidebar key={currentSection} activeSection={currentSection} />
    </div>
  );
}