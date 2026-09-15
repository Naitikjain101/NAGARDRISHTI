import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertTriangle, Bus, LayoutDashboard, ArrowRight, Activity, MapPin
} from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { useMapIntelligence } from '@/hooks/useMapIntelligence';
import { maintenanceApi } from '@/api/maintenance';
import { MapView } from '@/components/map/MapView';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { PageHeader } from '@/components/ui/PageHeader';
import { IncidentDrawer } from '@/components/incidents/IncidentDrawer';
import { formatDistanceToNow } from 'date-fns';
import { formatVideoTimestamp } from '@/utils/time';

export function CommandCenter() {
  const { incidents, buses, isLoading: mapLoading } = useMapIntelligence();
  
  const { isLoading: trafficLoading } = useQuery({
    queryKey: ['traffic_history'],
    queryFn: async () => {
      const res = await fetch('/api/traffic/history?limit=10');
      if (!res.ok) return { windows: [] };
      return res.json();
    },
    refetchInterval: 10000,
  });

  const { data: missionsData, isLoading: missionsLoading } = useQuery({
    queryKey: ['missions'],
    queryFn: async () => {
      const res = await fetch('/api/missions/');
      if (!res.ok) return { missions: [] };
      return res.json();
    },
    refetchInterval: 10000,
  });

  const { isLoading: tasksLoading } = useQuery({
    queryKey: ['maintenance'],
    queryFn: maintenanceApi.getTasks,
    refetchInterval: 10000,
  });

  const [selectedIncident, setSelectedIncident] = useState<any | null>(null);

  const activeIncidents = incidents.filter(i => i.status !== 'suppressed' && i.status !== 'rejected');
  const highPriorityIncidents = activeIncidents.filter(i => i.severity === 'CRITICAL' || i.severity === 'HIGH');
  
  const activeMissions = (missionsData?.missions || []).filter((m: any) => m.status === 'RUNNING' || m.status === 'READY');
  
  const getAttentionQueue = () => {
    return highPriorityIncidents
      .sort((a, b) => {
        const aDate = a.first_seen_at || a.created_at;
        const bDate = b.first_seen_at || b.created_at;
        const aTime = aDate ? new Date(aDate).getTime() : 0;
        const bTime = bDate ? new Date(bDate).getTime() : 0;
        return bTime - aTime;
      })
      .slice(0, 10);
  };

  const attentionQueue = getAttentionQueue();
  const isOnline = !mapLoading && !trafficLoading && !missionsLoading && !tasksLoading;

  return (
    <div className="page-content pb-10">
      <PageHeader
        title="Command Center"
        icon={LayoutDashboard}
        description="Municipal mobility and road-condition operations overview."
        actions={
          <div className="flex items-center gap-2">
            <StatusBadge status={isOnline ? 'ONLINE' : 'CONNECTING'} type="connectivity" />
          </div>
        }
      />

      {/* OPERATIONAL SUMMARY */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-4 shrink-0">
        <div className="bg-card border border-border rounded-lg p-3 flex items-center justify-between shadow-sm cursor-pointer hover:border-primary/50 transition-colors" onClick={() => window.location.hash = '#/incidents'}>
          <div>
            <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Active Events</p>
            <p className="text-2xl font-black mt-1">{activeIncidents.length}</p>
          </div>
          <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
            <Activity className="w-4 h-4 text-primary" />
          </div>
        </div>
        
        <div className="bg-card border border-border rounded-lg p-3 flex items-center justify-between shadow-sm cursor-pointer hover:border-red-500/50 transition-colors" onClick={() => window.location.hash = '#/road-intelligence'}>
          <div>
            <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Critical Priority</p>
            <p className="text-2xl font-black mt-1 text-red-500">{highPriorityIncidents.length}</p>
          </div>
          <div className="w-8 h-8 rounded-full bg-red-500/10 flex items-center justify-center">
            <AlertTriangle className="w-4 h-4 text-red-500" />
          </div>
        </div>

        <div className="bg-card border border-border rounded-lg p-3 flex items-center justify-between shadow-sm cursor-pointer hover:border-cyan-500/50 transition-colors" onClick={() => window.location.hash = '#/incidents'}>
          <div>
            <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Waterlogging</p>
            <p className="text-2xl font-black mt-1 text-cyan-500">{activeIncidents.filter(i => i.incident_type === 'waterlogging').length}</p>
          </div>
          <div className="w-8 h-8 rounded-full bg-cyan-500/10 flex items-center justify-center">
            <Activity className="w-4 h-4 text-cyan-500" />
          </div>
        </div>

        <div className="bg-card border border-border rounded-lg p-3 flex items-center justify-between shadow-sm cursor-pointer hover:border-orange-500/50 transition-colors" onClick={() => window.location.hash = '#/incidents'}>
          <div>
            <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Potholes</p>
            <p className="text-2xl font-black mt-1 text-orange-500">{activeIncidents.filter(i => i.incident_type === 'pothole').length}</p>
          </div>
          <div className="w-8 h-8 rounded-full bg-orange-500/10 flex items-center justify-center">
            <Activity className="w-4 h-4 text-orange-500" />
          </div>
        </div>

        <div className="bg-card border border-border rounded-lg p-3 flex items-center justify-between shadow-sm cursor-pointer hover:border-emerald-500/50 transition-colors" onClick={() => window.location.hash = '#/monitoring'}>
          <div>
            <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Active Vehicles</p>
            <p className="text-2xl font-black mt-1 text-emerald-500">{activeMissions.length}</p>
          </div>
          <div className="w-8 h-8 rounded-full bg-emerald-500/10 flex items-center justify-center">
            <Bus className="w-4 h-4 text-emerald-500" />
          </div>
        </div>
      </div>

      {/* PRIMARY MAP & ATTENTION QUEUE */}
      <div className="flex-1 min-h-[550px] flex gap-4">
        {/* Full screen Map */}
        <div className="flex-1 bg-card border border-border rounded-xl overflow-hidden flex flex-col shadow-card relative">
          <div className="flex items-center justify-between px-4 py-2.5 border-b border-border shrink-0 bg-secondary/50">
            <div className="flex items-center gap-2">
              <MapPin className="w-3.5 h-3.5 text-primary" />
              <h2 className="text-xs font-bold text-foreground uppercase tracking-wide">Live Operations Map</h2>
            </div>
          </div>
          <div className="flex-1 relative z-0">
            <MapView
              incidents={incidents}
              buses={buses}
              onIncidentClick={setSelectedIncident}
            />
          </div>
        </div>

        {/* Compact Requires Attention Panel */}
        {attentionQueue.length > 0 && (
          <div className="w-72 bg-card border border-border rounded-xl flex flex-col overflow-hidden shadow-card shrink-0">
            <div className="px-4 py-2.5 border-b border-border shrink-0 flex items-center justify-between bg-secondary/50">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-3.5 w-3.5 text-red-500" />
                <h2 className="text-[10px] font-bold text-foreground uppercase tracking-wide">Requires Attention</h2>
              </div>
              <span className="text-[9px] font-bold px-1.5 py-0.5 bg-red-100 text-red-700 rounded-full border border-red-200">
                {highPriorityIncidents.length}
              </span>
            </div>
            
            <div className="flex-1 overflow-y-auto p-0">
              <div className="divide-y divide-border/50">
                {attentionQueue.map((incident: any) => {
                  return (
                    <div 
                      key={incident.id} 
                      className="p-3 hover:bg-secondary/20 cursor-pointer transition-colors group"
                      onClick={() => setSelectedIncident(incident)}
                    >
                      <div className="flex justify-between items-start mb-1">
                        <span className="font-semibold text-[11px] capitalize text-foreground">
                          {(incident.type || incident.incident_type || '').replace('_', ' ')}
                        </span>
                        <StatusBadge status={incident.severity} type="severity" />
                      </div>
                      <div className="flex justify-between items-end">
                        <div className="flex flex-col">
                          {incident.timestamp !== undefined && incident.timestamp !== null ? (
                            <>
                              <span className="font-mono text-[10px] text-foreground">
                                {formatVideoTimestamp(incident.timestamp)}
                              </span>
                            </>
                          ) : (
                            <>
                              <span className="text-[9px] text-foreground">
                                {formatDistanceToNow(new Date(incident.first_seen_at || incident.created_at), { addSuffix: true })}
                              </span>
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
            <div className="p-2 border-t border-border shrink-0 bg-secondary/20">
              <Link
                to="/incidents"
                className="flex items-center justify-center gap-2 w-full py-1 text-[10px] font-bold text-primary hover:bg-primary/10 rounded transition-colors"
              >
                VIEW ALL <ArrowRight className="h-3 w-3" />
              </Link>
            </div>
          </div>
        )}
      </div>

      <IncidentDrawer 
        incident={selectedIncident} 
        onClose={() => setSelectedIncident(null)} 
      />
    </div>
  );
}
