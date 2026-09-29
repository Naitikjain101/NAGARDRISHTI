import { AlertTriangle, X } from 'lucide-react';
import { useRealtimeIncidents } from '@/hooks/useRealtimeIncidents';
import { useRef, useEffect } from 'react';
import { formatDistanceToNow } from 'date-fns';

interface NotificationsProps {
  onClose?: () => void;
}

export function Notifications({ onClose }: NotificationsProps) {
  const { data } = useRealtimeIncidents();
  const wrapperRef = useRef<HTMLDivElement>(null);

  const incidents = data?.incidents || [];
  const recentIncidents = incidents.slice(0, 5);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        onClose?.();
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [onClose]);

  return (
    <div
      ref={wrapperRef}
      className="absolute right-0 top-full mt-2 w-80 bg-card border border-border rounded-lg shadow-dropdown z-50 overflow-hidden animate-in fade-in slide-in-from-top-2 duration-150"
    >
      <div className="px-4 py-3 border-b border-border flex justify-between items-center">
        <h3 className="text-sm font-semibold text-foreground">Recent Alerts</h3>
        <button
          onClick={onClose}
          className="p-0.5 rounded text-muted-foreground hover:text-foreground transition-colors"
          aria-label="Close notifications"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      <div className="max-h-72 overflow-y-auto">
        {recentIncidents.length > 0 ? (
          <div className="divide-y divide-border">
              {recentIncidents.map(incident => {
                const inc = incident as any;
                const type = inc.incident_type || inc.type || '';
                const ts = inc.created_at || inc.first_seen_at;
                return (
                  <div key={inc.id} className="px-4 py-3 hover:bg-secondary/50 transition-colors cursor-pointer flex gap-3 items-start">
                    <div className={`mt-0.5 p-1.5 rounded shrink-0 ${
                      inc.severity === 'CRITICAL' ? 'bg-red-100 text-red-600' : 'bg-amber-100 text-amber-600'
                    }`}>
                      <AlertTriangle className="h-3 w-3" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-foreground capitalize truncate">
                        {inc.severity?.toLowerCase()} {type.replace('_', ' ')} detected
                      </p>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {ts ? formatDistanceToNow(new Date(ts), { addSuffix: true }) : ''}
                      </p>
                    </div>
                  </div>
                );
              })}
          </div>
        ) : (
          <div className="py-8 text-center text-sm text-muted-foreground">
            No new alerts
          </div>
        )}
      </div>

      <div className="px-4 py-2.5 border-t border-border bg-secondary/30 text-center">
        <button className="text-xs font-medium text-primary hover:text-primary/80 transition-colors">
          View all incidents →
        </button>
      </div>
    </div>
  );
}
