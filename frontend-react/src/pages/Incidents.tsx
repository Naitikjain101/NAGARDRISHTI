import { useState } from 'react';
import { useRealtimeIncidents } from '@/hooks/useRealtimeIncidents';
import { DataTable } from '@/components/incidents/DataTable';
import { IncidentDrawer } from '@/components/incidents/IncidentDrawer';
import type { Incident } from '@/api/incidents';
import { Search, Filter, Download } from 'lucide-react';
import { Skeleton } from '@/components/ui/Skeleton';

export function Incidents() {
  const { data, isLoading } = useRealtimeIncidents();
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);
  
  const incidents = data?.incidents || [];

  return (
    <div className="space-y-4 flex flex-col h-full">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-2xl font-bold">Incident Center</h1>
          <p className="text-muted-foreground">Manage, investigate, and assign urban infrastructure alerts.</p>
        </div>
        <button className="flex items-center gap-2 px-3 py-1.5 bg-secondary text-secondary-foreground rounded-md text-sm hover:bg-secondary/80 transition-colors">
          <Download className="h-4 w-4" /> Export CSV
        </button>
      </div>

      <div className="bg-card border border-border rounded-lg p-3 flex flex-wrap gap-3 items-center">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input 
            type="text" 
            placeholder="Search incident ID, location, or bus..." 
            className="w-full bg-background border border-border rounded-md pl-9 pr-3 py-1.5 text-sm focus:outline-none focus:border-primary"
          />
        </div>
        
        <select className="bg-background border border-border rounded-md px-3 py-1.5 text-sm focus:outline-none focus:border-primary">
          <option value="">All Severities</option>
          <option value="CRITICAL">Critical Only</option>
          <option value="HIGH">High & Above</option>
        </select>

        <select className="bg-background border border-border rounded-md px-3 py-1.5 text-sm focus:outline-none focus:border-primary">
          <option value="">All Types</option>
          <option value="waterlogging">Waterlogging</option>
          <option value="pothole">Potholes</option>
          <option value="no_helmet">Traffic Violations</option>
        </select>

        <select className="bg-background border border-border rounded-md px-3 py-1.5 text-sm focus:outline-none focus:border-primary">
          <option value="">All Statuses</option>
          <option value="active">Active (Unresolved)</option>
          <option value="resolved">Resolved</option>
        </select>

        <button className="p-1.5 bg-secondary text-muted-foreground rounded-md hover:text-foreground transition-colors">
          <Filter className="h-4 w-4" />
        </button>
      </div>

      <div className="flex-1 min-h-0">
        {isLoading ? (
          <div className="space-y-2">
            {[1, 2, 3, 4, 5, 6].map(i => (
              <Skeleton key={i} className="h-14 w-full rounded-lg" />
            ))}
          </div>
        ) : (
          <DataTable 
            incidents={incidents} 
            onRowClick={setSelectedIncident}
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
