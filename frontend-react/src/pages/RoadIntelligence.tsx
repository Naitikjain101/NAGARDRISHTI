import { useState, useEffect, useMemo } from 'react';
import { MapPin, AlertTriangle, Hammer, Loader2, Navigation } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { useRealtimeIncidents } from '@/hooks/useRealtimeIncidents';
import { maintenanceApi } from '@/api/maintenance';
import { PageHeader } from '@/components/ui/PageHeader';
import { IncidentDrawer } from '@/components/incidents/IncidentDrawer';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { formatDistanceToNow } from 'date-fns';
import { fetchRaw } from '../api/client';

export function RoadIntelligence() {
  const { data: incidentData, isLoading: isLoadingIncidents } = useRealtimeIncidents();
  const incidents = incidentData?.incidents || [];
  
  const { data: tasks = [], isLoading: isLoadingTasks } = useQuery({
    queryKey: ['maintenance'],
    queryFn: maintenanceApi.getTasks,
    refetchInterval: 5000,
  });

  const [missions, setMissions] = useState<any[]>([]);
  const [selectedRoute, setSelectedRoute] = useState<string>('all');
  const [selectedIncident, setSelectedIncident] = useState<any | null>(null);

  useEffect(() => {
    fetchRaw('/api/missions/')
      .then(r => r.json())
      .then(data => setMissions(data.missions || []))
      .catch(console.error);
  }, []);

  const isLoading = isLoadingIncidents || isLoadingTasks;

  const {
    missionMap,
    activeIncidents,
    highPriorityCount,
    inMaintenanceCount,
    routeAggregates,
    attentionQueue
  } = useMemo(() => {
    // 1. Build map of video_id -> route_name
    const missionMap = new Map<string, string>();
    missions.forEach(m => {
      const vId = m.metadata?.video_id || m.video_filename;
      if (vId) missionMap.set(vId, m.route_name || 'Unknown Route');
    });

    // 2. Filter incidents by route if selected
    const filteredIncidents = incidents.filter(i => {
      if (selectedRoute === 'all') return true;
      let rName = i.metadata?.route_name || missionMap.get(i.video_id) || missionMap.get(i.source_mission_id || '') || 'Unknown Route';
      return rName === selectedRoute;
    });

    // 3. Operational Summary metrics
    const activeIncidents = filteredIncidents.filter(i => i.status !== 'suppressed' && i.status !== 'rejected');
    const highPriorityCount = activeIncidents.filter(i => i.severity === 'CRITICAL' || i.severity === 'HIGH').length;
    
    // Check maintenance tasks
    const incidentTaskMap = new Map<string, any>();
    tasks.forEach(t => {
      incidentTaskMap.set(t.incident_id, t);
    });

    const inMaintenanceCount = activeIncidents.filter(i => {
      const t = incidentTaskMap.get(i.id);
      return t && t.status !== 'RESOLVED' && t.status !== 'REJECTED';
    }).length;

    // 4. Route Aggregates
    const routeStats = new Map<string, any>();
    activeIncidents.forEach(i => {
      let route = 'Unknown Route';
      if (i.metadata?.route_name) route = i.metadata.route_name;
      else if (i.video_id) route = missionMap.get(i.video_id) || 'Unknown Route';
      else if (i.source_mission_id) route = missionMap.get(i.source_mission_id || '') || 'Unknown Route';
      
      const key = route;
      
      if (!routeStats.has(key)) {
        routeStats.set(key, {
          route_name: route,
          total: 0,
          potholes: 0,
          waterlogging: 0,
          highPriority: 0,
          inMaintenance: 0,
          resolved: 0, // This is just for open incidents technically, but let's calculate
          latestTimestamp: i.timestamp || (i.created_at ? new Date(i.created_at).getTime() / 1000 : 0)
        });
      }
      
      const stats = routeStats.get(key);
      stats.total++;
      if (i.type === 'pothole' || (i as any).incident_type === 'pothole') stats.potholes++;
      if (i.type === 'waterlogging' || (i as any).incident_type === 'waterlogging') stats.waterlogging++;
      if (i.severity === 'CRITICAL' || i.severity === 'HIGH') stats.highPriority++;
      
      const t = incidentTaskMap.get(i.id);
      if (t && t.status !== 'RESOLVED' && t.status !== 'REJECTED') stats.inMaintenance++;

      const iTime = i.timestamp || (i.created_at ? new Date(i.created_at).getTime() / 1000 : 0);
      if (iTime > stats.latestTimestamp) {
        stats.latestTimestamp = iTime;
      }
    });

    const routeAggregates = Array.from(routeStats.values()).sort((a, b) => b.highPriority - a.highPriority || b.total - a.total);

    // 5. Attention Queue
    const attentionQueue = activeIncidents
      .filter(i => i.severity === 'CRITICAL' || i.severity === 'HIGH')
      .map(i => ({ ...i, maintenance: incidentTaskMap.get(i.id) }))
      .sort((a, b) => {
        const aTime = a.timestamp || (a.created_at ? new Date(a.created_at).getTime() / 1000 : 0);
        const bTime = b.timestamp || (b.created_at ? new Date(b.created_at).getTime() / 1000 : 0);
        return bTime - aTime;
      });

    return {
      missionMap,
      activeIncidents,
      highPriorityCount,
      inMaintenanceCount,
      routeAggregates,
      attentionQueue
    };
  }, [incidents, tasks, missions, selectedRoute]);

  const handleRowClick = (incident: any) => {
    // If it has a maintenance action mapped in tasks, attach it so the drawer displays the status correctly
    const task = tasks.find(t => t.incident_id === incident.id);
    setSelectedIncident({ ...incident, action: task });
  };

  const formatVideoTime = (time: number) => {
    const mins = Math.floor(time / 60).toString().padStart(2, '0');
    const secs = (time % 60).toFixed(2).padStart(5, '0');
    return `${mins}:${secs}`;
  };

  return (
    <div className="page-content pb-10">
      <PageHeader
        title="Road Intelligence"
        icon={MapPin}
        description="Monitor road-condition observations and maintenance priorities across monitored routes."
        actions={
          <select
            value={selectedRoute}
            onChange={e => setSelectedRoute(e.target.value)}
            className="h-8 bg-card border border-input text-foreground text-sm rounded px-3 focus:outline-none focus:ring-2 focus:ring-ring"
            aria-label="Filter by Route"
          >
            <option value="all">All Routes</option>
            {Array.from(new Set(missions.map(m => m.route_name).filter(Boolean))).map(rName => (
                <option key={rName} value={rName}>
                  {rName}
                </option>
            ))}
          </select>
        }
      />

      {isLoading ? (
        <div className="flex flex-col items-center justify-center p-12 bg-card border border-border rounded-lg text-center min-h-[400px]">
          <Loader2 className="w-8 h-8 animate-spin text-muted-foreground mb-4" />
          <p className="text-sm font-bold text-muted-foreground uppercase tracking-widest">
            Loading road intelligence...
          </p>
        </div>
      ) : activeIncidents.length === 0 ? (
        <div className="flex flex-col items-center justify-center p-12 bg-card border border-border rounded-lg text-center min-h-[400px]">
          <MapPin className="h-10 w-10 text-muted-foreground mb-4 opacity-50" />
          <p className="text-sm font-bold text-muted-foreground uppercase tracking-widest">
            No road-condition observations available.
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          
          {/* OPERATIONAL SUMMARY */}
          <div className="grid grid-cols-3 gap-4 mb-2">
            <div className="bg-card border border-border rounded-xl p-4 flex items-center justify-between shadow-sm">
              <div>
                <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Active Issues</p>
                <p className="text-3xl font-black mt-1">{activeIncidents.length}</p>
              </div>
              <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                <MapPin className="w-5 h-5 text-primary" />
              </div>
            </div>
            <div className="bg-card border border-border rounded-xl p-4 flex items-center justify-between shadow-sm">
              <div>
                <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">High Priority Needs</p>
                <p className="text-3xl font-black mt-1 text-red-500">
                  {highPriorityCount}
                </p>
              </div>
              <div className="w-10 h-10 rounded-full bg-red-500/10 flex items-center justify-center">
                <AlertTriangle className="w-5 h-5 text-red-500" />
              </div>
            </div>
            <div className="bg-card border border-border rounded-xl p-4 flex items-center justify-between shadow-sm">
              <div>
                <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">In Maintenance</p>
                <p className="text-3xl font-black mt-1 text-blue-500">
                  {inMaintenanceCount}
                </p>
              </div>
              <div className="w-10 h-10 rounded-full bg-blue-500/10 flex items-center justify-center">
                <Hammer className="w-5 h-5 text-blue-500" />
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
            
            {/* ROAD / ROUTE CONDITION TABLE */}
            <div className="bg-card border border-border rounded-lg overflow-hidden xl:col-span-2 flex flex-col">
              <div className="px-4 py-3 border-b border-border bg-secondary/50 flex items-center gap-2">
                <Navigation className="w-4 h-4 text-primary" />
                <h2 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Route Condition Summary</h2>
              </div>
              
              <div className="overflow-x-auto w-full flex-1">
                <table className="w-full text-sm text-left whitespace-nowrap">
                  <thead className="text-[10px] font-semibold uppercase bg-background text-muted-foreground border-b border-border">
                    <tr>
                      <th className="px-4 py-2">Route / Segment</th>
                      <th className="px-4 py-2 text-center">Total Issues</th>
                      <th className="px-4 py-2 text-center">High Priority</th>
                      <th className="px-4 py-2 text-center">Potholes</th>
                      <th className="px-4 py-2 text-center">In Maintenance</th>
                      <th className="px-4 py-2 text-center">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/50">
                    {routeAggregates.map((route, i) => (
                      <tr key={i} className="hover:bg-secondary/20 transition-colors">
                        <td className="px-4 py-3 font-medium flex items-center gap-2">
                          <MapPin className="w-3 h-3 text-muted-foreground" />
                          {route.route_name}
                        </td>
                        <td className="px-4 py-3 text-center font-mono font-bold text-foreground">
                          {route.total}
                        </td>
                        <td className="px-4 py-3 text-center font-mono font-bold text-red-500">
                          {route.highPriority}
                        </td>
                        <td className="px-4 py-3 text-center font-mono text-muted-foreground">
                          {route.potholes}
                        </td>
                        <td className="px-4 py-3 text-center font-mono text-blue-500">
                          {route.inMaintenance}
                        </td>
                        <td className="px-4 py-3 text-center">
                          {route.highPriority > 0 ? (
                            <span className="inline-flex items-center rounded-full bg-red-500/10 px-2 py-0.5 text-[10px] font-bold text-red-500 border border-red-500/20">
                              ATTENTION
                            </span>
                          ) : (
                            <span className="inline-flex items-center rounded-full bg-yellow-500/10 px-2 py-0.5 text-[10px] font-bold text-yellow-500 border border-yellow-500/20">
                              ACTIVE
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* PRIORITY / ATTENTION QUEUE */}
            <div className="bg-card border border-border rounded-lg overflow-hidden flex flex-col">
              <div className="px-4 py-3 border-b border-border bg-secondary/50 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-red-500" />
                <h2 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Attention Queue</h2>
              </div>
              <div className="p-0 flex-1 overflow-y-auto max-h-[400px]">
                {attentionQueue.length > 0 ? (
                  <div className="divide-y divide-border/50">
                    {attentionQueue.map((incident, i) => {
                      const routeName = incident.route_name || incident.metadata?.route_name || missionMap.get(incident.video_id) || missionMap.get(incident.source_mission_id || '') || 'Unknown Route';
                      
                      return (
                        <div 
                          key={i} 
                          className="p-3 hover:bg-secondary/20 cursor-pointer transition-colors group"
                          onClick={() => handleRowClick(incident)}
                        >
                          <div className="flex justify-between items-start mb-1">
                            <span className="font-semibold text-xs capitalize">
                              {(incident.type || (incident as any).incident_type || '').replace('_', ' ')}
                            </span>
                            <StatusBadge status={incident.severity} type="severity" />
                          </div>
                          
                          <div className="flex items-center gap-1 text-[11px] text-muted-foreground mb-2">
                            <MapPin className="w-3 h-3 opacity-70" />
                            <span className="truncate max-w-[180px]">{routeName}</span>
                          </div>
                          
                          <div className="flex justify-between items-end">
                            <div className="flex flex-col">
                              {incident.timestamp ? (
                                <>
                                  <span className="font-mono text-[10px] text-foreground">
                                    {formatVideoTime(incident.timestamp)}
                                  </span>
                                  <span className="text-[9px] opacity-70">Video Time</span>
                                </>
                              ) : (
                                <>
                                  <span className="text-[10px] text-foreground">
                                    {formatDistanceToNow(new Date(incident.created_at), { addSuffix: true })}
                                  </span>
                                  <span className="text-[9px] opacity-70">Logged</span>
                                </>
                              )}
                            </div>
                            
                            <div>
                              {incident.maintenance ? (
                                <span className="text-[10px] font-bold text-blue-500">
                                  {incident.maintenance.status.replace('_', ' ')}
                                </span>
                              ) : (
                                <span className="text-[10px] font-medium text-muted-foreground italic">
                                  Unassigned
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="p-8 text-center text-xs text-muted-foreground uppercase tracking-widest font-bold">
                    No critical issues pending
                  </div>
                )}
              </div>
            </div>
            
          </div>
        </div>
      )}

      {selectedIncident && (
        <IncidentDrawer
          incident={selectedIncident}
          onClose={() => setSelectedIncident(null)}
        />
      )}
    </div>
  );
}
