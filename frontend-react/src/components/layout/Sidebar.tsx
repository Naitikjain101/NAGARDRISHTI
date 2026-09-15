import { Link, useLocation } from 'react-router-dom'
import { useState, useEffect } from 'react'
import {
  LayoutDashboard, Activity, Video,
  MapPin, Navigation, AlertTriangle, Bus,
  Wrench, Settings, Map, Waves
} from 'lucide-react'
import { cn } from '@/lib/utils'

const navItems = [
  { name: 'Command Center',        href: '/',                icon: LayoutDashboard },
  { name: 'Live Monitoring',       href: '/monitoring',      icon: Activity },
  { name: 'Video Analysis',        href: '/video',           icon: Video },
  { name: 'Live Map',              href: '/map',             icon: Map },
  { name: 'Road Intelligence',     href: '/road-intelligence', icon: MapPin },
  { name: 'Traffic Intelligence',  href: '/traffic',         icon: Navigation },
  { name: 'Incidents',             href: '/incidents',       icon: AlertTriangle },
  { name: 'Maintenance',           href: '/maintenance',     icon: Wrench },
  { name: 'Fleet',                 href: '/fleet',           icon: Bus },
]

const STORAGE_KEY = 'nd_sidebar_collapsed'

function NavItem({
  item,
  isActive,
  collapsed,
}: {
  item: { name: string; href: string; icon: React.ComponentType<{ className?: string }> }
  isActive: boolean
  collapsed: boolean
}) {
  const Icon = item.icon

  return (
    <Link
      to={item.href}
      title={collapsed ? item.name : undefined}
      aria-current={isActive ? 'page' : undefined}
      className={cn(
        'nav-item',
        isActive && 'active',
        collapsed && 'justify-center px-2'
      )}
    >
      <Icon className="h-4 w-4 shrink-0" />
      {!collapsed && <span>{item.name}</span>}

      {/* Tooltip when collapsed */}
      {collapsed && (
        <span
          aria-hidden="true"
          className="pointer-events-none absolute left-full ml-2 px-2 py-1 text-xs font-medium bg-foreground text-background rounded shadow-dropdown whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity z-50"
        >
          {item.name}
        </span>
      )}
    </Link>
  )
}

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

  const isActive = (href: string) => {
    if (href === '/') return location.pathname === '/'
    return location.pathname.startsWith(href)
  }

  return (
    <aside
      style={{ backgroundColor: 'var(--sidebar-bg)', borderRight: '1px solid var(--sidebar-border)' }}
      className={cn(
        'relative flex flex-col h-full overflow-hidden shrink-0 transition-all duration-200 ease-in-out',
        collapsed ? 'w-14' : 'w-56'
      )}
    >
      {/* Logo / Branding */}
      <div
        role="button"
        tabIndex={0}
        onClick={() => setCollapsed(c => !c)}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setCollapsed(c => !c) }}
        title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        style={{ borderBottom: '1px solid var(--sidebar-border)' }}
        className={cn('flex items-center h-14 shrink-0 px-4 gap-3 cursor-pointer hover:bg-white/5 transition-colors', collapsed && 'justify-center px-2')}
      >
        {/* Logo mark */}
        <div className="w-7 h-7 rounded-md bg-primary flex items-center justify-center shrink-0">
          <Waves className="h-4 w-4 text-white" />
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <p className="text-white font-semibold text-sm leading-tight truncate">NagarDrishti</p>
            <p className="text-[10px] leading-tight truncate" style={{ color: 'var(--sidebar-text-muted)' }}>
              Municipal Intelligence
            </p>
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav
        className="flex-1 overflow-y-auto overflow-x-hidden py-3 px-2 space-y-0.5"
        aria-label="Main navigation"
      >
        {/* Section label */}
        {!collapsed && (
          <p className="px-2 py-1.5 text-[10px] font-semibold uppercase tracking-widest" style={{ color: 'var(--sidebar-text-muted)' }}>
            Operations
          </p>
        )}

        {navItems.map(item => (
          <div key={item.href} className="group relative">
            <NavItem
              item={item}
              isActive={isActive(item.href)}
              collapsed={collapsed}
            />
          </div>
        ))}
      </nav>

      {/* Bottom — Settings */}
      <div
        style={{ borderTop: '1px solid var(--sidebar-border)' }}
        className="shrink-0 p-2"
      >
        <div className="group relative">
          <Link
            to="/settings"
            title={collapsed ? 'Settings' : undefined}
            aria-current={isActive('/settings') ? 'page' : undefined}
            className={cn(
              'nav-item',
              isActive('/settings') && 'active',
              collapsed && 'justify-center px-2'
            )}
          >
            <Settings className="h-4 w-4 shrink-0" />
            {!collapsed && <span>Settings</span>}
            {collapsed && (
              <span
                aria-hidden="true"
                className="pointer-events-none absolute left-full ml-2 px-2 py-1 text-xs font-medium bg-foreground text-background rounded shadow-dropdown whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity z-50"
              >
                Settings
              </span>
            )}
          </Link>
        </div>
      </div>


    </aside>
  )
}
