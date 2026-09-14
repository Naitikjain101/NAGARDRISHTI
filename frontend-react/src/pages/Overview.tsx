import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { 
  AlertOctagon, Activity, MapPin, AlertTriangle, 
  Droplets, Bus, ActivitySquare, ServerCrash 
} from 'lucide-react';
import { useRealtimeIncidents } from '@/hooks/useRealtimeIncidents';
import { useQuery } from '@tanstack/react-query';
import { aiApi } from '@/api/ai';
import { MapView } from '@/components/map/MapView';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { formatDistanceToNow } from 'date-fns';

export function Overview() {
  const { data: incidentsData, isLoading: incidentsLoading } = useRealtimeIncidents();
  const incidents = incidentsData?.incidents || [];
  
  const { data: systemStatus } = useQuery({
    queryKey: ['systemStatus'],
    queryFn: aiApi.getSystemStatus,
    refetchInterval: 10000,
  });

  const [currentTime, setCurrentTime] = useState(new Date());
  
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const criticalIncidents = incidents.filter(i => i.severity === 'CRITICAL');
  const potholes = incidents.filter(i => i.type === 'pothole');
  const waterlogging = incidents.filter(i => i.type === 'waterlogging');
  
  const { data: busData } = useQuery({
    queryKey: ['mapBuses'],
    queryFn: async () => {
      const res = await fetch('/api/map/buses');
      if (!res.ok) return { buses: [] };
      return res.json();
    },
    refetchInterval: 5000,
  });
  const activeBuses = busData?.buses?.length ?? 0;

  // Data Freshness
  const latestIncident = incidents.length > 0 ? incidents[0] : null;
  const lastUpdate = latestIncident ? new Date(latestIncident.created_at) : null;
  
  // Simple KPI Card component for the top row
  const KpiCard = ({ title, value, icon: Icon, alert = false }: any) => (
    <div className={`bg-card border ${alert ? 'border-red-500/50 shadow-[0_0_10px_rgba(239,68,68,0.1)]' : 'border-border'} rounded-lg p-4 flex items-center gap-4`}>
      <div className={`p-3 rounded-lg ${alert ? 'bg-red-500/10' : 'bg-secondary'}`}>
        <Icon className={`h-5 w-5 ${alert ? 'text-red-500' : 'text-primary'}`} />
      </div>
      <div>
        <p className="text-xs text-muted-foreground uppercase tracking-wider font-semibold">{title}</p>
        <p className="text-2xl font-bold leading-tight">{value}</p>
      </div>
    </div>
  );

  return (
    <div className="flex flex-col h-full space-y-4">
      
      {/* HEADER SECTION */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-4 pb-2 border-b border-border/50">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Urban Watch Command Center</h1>
          <div className="flex items-center gap-4 mt-1">
            <span className="flex items-center gap-1.5 text-xs font-medium">
              <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              LIVE SYSTEM AWARENESS
            </span>
            <span className="text-xs text-muted-foreground font-mono">
              {currentTime.toLocaleTimeString()}
            </span>
            <span className="text-xs text-muted-foreground">
              Last data update: {lastUpdate ? formatDistanceToNow(lastUpdate, { addSuffix: true }) : 'Waiting...'}
            </span>
          </div>
        </div>
        <div className="flex gap-2">
           <StatusBadge status={systemStatus?.status === 'ok' ? 'ONLINE' : 'ERROR'} type="connectivity" />
           <StatusBadge status={incidentsLoading ? 'CONNECTING' : 'LIVE'} type="connectivity" />
        </div>
      </div>

      {/* KPI ROW */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <KpiCard title="Active Events" value={incidents.length} icon={ActivitySquare} />
        <KpiCard title="Critical" value={criticalIncidents.length} icon={AlertOctagon} alert={criticalIncidents.length > 0} />
        <KpiCard title="Waterlogging" value={waterlogging.length} icon={Droplets} />
        <KpiCard title="Potholes" value={potholes.length} icon={AlertTriangle} />
        <KpiCard title="Active Buses" value={activeBuses} icon={Bus} />
        <KpiCard title="AI Health" value={systemStatus?.status === 'ok' ? 'OK' : 'ERR'} icon={ServerCrash} alert={systemStatus?.status !== 'ok'} />
      </div>

      {/* MAIN SPLIT VIEW */}
      <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-3 gap-4">
        
        {/* LEFT: LIVE MAP (2/3 width) */}
        <div className="lg:col-span-2 bg-card border border-border rounded-lg overflow-hidden flex flex-col relative">
          <div className="absolute top-4 left-4 z-[1000] bg-background/90 backdrop-blur text-xs font-semibold px-3 py-1.5 rounded-md border border-border shadow-sm flex items-center gap-2">
             <MapPin className="h-3 w-3 text-primary" /> Live Urban Map
          </div>
          <div className="flex-1 w-full h-full">
            <MapView 
              incidents={incidents as unknown as any[]}
              onIncidentClick={() => {}} // We'll link this to global drawer or detailed view later
            />
          </div>
        </div>

        {/* RIGHT: CRITICAL INCIDENTS (1/3 width) */}
        <div className="bg-card border border-border rounded-lg flex flex-col overflow-hidden">
          <div className="p-4 border-b border-border bg-secondary/30 flex justify-between items-center">
            <h3 className="font-semibold flex items-center gap-2">
              <AlertOctagon className="h-4 w-4 text-red-500" />
              Critical Attention Required
            </h3>
            <span className="text-xs bg-red-500/20 text-red-500 px-2 py-0.5 rounded-full font-bold">{criticalIncidents.length}</span>
          </div>
          
          <div className="flex-1 overflow-y-auto p-2 space-y-2">
            {criticalIncidents.length === 0 ? (
               <div className="h-full flex flex-col items-center justify-center text-muted-foreground p-6 text-center">
                 <div className="w-10 h-10 rounded-full bg-secondary flex items-center justify-center mb-3">
                   <Activity className="h-5 w-5" />
                 </div>
                 <p className="text-sm font-medium">No Critical Incidents</p>
                 <p className="text-xs mt-1">The urban network is currently clear of severe hazards.</p>
               </div>
            ) : (
              criticalIncidents.map(incident => (
                <div key={incident.id} className="p-3 bg-background border border-border rounded-lg hover:border-red-500/50 transition-colors cursor-pointer group">
                  <div className="flex justify-between items-start mb-2">
                    <div className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-red-500"></span>
                      <span className="font-semibold text-sm capitalize">{incident.type.replace('_', ' ')}</span>
                    </div>
                    <span className="text-[10px] text-muted-foreground font-mono">{formatDistanceToNow(new Date(incident.created_at))} ago</span>
                  </div>
                  <div className="text-xs text-muted-foreground flex justify-between items-end">
                    <span>Conf: {Math.round(incident.confidence * 100)}%</span>
                    <Link to="/incidents" className="text-primary hover:underline opacity-0 group-hover:opacity-100 transition-opacity">View Details &rarr;</Link>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

    </div>
  );
}
