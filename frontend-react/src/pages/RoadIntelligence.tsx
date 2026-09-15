import { MapPin, Droplets, AlertCircle, HardHat } from 'lucide-react';
import { useRealtimeIncidents } from '@/hooks/useRealtimeIncidents';
import { MetricCard } from '@/components/ui/MetricCard';
import { EmptyState } from '@/components/ui/EmptyState';
import { PageHeader } from '@/components/ui/PageHeader';

export function RoadIntelligence() {
  const { data } = useRealtimeIncidents();
  const incidents = data?.incidents || [];

  const potholes = incidents.filter((i: any) => i.incident_type === 'pothole' || i.type === 'pothole');
  const waterlogging = incidents.filter((i: any) => i.incident_type === 'waterlogging' || i.type === 'waterlogging');
  const critical = incidents.filter((i: any) =>
    i.severity === 'CRITICAL' &&
    (['pothole', 'waterlogging'].includes(i.incident_type || i.type || ''))
  );

  return (
    <div className="page-content">
      <PageHeader
        title="Road Intelligence"
        icon={MapPin}
        description="Monitor pavement health, pothole events, and waterlogging across surveyed road segments."
      />

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Total Potholes"
          value={potholes.length}
          icon={AlertCircle}
          variant={potholes.length > 0 ? 'warning' : 'default'}
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
          variant={critical.length > 0 ? 'critical' : 'default'}
          description="Immediate attention required"
        />
        <MetricCard
          title="Segments Surveyed"
          value="—"
          icon={MapPin}
          description="Requires geospatial segment data"
        />
      </div>

      <div className="flex-1 min-h-[300px] panel flex items-center justify-center">
        <EmptyState
          icon={MapPin}
          title="Road Segment Data Unavailable"
          description="Aggregation of incidents into road segments (e.g. NH-44, Ring Road) requires geospatial bounding data which is not yet seeded in the database."
        />
      </div>
    </div>
  );
}
