import { Navigation, Car, Users, AlertTriangle } from 'lucide-react';
import { useRealtimeIncidents } from '@/hooks/useRealtimeIncidents';
import { MetricCard } from '@/components/ui/MetricCard';
import { EmptyState } from '@/components/ui/EmptyState';

export function TrafficIntelligence() {
  const { data } = useRealtimeIncidents();
  const incidents = data?.incidents || [];

  // Assuming no_helmet and helmet represent two wheeler traffic tracking metrics in this domain
  const noHelmet = incidents.filter(i => i.type === 'no_helmet');

  return (
    <div className="space-y-6 flex flex-col h-full">
      <div>
        <h1 className="text-2xl font-bold">Traffic Intelligence</h1>
        <p className="text-muted-foreground">Monitor traffic flow, congestion, and compliance.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <MetricCard 
          title="Vehicle Flow Count" 
          value="—" 
          icon={Car} 
          description="Vehicle tracking table not synced" 
        />
        <MetricCard 
          title="Avg Speed (km/h)" 
          value="—" 
          icon={Navigation} 
          description="No speed tracking data" 
        />
        <MetricCard 
          title="Helmet Violations" 
          value={noHelmet.length} 
          icon={Users} 
          description="Two-wheeler compliance issues" 
        />
        <MetricCard 
          title="Congestion Zones" 
          value="—" 
          icon={AlertTriangle} 
          description="Awaiting density analytics" 
        />
      </div>

      <div className="flex-1 min-h-[400px]">
        <EmptyState 
          icon={Navigation}
          title="Traffic Heatmap Unavailable"
          description="Real-time traffic density and speed heatmap requires the 'traffic_windows' table data to be populated by the backend."
        />
      </div>
    </div>
  );
}
