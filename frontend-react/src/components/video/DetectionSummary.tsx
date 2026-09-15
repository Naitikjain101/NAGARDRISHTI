import { AlertTriangle, Droplets, List } from 'lucide-react';
import { cn } from '@/lib/utils';

interface DetectionSummaryProps {
  results: any;
  onSeek: (time: number) => void;
}

export function DetectionSummary({ results, onSeek }: DetectionSummaryProps) {
  if (!results) {
    return (
      <div className="bg-card border border-border rounded-lg shadow-sm flex flex-col h-full">
        <div className="px-4 py-3 border-b border-border flex items-center gap-2 shrink-0">
          <List className="h-4 w-4 text-primary" />
          <h3 className="font-semibold text-sm">Detection Log</h3>
        </div>
        <div className="flex-1 p-4 flex items-center justify-center text-sm text-muted-foreground italic">
          No detection data available.
        </div>
      </div>
    );
  }

  const potholes = results.pothole_events || [];
  const waterlogging = results.waterlogging_events || [];
  const allEvents = [...potholes, ...waterlogging].sort(
    (a, b) => a.first_seen_timestamp - b.first_seen_timestamp
  );

  return (
    <div className="bg-card border border-border rounded-lg shadow-sm flex flex-col h-full overflow-hidden">
      <div className="px-4 py-3 border-b border-border flex items-center justify-between shrink-0 bg-secondary/30">
        <div className="flex items-center gap-2">
          <List className="h-4 w-4 text-primary" />
          <h3 className="font-semibold text-sm">Detection Log</h3>
        </div>
        <span className="text-xs font-semibold bg-primary/10 text-primary px-2 py-0.5 rounded">
          {allEvents.length} Events
        </span>
      </div>

      <div className="grid grid-cols-2 gap-px bg-border shrink-0">
        <div className="bg-card p-3 flex flex-col items-center justify-center">
          <div className="flex items-center gap-1.5 text-orange-500 mb-1">
            <AlertTriangle className="h-4 w-4" />
            <span className="text-xs font-semibold uppercase tracking-wider">Potholes</span>
          </div>
          <span className="text-2xl font-bold">{potholes.length}</span>
        </div>
        <div className="bg-card p-3 flex flex-col items-center justify-center">
          <div className="flex items-center gap-1.5 text-blue-500 mb-1">
            <Droplets className="h-4 w-4" />
            <span className="text-xs font-semibold uppercase tracking-wider">Water</span>
          </div>
          <span className="text-2xl font-bold">{waterlogging.length}</span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-1 bg-secondary/10">
        {allEvents.length === 0 ? (
          <div className="h-full flex items-center justify-center text-sm text-muted-foreground italic">
            No infrastructure hazards detected.
          </div>
        ) : (
          allEvents.map((evt: any, i: number) => {
            const isPothole = evt.incident_type === 'pothole' || evt.type === 'pothole';
            return (
              <button
                key={evt.id || i}
                onClick={() => onSeek(evt.first_seen_timestamp)}
                className="w-full text-left px-3 py-2 rounded-md hover:bg-secondary border border-transparent hover:border-border transition-colors flex items-start gap-3 group"
              >
                <div className={cn(
                  "mt-0.5 p-1 rounded shrink-0",
                  isPothole ? "bg-orange-100 text-orange-600" : "bg-blue-100 text-blue-600"
                )}>
                  {isPothole ? <AlertTriangle className="h-3.5 w-3.5" /> : <Droplets className="h-3.5 w-3.5" />}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-semibold capitalize text-foreground">
                      {(evt.incident_type || evt.type || '').replace('_', ' ')}
                    </p>
                    <span className="text-xs font-mono text-muted-foreground bg-secondary/50 px-1 rounded">
                      {new Date(evt.first_seen_timestamp * 1000).toISOString().substr(14, 5)}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-[10px] text-muted-foreground">
                      Conf: {Math.round((evt.confidence || 0) * 100)}%
                    </span>
                    {evt.status === 'confirmed' && (
                      <span className="text-[10px] font-semibold text-green-600 bg-green-50 px-1 rounded">Verified</span>
                    )}
                  </div>
                </div>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}
