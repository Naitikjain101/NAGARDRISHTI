import { formatDistanceToNow } from 'date-fns';
import type { Incident } from '@/api/incidents';
import { Info, MapPin } from 'lucide-react';
import { StatusBadge } from '../ui/StatusBadge';

interface DataTableProps {
  incidents: Incident[];
  onRowClick: (incident: Incident) => void;
}

export function DataTable({ incidents, onRowClick }: DataTableProps) {
  if (incidents.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-12 bg-card border border-border rounded-lg text-center h-[400px]">
        <Info className="h-10 w-10 text-muted-foreground mb-4" />
        <p className="text-lg font-medium">No Incidents Found</p>
        <p className="text-sm text-muted-foreground mt-1">Try adjusting your filters or wait for the AI to detect new events.</p>
      </div>
    );
  }

  return (
    <div className="w-full overflow-x-auto rounded-lg border border-border bg-card">
      <table className="w-full text-sm text-left whitespace-nowrap">
        <thead className="text-[11px] font-semibold uppercase bg-secondary/50 text-muted-foreground border-b border-border">
          <tr>
            <th className="px-4 py-3 font-medium">Type</th>
            <th className="px-4 py-3 font-medium">Severity</th>
            <th className="px-4 py-3 font-medium">Status</th>
            <th className="px-4 py-3 font-medium">Detected</th>
            <th className="px-4 py-3 font-medium">Location</th>
            <th className="px-4 py-3 font-medium">Confidence</th>
            <th className="px-4 py-3 font-medium">ID</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border/50">
          {incidents.map((incident) => (
            <tr 
              key={incident.id} 
              className="hover:bg-secondary/20 cursor-pointer transition-colors group"
              onClick={() => onRowClick(incident)}
            >
              <td className="px-4 py-3 font-medium capitalize">
                {incident.type.replace('_', ' ')}
              </td>
              <td className="px-4 py-3">
                <StatusBadge status={incident.severity} type="severity" />
              </td>
              <td className="px-4 py-3">
                <StatusBadge status={incident.status} type="state" />
              </td>
              <td className="px-4 py-3 text-muted-foreground">
                <div className="flex flex-col">
                  <span>{formatDistanceToNow(new Date(incident.created_at), { addSuffix: true })}</span>
                  <span className="text-[10px] opacity-70">{new Date(incident.created_at).toLocaleTimeString()}</span>
                </div>
              </td>
              <td className="px-4 py-3">
                {incident.gps_available ? (
                  <span className="flex items-center gap-1.5 text-xs">
                    <MapPin className="h-3 w-3 text-emerald-500" />
                    {incident.latitude?.toFixed(4)}, {incident.longitude?.toFixed(4)}
                  </span>
                ) : (
                  <span className="text-muted-foreground text-xs">No GPS Data</span>
                )}
              </td>
              <td className="px-4 py-3">
                <div className="flex items-center gap-2">
                  <div className="w-16 h-1.5 bg-secondary rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-primary" 
                      style={{ width: `${Math.round(incident.confidence * 100)}%` }} 
                    />
                  </div>
                  <span className="text-xs font-mono">{Math.round(incident.confidence * 100)}%</span>
                </div>
              </td>
              <td className="px-4 py-3 text-muted-foreground font-mono text-xs">
                {incident.id.slice(0, 8)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
