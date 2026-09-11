import { Wrench, CheckCircle, Clock, AlertTriangle, Plus } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { maintenanceApi } from '@/api/maintenance';

export function Maintenance() {
  const { data: tasks, isLoading } = useQuery({
    queryKey: ['maintenance'],
    queryFn: maintenanceApi.getTasks
  });

  const columns = [
    { id: 'OPEN', title: 'OPEN / UNASSIGNED', icon: AlertTriangle, color: 'text-red-500' },
    { id: 'ASSIGNED', title: 'ASSIGNED', icon: Clock, color: 'text-orange-500' },
    { id: 'IN_PROGRESS', title: 'IN PROGRESS', icon: Wrench, color: 'text-blue-500' },
    { id: 'RESOLVED', title: 'RESOLVED', icon: CheckCircle, color: 'text-emerald-500' },
  ];

  return (
    <div className="space-y-6 flex flex-col h-full">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-2xl font-bold">Maintenance Dispatch</h1>
          <p className="text-muted-foreground">Assign and track resolution of physical infrastructure hazards.</p>
        </div>
        <button disabled className="flex items-center gap-2 px-3 py-1.5 bg-primary/50 text-primary-foreground rounded-md text-sm cursor-not-allowed">
          <Plus className="h-4 w-4" /> Manual Ticket
        </button>
      </div>

      <div className="flex-1 min-h-0 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 overflow-x-auto pb-2">
        {columns.map(col => {
          const colTasks = tasks?.filter(t => t.status === col.id) || [];
          
          return (
            <div key={col.id} className="bg-card border border-border rounded-lg flex flex-col h-full overflow-hidden min-w-[280px]">
              <div className="p-3 border-b border-border bg-secondary/30 flex justify-between items-center">
                <h3 className={`font-semibold text-sm flex items-center gap-2 uppercase tracking-wider ${col.color}`}>
                  <col.icon className="h-4 w-4" /> {col.title}
                </h3>
                <span className="text-xs font-bold bg-secondary px-2 py-0.5 rounded-full text-muted-foreground">
                  {colTasks.length}
                </span>
              </div>
              
              <div className="flex-1 p-2 bg-secondary/10 overflow-y-auto flex flex-col gap-2">
                {isLoading ? (
                   <div className="animate-pulse bg-secondary/50 h-24 rounded-md"></div>
                ) : colTasks.length === 0 ? (
                  <div className="h-full flex flex-col items-center justify-center text-center p-4 min-h-[150px]">
                    <Wrench className="h-8 w-8 text-muted-foreground/30 mb-2" />
                    <p className="text-sm font-medium text-muted-foreground">Queue Empty</p>
                    <p className="text-xs text-muted-foreground/70 mt-1">
                      No tickets currently in this status.
                    </p>
                  </div>
                ) : (
                  colTasks.map(task => (
                    <div key={task.id} className="bg-card border border-border rounded-md p-3 shadow-sm text-sm">
                      <div className="flex justify-between items-start mb-1">
                        <span className="font-semibold">{task.title}</span>
                        <span className={`text-[10px] px-1.5 py-0.5 rounded-sm font-medium ${
                          task.severity === 'CRITICAL' ? 'bg-red-500/10 text-red-500' :
                          task.severity === 'HIGH' ? 'bg-orange-500/10 text-orange-500' :
                          'bg-blue-500/10 text-blue-500'
                        }`}>
                          {task.severity}
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground mb-2 line-clamp-2">{task.description}</p>
                      <div className="flex justify-between text-xs text-muted-foreground">
                        <span>{new Date(task.created_at).toLocaleDateString()}</span>
                        {task.assigned_to && <span>{task.assigned_to}</span>}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
