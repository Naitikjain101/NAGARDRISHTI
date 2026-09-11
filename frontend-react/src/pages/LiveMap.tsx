import { useState } from 'react';
import { MapView } from '@/components/map/MapView';
import { useRealtimeIncidents } from '@/hooks/useRealtimeIncidents';
import { IncidentDrawer } from '@/components/incidents/IncidentDrawer';
import type { Incident } from '@/api/incidents';
import { Filter, Layers } from 'lucide-react';
import { cn } from '@/lib/utils';

export function LiveMap() {
  const [filterType, setFilterType] = useState<string>('all');
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);
  
  // Realtime hook auto-updates map data
  const { data, isLoading } = useRealtimeIncidents();
  const allIncidents = data?.incidents || [];

  const incidents = filterType === 'all' 
    ? allIncidents 
    : filterType === 'critical'
      ? allIncidents.filter(i => i.severity === 'CRITICAL')
      : allIncidents.filter(i => i.type === filterType);

  const FilterButton = ({ id, label, icon: Icon, count }: any) => (
    <button
      onClick={() => setFilterType(id)}
      className={cn(
        "w-full flex items-center justify-between p-3 rounded-md border transition-all text-sm font-medium",
        filterType === id 
          ? "bg-primary text-primary-foreground border-primary" 
          : "bg-background border-border hover:border-primary/50 text-muted-foreground hover:text-foreground"
      )}
    >
      <div className="flex items-center gap-2">
        {Icon && <Icon className="h-4 w-4" />}
        {label}
      </div>
      <span className={cn("text-xs py-0.5 px-2 rounded-full", filterType === id ? "bg-primary-foreground/20 text-primary-foreground" : "bg-secondary text-foreground")}>
        {count}
      </span>
    </button>
  );

  return (
    <div className="flex flex-col h-full space-y-4">
      <div>
        <h1 className="text-2xl font-bold">Live Urban Map</h1>
        <p className="text-muted-foreground">Real-time spatial view of active incidents and fleet telemetry.</p>
      </div>
      
      <div className="flex-1 border border-border rounded-lg overflow-hidden flex flex-col md:flex-row relative bg-background">
        
        {/* Left Filter Sidebar */}
        <div className="w-full md:w-64 border-b md:border-b-0 md:border-r border-border bg-card p-4 flex flex-col gap-2 shrink-0 z-10">
          <h3 className="text-sm font-semibold mb-2 flex items-center gap-2 uppercase tracking-wider text-muted-foreground">
            <Filter className="h-4 w-4" /> Map Filters
          </h3>
          <FilterButton id="all" label="All Events" count={allIncidents.length} icon={Layers} />
          <FilterButton id="critical" label="Critical Hazards" count={allIncidents.filter(i => i.severity === 'CRITICAL').length} />
          <FilterButton id="waterlogging" label="Waterlogging" count={allIncidents.filter(i => i.type === 'waterlogging').length} />
          <FilterButton id="pothole" label="Potholes" count={allIncidents.filter(i => i.type === 'pothole').length} />
          <FilterButton id="bus" label="Fleet (Buses)" count={0} />
        </div>

        {/* Map Area */}
        <div className="flex-1 relative">
          {isLoading && (
            <div className="absolute inset-0 bg-background/50 backdrop-blur-sm z-50 flex items-center justify-center">
              <div className="px-4 py-2 bg-card border border-border rounded-full shadow-lg font-medium text-sm flex items-center gap-2">
                <div className="w-4 h-4 rounded-full border-2 border-primary border-t-transparent animate-spin" />
                Loading Spatial Data...
              </div>
            </div>
          )}
          
          <MapView 
            incidents={incidents}
            onIncidentClick={setSelectedIncident}
          />
        </div>

        {/* Global Incident Drawer triggered by map markers */}
        <IncidentDrawer 
          incident={selectedIncident} 
          onClose={() => setSelectedIncident(null)} 
        />
      </div>
    </div>
  );
}
