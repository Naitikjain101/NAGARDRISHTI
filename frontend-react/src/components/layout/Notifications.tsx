import { Bell, AlertTriangle } from 'lucide-react';
import { useRealtimeIncidents } from '@/hooks/useRealtimeIncidents';
import { useState, useRef, useEffect } from 'react';
import { formatDistanceToNow } from 'date-fns';

export function Notifications() {
  const [isOpen, setIsOpen] = useState(false);
  const { data } = useRealtimeIncidents();
  const wrapperRef = useRef<HTMLDivElement>(null);

  const incidents = data?.incidents || [];
  const recentIncidents = incidents.slice(0, 5); // Just show top 5 most recent

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div className="relative" ref={wrapperRef}>
      <button 
        className={`relative p-2 rounded-md transition-colors ${isOpen ? 'bg-secondary text-foreground' : 'text-muted-foreground hover:bg-secondary/50 hover:text-foreground'}`}
        onClick={() => setIsOpen(!isOpen)}
      >
        <Bell className="h-5 w-5" />
        {recentIncidents.length > 0 && (
          <span className="absolute top-1.5 right-1.5 h-2 w-2 rounded-full bg-destructive animate-pulse"></span>
        )}
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-80 bg-card border border-border rounded-lg shadow-xl z-50 overflow-hidden animate-in fade-in slide-in-from-top-2 duration-200">
          <div className="p-3 border-b border-border flex justify-between items-center bg-secondary/30">
            <h3 className="font-semibold text-sm">Notifications</h3>
            <span className="text-xs text-muted-foreground cursor-pointer hover:text-foreground">Mark all read</span>
          </div>
          
          <div className="max-h-[350px] overflow-y-auto">
            {recentIncidents.length > 0 ? (
              <div className="divide-y divide-border">
                {recentIncidents.map(incident => (
                  <div key={incident.id} className="p-3 hover:bg-secondary/30 transition-colors cursor-pointer flex gap-3 items-start">
                    <div className={`mt-0.5 p-1.5 rounded-full shrink-0 ${incident.severity === 'CRITICAL' ? 'bg-red-500/20 text-red-500' : 'bg-orange-500/20 text-orange-500'}`}>
                      <AlertTriangle className="h-3 w-3" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium capitalize truncate">{incident.severity.toLowerCase()} {incident.type.replace('_', ' ')} detected</p>
                      <p className="text-xs text-muted-foreground mt-0.5">{formatDistanceToNow(new Date(incident.created_at), { addSuffix: true })}</p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-6 text-center text-sm text-muted-foreground">
                No new notifications.
              </div>
            )}
          </div>
          <div className="p-2 border-t border-border text-center bg-secondary/30">
            <button className="text-xs text-muted-foreground hover:text-foreground font-medium">View All Alerts</button>
          </div>
        </div>
      )}
    </div>
  );
}
