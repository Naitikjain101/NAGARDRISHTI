import { Wrench, CheckCircle, Clock, AlertTriangle, Plus } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { maintenanceApi } from '@/api/maintenance';
import { useState } from 'react';
import { IncidentDrawer } from '@/components/incidents/IncidentDrawer';
import { PageHeader } from '@/components/ui/PageHeader';
import { EmptyState } from '@/components/ui/EmptyState';
import { Skeleton } from '@/components/ui/Skeleton';
import { StatusBadge } from '@/components/ui/StatusBadge';

const columns = [
  { id: 'UNASSIGNED', title: 'Unassigned',  icon: AlertTriangle, color: 'text-orange-600', bg: 'bg-orange-50 border-orange-200' },
  { id: 'ASSIGNED',   title: 'Assigned',    icon: Clock,         color: 'text-amber-600',  bg: 'bg-amber-50 border-amber-200' },
  { id: 'IN_PROGRESS',title: 'In Progress', icon: Wrench,        color: 'text-blue-600',   bg: 'bg-blue-50 border-blue-200' },
  { id: 'RESOLVED',   title: 'Resolved',    icon: CheckCircle,   color: 'text-green-600',  bg: 'bg-green-50 border-green-200' },
];

export function Maintenance() {
  const { data: tasks, isLoading } = useQuery({
    queryKey: ['maintenance'],
    queryFn: maintenanceApi.getTasks
  });

  const [selectedIncident, setSelectedIncident] = useState<any | null>(null);

  return (
    <div className="page-content">
      <PageHeader
        title="Maintenance Dispatch"
        icon={Wrench}
        description="Assign and track resolution of physical infrastructure hazards."
        actions={
          <button
            disabled
            className="flex items-center gap-2 px-3 py-1.5 text-xs font-medium border border-border rounded text-muted-foreground cursor-not-allowed opacity-60"
          >
            <Plus className="h-3.5 w-3.5" />
            Manual Ticket
          </button>
        }
      />

      {/* Kanban board */}
      <div className="flex-1 min-h-0 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 overflow-x-auto pb-2">
        {columns.map(col => {
          const colTasks = tasks?.filter((t: any) => t.status === col.id) || [];

          return (
            <div key={col.id} className="bg-card border border-border rounded-lg flex flex-col min-h-[500px] min-w-[260px] shadow-card">
              {/* Column header */}
              <div className={`px-3 py-2.5 border-b border-border flex items-center justify-between rounded-t-lg ${col.bg} bg-opacity-50`}>
                <div className="flex items-center gap-2">
                  <col.icon className={`h-4 w-4 ${col.color}`} />
                  <h3 className={`text-xs font-semibold uppercase tracking-wider ${col.color}`}>
                    {col.title}
                  </h3>
                </div>
                <span className="text-xs font-bold bg-white/70 border border-border px-1.5 py-0.5 rounded text-muted-foreground">
                  {colTasks.length}
                </span>
              </div>

              {/* Tasks */}
              <div className="flex-1 p-2 overflow-y-auto space-y-2 bg-secondary/20">
                {isLoading ? (
                  <Skeleton className="h-20" />
                ) : colTasks.length === 0 ? (
                  <EmptyState
                    icon={Wrench}
                    title="Queue Empty"
                    description="No tickets in this status."
                    className="min-h-[120px]"
                  />
                ) : (
                  colTasks.map((task: any) => (
                    <div
                      key={task.id}
                      className="bg-card border border-border rounded-md p-3 shadow-card text-sm cursor-pointer hover:border-primary/30 hover:shadow transition-all"
                      onClick={() => {
                        const incident = task.incidents as any;
                        if (incident) {
                          incident.action = task;
                          setSelectedIncident(incident);
                        }
                      }}
                    >
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <span className="font-semibold text-foreground text-xs leading-snug">{task.action_type}</span>
                        <span className="text-[9px] text-muted-foreground font-mono shrink-0">
                          {task.id.split('-')[0].toUpperCase()}
                        </span>
                      </div>

                      {task.assigned_department && (
                        <p className="text-[11px] text-muted-foreground mb-2 line-clamp-1">
                          {task.assigned_department}
                        </p>
                      )}

                      <div className="flex items-center justify-between">
                        <span className="text-[10px] text-muted-foreground">
                          {new Date(task.created_at).toLocaleDateString('en-IN')}
                        </span>
                        <StatusBadge status={task.status} type="state" />
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          );
        })}
      </div>

      <IncidentDrawer
        incident={selectedIncident}
        onClose={() => setSelectedIncident(null)}
      />
    </div>
  );
}
