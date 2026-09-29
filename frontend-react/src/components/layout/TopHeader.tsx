import { Bell, User, ChevronDown, LogOut } from 'lucide-react'
import { useState, useRef, useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { Notifications } from './Notifications'
import { useAuth } from '../../contexts/AuthContext'

// Map routes to display names
const routeLabels: Record<string, string> = {
  '/':                 'Command Center',
  '/monitoring':       'Live Monitoring',
  '/video':            'Video Analysis',
  '/road-intelligence':'Road Intelligence',
  '/traffic':          'Traffic Intelligence',
  '/incidents':        'Incidents',
  '/maintenance':      'Maintenance Dispatch',
  '/fleet':            'Fleet',
  '/fleet-replay':     'Fleet Replay',
  '/settings':         'Settings',
  '/ai/control':       'AI Control Center',
  '/ai/pothole-lab':   'Model Lab',
}

function getRouteLabel(pathname: string): string {
  // Exact match first
  if (routeLabels[pathname]) return routeLabels[pathname]
  // Prefix match
  for (const [route, label] of Object.entries(routeLabels)) {
    if (route !== '/' && pathname.startsWith(route)) return label
  }
  return 'NagarDrishti'
}

export function TopHeader() {
  const [notifOpen, setNotifOpen] = useState(false)
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const location = useLocation()
  const pageTitle = getRouteLabel(location.pathname)
  const { user, profile, signOut } = useAuth()
  const userMenuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target as Node)) {
        setUserMenuOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [userMenuRef])

  const displayName = profile?.display_name || profile?.username || user?.email || 'User'
  const displayRole = profile?.role ? profile.role.replace(/_/g, ' ') : 'VIEWER'

  return (
    <header className="h-14 border-b border-border bg-card flex items-center justify-between px-5 shrink-0 z-30">
      {/* Left: application context */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold text-foreground">NagarDrishti</span>
          <span className="text-muted-foreground text-xs">/</span>
          <span className="text-xs font-medium text-muted-foreground">{pageTitle}</span>
        </div>
      </div>

      {/* Right: actions */}
      <div className="flex items-center gap-1">
        {/* Notifications */}
        <div className="relative">
          <button
            id="notifications-btn"
            onClick={() => setNotifOpen(o => !o)}
            className="relative p-2 rounded text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors"
            aria-label="Open notifications"
          >
            <Bell className="h-4 w-4" />
            {/* Unread dot — will be driven by notification data later */}
            <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full bg-red-500" aria-hidden="true" />
          </button>
          {notifOpen && <Notifications onClose={() => setNotifOpen(false)} />}
        </div>

        {/* User Profile Menu */}
        <div className="relative" ref={userMenuRef}>
          <button
            id="user-menu-btn"
            onClick={() => setUserMenuOpen(!userMenuOpen)}
            className="flex items-center gap-2 px-2 py-1.5 rounded text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors"
            aria-label="User account"
          >
            <div className="w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center">
              <User className="h-3.5 w-3.5 text-primary" />
            </div>
            <div className="flex flex-col items-start hidden md:flex">
              <span className="text-xs font-medium leading-none">{displayName}</span>
              <span className="text-[10px] text-muted-foreground mt-0.5 capitalize">{displayRole.toLowerCase()}</span>
            </div>
            <ChevronDown className="h-3 w-3 hidden md:block" />
          </button>

          {userMenuOpen && (
            <div className="absolute right-0 mt-2 w-48 rounded-md shadow-lg bg-card border border-border py-1 z-50">
              <div className="px-4 py-2 border-b border-border/50 md:hidden">
                <p className="text-sm font-medium text-foreground truncate">{displayName}</p>
                <p className="text-xs text-muted-foreground capitalize truncate">{displayRole.toLowerCase()}</p>
              </div>
              <button
                onClick={() => {
                  setUserMenuOpen(false);
                  signOut();
                }}
                className="w-full text-left px-4 py-2 text-sm text-red-400 hover:bg-secondary flex items-center gap-2 transition-colors"
              >
                <LogOut className="h-4 w-4" />
                Sign Out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
