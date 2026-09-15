import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertOctagon, Activity, AlertTriangle,
  Droplets, Bus, LayoutDashboard, ArrowRight
} from 'lucide-react';
import { useRealtimeIncidents } from '@/hooks/useRealtimeIncidents';
import { useQuery } from '@tanstack/react-query';
import { MapView } from '@/components/map/MapView';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { MetricCard } from '@/components/ui/MetricCard';
import { PageHeader } from '@/components/ui/PageHeader';
import { EmptyState } from '@/components/ui/EmptyState';
import { formatDistanceToNow } from 'date-fns';

export function Overview() {
  const { data: incidentsData, isLoading: incidentsLoading } = useRealtimeIncidents();
  const incidents = incidentsData?.incidents || [];

  const { data: systemStatus } = useQuery({
    queryKey: ['systemStatus'],
    queryFn: async () => {
      const res = await fetch('/api/system/status');
      if (!res.ok) return { status: 'error' };
      return res.json();
    },
    refetchInterval: 10000,
  });

  const [currentTime, setCurrentTime] = useState(new Date());
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const { data: busData } = useQuery({
    queryKey: ['mapBuses'],
    queryFn: async () => {
      const res = await fetch('/api/map/buses');
      if (!res.ok) return { buses: [] };
      return res.json();
    },
    refetchInterval: 5000,
  });

  const criticalIncidents = incidents.filter((i: any) => i.severity === 'CRITICAL');
  const potholes = incidents.filter((i: any) => i.incident_type === 'pothole' || i.type === 'pothole');
  const waterlogging = incidents.filter((i: any) => i.incident_type === 'waterlogging' || i.type === 'waterlogging');
  const activeBuses = busData?.buses?.length ?? 0;
  const isOnline = systemStatus?.status === 'ok';

  return (
    <div className="page-content">
      {/* Header */}
      <PageHeader
        title="Command Center"
        icon={LayoutDashboard}
        description="Real-time urban infrastructure monitoring across all active zones."
        badge={
          <span className="flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground">
            <span className={`w-1.5 h-1.5 rounded-full ${isOnline ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
            {isOnline ? 'Live' : 'Offline'} · {currentTime.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
          </span>
        }
        actions={
          <div className="flex items-center gap-2">
            <StatusBadge status={isOnline ? 'ONLINE' : 'ERROR'} type="connectivity" />
            <StatusBadge status={incidentsLoading ? 'CONNECTING' : 'LIVE'} type="connectivity" />
          </div>
        }
      />

      {/* KPI Row */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
        <MetricCard
          title="Active Events"
          value={incidents.length}
          icon={Activity}
          description="Open incident records"
        />
        <MetricCard
          title="Critical"
          value={criticalIncidents.length}
          icon={AlertOctagon}
          variant={criticalIncidents.length > 0 ? 'critical' : 'default'}
          description="Require immediate action"
        />
        <MetricCard
          title="Waterlogging"
          value={waterlogging.length}
          icon={Droplets}
          description="Standing water events"
        />
        <MetricCard
          title="Potholes"
          value={potholes.length}
          icon={AlertTriangle}
          description="Road surface defects"
        />
        <MetricCard
          title="Active Vehicles"
          value={activeBuses}
          icon={Bus}
          description="On-route survey units"
        />
      </div>

      {/* Main content — Map + Critical sidebar */}
      <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-3 gap-4">

        {/* Map — 2/3 width */}
        <div className="lg:col-span-2 bg-card border border-border rounded-lg overflow-hidden flex flex-col shadow-card relative">
          <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
              <span className="text-xs font-semibold text-foreground uppercase tracking-wide">Live Urban Map</span>
            </div>
            <Link
              to="/map"
              className="flex items-center gap-1 text-xs text-primary hover:text-primary/80 font-medium transition-colors"
            >
              Full Map <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
          <div className="flex-1 min-h-[350px]">
            <MapView
              incidents={incidents as unknown as any[]}
              onIncidentClick={() => {}}
            />
          </div>
        </div>

        {/* Critical incidents sidebar — 1/3 width */}
        <div className="bg-card border border-border rounded-lg flex flex-col overflow-hidden shadow-card">
          <div className="px-4 py-3 border-b border-border shrink-0 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertOctagon className="h-4 w-4 text-red-600" />
              <h2 className="text-xs font-semibold text-foreground uppercase tracking-wide">Critical Alerts</h2>
            </div>
            {criticalIncidents.length > 0 && (
              <span className="text-[10px] font-bold px-1.5 py-0.5 bg-red-100 text-red-700 rounded">
                {criticalIncidents.length}
              </span>
            )}
          </div>

          <div className="flex-1 overflow-y-auto p-3 space-y-2">
            {criticalIncidents.length === 0 ? (
              <EmptyState
                icon={Activity}
                title="No Critical Incidents"
                description="The urban network is clear of severe hazards."
                className="min-h-[200px]"
              />
            ) : (
              criticalIncidents.map((incident: any) => (
                <div
                  key={incident.id}
                  className="p-3 bg-background border border-border rounded-lg hover:border-red-200 hover:bg-red-50/30 transition-colors cursor-pointer group"
                >
                  <div className="flex items-start justify-between gap-2 mb-1.5">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="w-1.5 h-1.5 rounded-full bg-red-500 shrink-0 mt-0.5" />
                      <span className="text-sm font-semibold text-foreground capitalize truncate">
                        {(incident.incident_type || incident.type || '').replace('_', ' ')}
                      </span>
                    </div>
                    <span className="text-[10px] text-muted-foreground shrink-0">
                      {formatDistanceToNow(new Date(incident.created_at || incident.first_seen_at), { addSuffix: true })}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>Confidence: {Math.round((incident.confidence || 0) * 100)}%</span>
                    <Link
                      to="/incidents"
                      className="text-primary opacity-0 group-hover:opacity-100 transition-opacity text-xs font-medium"
                    >
                      View →
                    </Link>
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="p-3 border-t border-border shrink-0">
            <Link
              to="/incidents"
              className="flex items-center justify-center gap-2 w-full py-2 text-xs font-semibold text-primary border border-primary/20 rounded hover:bg-primary/5 transition-colors"
            >
              View All Incidents <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
