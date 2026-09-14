
import { Link, useLocation } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { 
  LayoutDashboard, Map, Activity, Video, 
  MapPin, Navigation, AlertTriangle, Bus, 
  BarChart2, Wrench, Cpu, Settings, ChevronLeft, ChevronRight
} from 'lucide-react'
import { cn } from '@/lib/utils'

const navItems = [
  { name: 'Overview', href: '/', icon: LayoutDashboard },
  { name: 'Live Map', href: '/map', icon: Map },
  { name: 'Fleet Replay', href: '/fleet-replay', icon: Navigation },
  { name: 'Live Monitoring', href: '/monitoring', icon: Activity },
  { name: 'Video Analysis', href: '/video', icon: Video },
  { name: 'Road Intelligence', href: '/road-intelligence', icon: MapPin },
  { name: 'Traffic Intelligence', href: '/traffic', icon: Navigation },
  { name: 'Incidents', href: '/incidents', icon: AlertTriangle },
  { name: 'Fleet', href: '/fleet', icon: Bus },
  { name: 'Analytics', href: '/analytics', icon: BarChart2 },
  { name: 'Maintenance', href: '/maintenance', icon: Wrench },
  { name: 'AI Control Center', href: '/ai/control', icon: Cpu },
  { name: 'Model Lab', href: '/ai/pothole-lab', icon: Cpu },
]

const STORAGE_KEY = 'nw_sidebar_collapsed'

export function Sidebar() {
  const location = useLocation()
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem(STORAGE_KEY) === 'true' }
    catch { return false }
  })

  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, String(collapsed)) }
    catch {}
  }, [collapsed])

  return (
    <aside className={cn(
      "relative border-r border-border bg-card flex flex-col h-[calc(100vh-3.5rem)] sticky top-14 transition-all duration-200 ease-in-out shrink-0",
      collapsed ? "w-14" : "w-64"
    )}>
      {/* Collapse toggle button */}
      <button
        onClick={() => setCollapsed(c => !c)}
        className="absolute -right-3 top-6 z-20 flex h-6 w-6 items-center justify-center rounded-full border border-border bg-card shadow-sm hover:bg-secondary transition-colors"
        title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        {collapsed
          ? <ChevronRight className="h-3 w-3 text-muted-foreground" />
          : <ChevronLeft className="h-3 w-3 text-muted-foreground" />
        }
      </button>

      <div className="flex-1 overflow-y-auto py-4 overflow-x-hidden">
        <nav className="space-y-1 px-2">
          {navItems.map((item) => {
            const isActive = location.pathname === item.href
            return (
              <Link
                key={item.name}
                to={item.href}
                title={collapsed ? item.name : undefined}
                className={cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors group relative",
                  isActive
                    ? "bg-secondary text-secondary-foreground"
                    : "text-muted-foreground hover:bg-secondary/50 hover:text-foreground",
                  collapsed && "justify-center px-2"
                )}
              >
                <item.icon className="h-4 w-4 shrink-0" />
                {!collapsed && <span className="truncate">{item.name}</span>}
                {/* Floating tooltip when collapsed */}
                {collapsed && (
                  <span className="absolute left-full ml-2 px-2 py-1 text-xs font-medium bg-popover text-popover-foreground border border-border rounded-md shadow-md whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50">
                    {item.name}
                  </span>
                )}
              </Link>
            )
          })}
        </nav>
      </div>

      <div className={cn("border-t border-border", collapsed ? "p-2" : "px-4 py-4")}>
        <Link
          to="/settings"
          title={collapsed ? "Settings" : undefined}
          className={cn(
            "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors group relative",
            location.pathname === '/settings'
              ? "bg-secondary text-secondary-foreground"
              : "text-muted-foreground hover:bg-secondary/50 hover:text-foreground",
            collapsed && "justify-center px-2"
          )}
        >
          <Settings className="h-4 w-4 shrink-0" />
          {!collapsed && <span>Settings</span>}
          {collapsed && (
            <span className="absolute left-full ml-2 px-2 py-1 text-xs font-medium bg-popover text-popover-foreground border border-border rounded-md shadow-md whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50">
              Settings
            </span>
          )}
        </Link>
      </div>
    </aside>
  )
}

