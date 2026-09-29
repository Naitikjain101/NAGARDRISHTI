import { useState } from 'react';
import { Wrench, CheckCircle, Clock, AlertTriangle, Plus } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { maintenanceApi } from '@/api/maintenance';
import type { MaintenanceAction } from '@/api/maintenance';
import { IncidentDrawer } from '@/components/incidents/IncidentDrawer';
import { PageHeader } from '@/components/ui/PageHeader';
import { Skeleton } from '@/components/ui/Skeleton';
import { MaintenanceTable } from '@/components/maintenance/MaintenanceTable';
import { SearchInput } from '@/components/ui/SearchInput';
import { Select } from '@/components/ui/Select';
import { Button } from '@/components/ui/Button';

export function Maintenance() {
  const { data: allTasks = [], isLoading } = useQuery({
    queryKey: ['maintenance'],
    queryFn: maintenanceApi.getTasks,
    refetchInterval: 5000,
  });

  const [selectedIncident, setSelectedIncident] = useState<any | null>(null);
  
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [assignmentFilter, setAssignmentFilter] = useState('');
  const [routeFilter, setRouteFilter] = useState('');

  // Extract unique routes from tasks for the dropdown
  const uniqueRoutes = Array.from(new Set(
    allTasks.map((t: any) => t.incidents?.route_name || t.incidents?.metadata?.route_name).filter(Boolean)
  )).sort();

  // Filter Logic
  const tasks = allTasks.filter((task: any) => {
    const incident = task.incidents;
    const matchesSearch = !search || 
      task.id?.toLowerCase().includes(search.toLowerCase()) || 
      task.action_type?.toLowerCase().includes(search.toLowerCase()) ||
      incident?.incident_type?.toLowerCase().includes(search.toLowerCase());
    
    const matchesStatus = !statusFilter || task.status === statusFilter;
    const priority = incident?.priority_level || incident?.severity || '';
    const matchesPriority = !priorityFilter || priority === priorityFilter;
    const matchesType = !typeFilter || task.action_type?.includes(typeFilter) || incident?.incident_type === typeFilter;
    const matchesAssignment = !assignmentFilter || 
      (assignmentFilter === 'ASSIGNED' && task.assigned_department) ||
      (assignmentFilter === 'UNASSIGNED' && !task.assigned_department);
    const incidentRoute = incident?.route_name || incident?.metadata?.route_name || '';
    const matchesRoute = !routeFilter || incidentRoute === routeFilter;
    
    return matchesSearch && matchesStatus && matchesPriority && matchesType && matchesAssignment && matchesRoute;
  });

  const activeTasks = allTasks.filter(t => t.status !== 'RESOLVED');

  return (
    <div className="page-content">
      <PageHeader
        title="Maintenance Dispatch"
        icon={Wrench}
        description="Assign and track resolution of physical infrastructure hazards."
        actions={
          <Button variant="outline" size="sm" icon={Plus} disabled className="opacity-60 cursor-not-allowed">
            Manual Ticket
          </Button>
        }
      />

      {/* Metrics Panel */}
      <div className="grid grid-cols-4 gap-4 mb-2">
        <div className="bg-card border border-border rounded-xl p-4 flex items-center justify-between shadow-sm">
          <div>
            <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Open Work Orders</p>
            <p className="text-3xl font-black mt-1">{activeTasks.length}</p>
          </div>
          <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
            <Wrench className="w-5 h-5 text-primary" />
          </div>
        </div>
        <div className="bg-card border border-border rounded-xl p-4 flex items-center justify-between shadow-sm">
          <div>
            <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Unassigned</p>
            <p className="text-3xl font-black mt-1 text-orange-500">
              {activeTasks.filter(t => t.status === 'UNASSIGNED' || !t.assigned_department).length}
            </p>
          </div>
          <div className="w-10 h-10 rounded-full bg-orange-500/10 flex items-center justify-center">
            <AlertTriangle className="w-5 h-5 text-orange-500" />
          </div>
        </div>
        <div className="bg-card border border-border rounded-xl p-4 flex items-center justify-between shadow-sm">
          <div>
            <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">In Progress</p>
            <p className="text-3xl font-black mt-1 text-blue-500">
              {allTasks.filter(t => t.status === 'IN_PROGRESS').length}
            </p>
          </div>
          <div className="w-10 h-10 rounded-full bg-blue-500/10 flex items-center justify-center">
            <Clock className="w-5 h-5 text-blue-500" />
          </div>
        </div>
        <div className="bg-card border border-border rounded-xl p-4 flex items-center justify-between shadow-sm">
          <div>
            <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Resolved</p>
            <p className="text-3xl font-black mt-1 text-emerald-500">
              {allTasks.filter(t => t.status === 'RESOLVED').length}
            </p>
          </div>
          <div className="w-10 h-10 rounded-full bg-emerald-500/10 flex items-center justify-center">
            <CheckCircle className="w-5 h-5 text-emerald-500" />
          </div>
        </div>
      </div>

      {/* Filter bar */}
      <div className="bg-card border border-border rounded-lg p-3 flex flex-wrap items-center gap-3">
        <SearchInput
          value={search}
          onChange={setSearch}
          placeholder="Search by ID, location, or type..."
          className="min-w-[220px] flex-1"
          id="maintenance-search"
        />

        <Select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
          aria-label="Filter by status"
        >
          <option value="">All Statuses</option>
          <option value="UNASSIGNED">Unassigned</option>
          <option value="ASSIGNED">Assigned</option>
          <option value="IN_PROGRESS">In Progress</option>
          <option value="RESOLVED">Resolved</option>
        </Select>

        <Select
          value={priorityFilter}
          onChange={e => setPriorityFilter(e.target.value)}
          aria-label="Filter by priority"
        >
          <option value="">All Priorities</option>
          <option value="CRITICAL">Critical</option>
          <option value="HIGH">High</option>
          <option value="MODERATE">Moderate</option>
          <option value="LOW">Low</option>
        </Select>
        
        <Select
          value={assignmentFilter}
          onChange={e => setAssignmentFilter(e.target.value)}
          aria-label="Filter by assignment"
        >
          <option value="">All Assignments</option>
          <option value="UNASSIGNED">Unassigned Teams</option>
          <option value="ASSIGNED">Assigned Teams</option>
        </Select>

        <Select
          value={routeFilter}
          onChange={e => setRouteFilter(e.target.value)}
          aria-label="Filter by Route"
        >
          <option value="">All Routes</option>
          {uniqueRoutes.map((route: any) => (
            <option key={route} value={route}>{route}</option>
          ))}
        </Select>

        {(search || statusFilter || priorityFilter || typeFilter || assignmentFilter || routeFilter) && (
          <button
            onClick={() => { setSearch(''); setStatusFilter(''); setPriorityFilter(''); setTypeFilter(''); setAssignmentFilter(''); setRouteFilter(''); }}
            className="text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Count */}
      {!isLoading && (
        <p className="text-xs text-muted-foreground -mt-2">
          Showing <span className="font-semibold text-foreground">{tasks.length}</span> of{' '}
          <span className="font-semibold text-foreground">{allTasks.length}</span> work orders
        </p>
      )}

      {/* Table */}
      <div className="flex-1 min-h-0">
        {isLoading ? (
          <div className="space-y-2">
            {[1, 2, 3, 4, 5].map(i => (
              <Skeleton key={i} className="h-12 w-full rounded-lg" />
            ))}
          </div>
        ) : allTasks.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-12 bg-card border border-border rounded-lg text-center h-[400px]">
            <Wrench className="h-10 w-10 text-muted-foreground mb-4 opacity-50" />
            <p className="text-sm font-bold text-muted-foreground uppercase tracking-widest">
              No maintenance work orders
            </p>
          </div>
        ) : tasks.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-12 bg-card border border-border rounded-lg text-center h-[400px]">
            <AlertTriangle className="h-10 w-10 text-muted-foreground mb-4 opacity-50" />
            <p className="text-sm font-bold text-muted-foreground uppercase tracking-widest">
              No work orders match your filters.
            </p>
          </div>
        ) : (
          <MaintenanceTable
            tasks={tasks}
            onRowClick={(task: MaintenanceAction) => {
              const incident = (task as any).incidents;
              if (incident) {
                incident.action = task;
                setSelectedIncident(incident);
              }
            }}
          />
        )}
      </div>

      <IncidentDrawer
        incident={selectedIncident}
        onClose={() => setSelectedIncident(null)}
      />
    </div>
  );
}
