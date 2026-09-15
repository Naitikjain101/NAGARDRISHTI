import { formatDistanceToNow } from 'date-fns';
import type { MaintenanceAction } from '@/api/maintenance';
import { Wrench, MapPin } from 'lucide-react';
import { StatusBadge } from '../ui/StatusBadge';

interface MaintenanceTableProps {
  tasks: MaintenanceAction[];
  onRowClick: (task: MaintenanceAction) => void;
}

export function MaintenanceTable({ tasks, onRowClick }: MaintenanceTableProps) {
  if (tasks.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-12 bg-card border border-border rounded-lg text-center h-[400px]">
        <Wrench className="h-10 w-10 text-muted-foreground mb-4 opacity-50" />
        <p className="text-sm font-bold text-muted-foreground uppercase tracking-widest">
          No maintenance work orders
        </p>
      </div>
    );
  }

  return (
    <div className="w-full overflow-x-auto rounded-lg border border-border bg-card">
      <table className="w-full text-sm text-left whitespace-nowrap">
        <thead className="text-[11px] font-semibold uppercase bg-secondary/50 text-muted-foreground border-b border-border">
          <tr>
            <th className="px-4 py-3 font-medium">Work Order ID</th>
            <th className="px-4 py-3 font-medium">Issue</th>
            <th className="px-4 py-3 font-medium">Location</th>
            <th className="px-4 py-3 font-medium">Priority</th>
            <th className="px-4 py-3 font-medium">Status</th>
            <th className="px-4 py-3 font-medium">Assigned To</th>
            <th className="px-4 py-3 font-medium">Date Created</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border/50">
          {tasks.map((task) => {
            const incident = (task as any).incidents;
            return (
              <tr 
                key={task.id} 
                className="hover:bg-secondary/20 cursor-pointer transition-colors group"
                onClick={() => onRowClick(task)}
              >
                <td className="px-4 py-3 font-mono text-xs font-bold">
                  WO-{task.id.split('-')[0].toUpperCase()}
                </td>
                <td className="px-4 py-3 font-medium">
                  {task.action_type || (incident?.incident_type ? incident.incident_type.replace('_', ' ') : 'Unknown Issue')}
                </td>
                <td className="px-4 py-3">
                  {incident?.latitude ? (
                    <span className="flex flex-col">
                      <span className="flex items-center gap-1.5 text-xs">
                        <MapPin className="h-3 w-3 text-emerald-500" />
                        {incident.latitude.toFixed(4)}, {incident.longitude.toFixed(4)}
                      </span>
                      <span className="text-[9px] text-muted-foreground ml-4">GPS-linked</span>
                    </span>
                  ) : (
                    <span className="text-muted-foreground text-xs">Location unavailable</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  {incident?.priority_level ? (
                    <StatusBadge status={incident.priority_level} type="severity" />
                  ) : incident?.severity ? (
                    <StatusBadge status={incident.severity} type="severity" />
                  ) : (
                    <span className="text-muted-foreground text-xs">N/A</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <StatusBadge status={task.status} type="state" />
                </td>
                <td className="px-4 py-3 text-xs">
                  {task.assigned_department ? (
                    <span className="text-foreground">{task.assigned_department}</span>
                  ) : (
                    <span className="text-muted-foreground italic">Unassigned</span>
                  )}
                </td>
                <td className="px-4 py-3 text-muted-foreground">
                  <div className="flex flex-col">
                    <span>{formatDistanceToNow(new Date(task.created_at), { addSuffix: true })}</span>
                    <span className="text-[10px] opacity-70">{new Date(task.created_at).toLocaleDateString()}</span>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
