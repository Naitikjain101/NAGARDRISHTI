
import { Link, useLocation } from 'react-router-dom'
import { 
  LayoutDashboard, Map, Activity, Video, 
  MapPin, Navigation, AlertTriangle, Bus, 
  BarChart2, Wrench, Cpu, Settings
} from 'lucide-react'
import { cn } from '@/lib/utils'

const navItems = [
  { name: 'Overview', href: '/', icon: LayoutDashboard },
  { name: 'Live Map (Command Center)', href: '/map', icon: Map },
  { name: 'Fleet Consensus Replay', href: '/fleet-replay', icon: Navigation },
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

export function Sidebar() {
  const location = useLocation()

  return (
    <aside className="w-64 border-r border-border bg-card flex flex-col h-[calc(100vh-3.5rem)] sticky top-14">
      <div className="flex-1 overflow-y-auto py-4">
        <nav className="space-y-1 px-2">
          {navItems.map((item) => {
            const isActive = location.pathname === item.href
            return (
              <Link
                key={item.name}
                to={item.href}
                className={cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  isActive 
                    ? "bg-secondary text-secondary-foreground" 
                    : "text-muted-foreground hover:bg-secondary/50 hover:text-foreground"
                )}
              >
                <item.icon className="h-4 w-4" />
                {item.name}
              </Link>
            )
          })}
        </nav>
      </div>
      <div className="p-4 border-t border-border">
        <Link
          to="/settings"
          className={cn(
            "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
            location.pathname === '/settings'
              ? "bg-secondary text-secondary-foreground" 
              : "text-muted-foreground hover:bg-secondary/50 hover:text-foreground"
          )}
        >
          <Settings className="h-4 w-4" />
          Settings
        </Link>
      </div>
    </aside>
  )
}
