import { Bell, User, ChevronDown } from 'lucide-react'
import { useState } from 'react'
import { useLocation } from 'react-router-dom'
import { Notifications } from './Notifications'

// Map routes to display names
const routeLabels: Record<string, string> = {
  '/':                 'Command Center',
  '/monitoring':       'Live Monitoring',
  '/video':            'Video Analysis',
  '/map':              'Live Map',
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
  const location = useLocation()
  const pageTitle = getRouteLabel(location.pathname)

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

        {/* User stub */}
        <button
          id="user-menu-btn"
          className="flex items-center gap-2 px-2 py-1.5 rounded text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors"
          aria-label="User account"
        >
          <div className="w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center">
            <User className="h-3.5 w-3.5 text-primary" />
          </div>
          <span className="text-xs font-medium hidden md:block">Admin</span>
          <ChevronDown className="h-3 w-3 hidden md:block" />
        </button>
      </div>
    </header>
  )
}
