import { MapPin, Droplets, AlertCircle, HardHat } from 'lucide-react';
import { useRealtimeIncidents } from '@/hooks/useRealtimeIncidents';
import { MetricCard } from '@/components/ui/MetricCard';
import { EmptyState } from '@/components/ui/EmptyState';

export function RoadIntelligence() {
  const { data } = useRealtimeIncidents();
  const incidents = data?.incidents || [];

  const potholes = incidents.filter(i => i.type === 'pothole');
  const waterlogging = incidents.filter(i => i.type === 'waterlogging');
  const critical = incidents.filter(i => i.severity === 'CRITICAL' && (i.type === 'pothole' || i.type === 'waterlogging'));

  return (
    <div className="space-y-6 flex flex-col h-full">
      <div>
        <h1 className="text-2xl font-bold">Road Intelligence</h1>
        <p className="text-muted-foreground">Monitor pavement health, potholes, and waterlogging events.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <MetricCard 
          title="Total Potholes" 
          value={potholes.length} 
          icon={AlertCircle} 
          description="Active unaddressed potholes" 
        />
        <MetricCard 
          title="Waterlogging Events" 
          value={waterlogging.length} 
          icon={Droplets} 
          description="Areas with standing water" 
        />
        <MetricCard 
          title="Critical Road Hazards" 
          value={critical.length} 
          icon={HardHat} 
          description="Immediate attention required" 
        />
        <MetricCard 
          title="Segments Surveyed" 
          value="—" 
          icon={MapPin} 
          description="No segment metadata available" 
        />
      </div>

      <div className="flex-1 min-h-[400px]">
        <EmptyState 
          icon={MapPin}
          title="Road Segments Data Unavailable"
          description="Aggregation of incidents into specific road segments (e.g. NH-44, Ring Road) requires geospatial bounding data which is currently not seeded in the database."
        />
      </div>
    </div>
  );
}
