import { Bus, Clock, AlertTriangle, Search, Filter, Activity } from 'lucide-react';
import { MetricCard } from '@/components/ui/MetricCard';
import { EmptyState } from '@/components/ui/EmptyState';
import { useQuery } from '@tanstack/react-query';
import { fleetApi } from '@/api/fleet';
import { Skeleton } from '@/components/ui/Skeleton';

export function Fleet() {
  const { data: buses, isLoading } = useQuery({
    queryKey: ['fleet'],
    queryFn: fleetApi.getBuses
  });

  const totalBuses = buses?.length || 0;
  const onlineBuses = buses?.filter(b => b.status === 'ONLINE').length || 0;
  const warningBuses = buses?.filter(b => b.status === 'WARNING').length || 0;
  const offlineBuses = buses?.filter(b => b.status === 'OFFLINE' || b.status === 'MAINTENANCE').length || 0;

  return (
    <div className="space-y-6 flex flex-col h-full">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-2xl font-bold">Fleet Operations</h1>
          <p className="text-muted-foreground">Track public transit vehicles and monitor route adherence.</p>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard title="Total Buses" value={isLoading ? "—" : totalBuses} icon={Bus} description="Registered in network" />
        <MetricCard title="Online" value={isLoading ? "—" : onlineBuses} icon={Activity} description="Active telemetry" />
        <MetricCard title="Warning" value={isLoading ? "—" : warningBuses} icon={AlertTriangle} description="Deviations/delays" />
        <MetricCard title="Offline" value={isLoading ? "—" : offlineBuses} icon={Clock} description="Maintenance or parked" />
      </div>

      <div className="bg-card border border-border rounded-lg p-3 flex flex-wrap gap-3 items-center">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input 
            type="text" 
            disabled
            placeholder="Search bus ID or route..." 
            className="w-full bg-secondary/50 border border-border rounded-md pl-9 pr-3 py-1.5 text-sm cursor-not-allowed text-muted-foreground"
          />
        </div>
        <button disabled className="p-1.5 bg-secondary text-muted-foreground rounded-md opacity-50 cursor-not-allowed">
          <Filter className="h-4 w-4" />
        </button>
      </div>

      <div className="flex-1 bg-card border border-border rounded-lg overflow-hidden flex flex-col">
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left whitespace-nowrap">
            <thead className="text-[11px] font-semibold uppercase bg-secondary/50 text-muted-foreground border-b border-border">
              <tr>
                <th className="px-4 py-3">Bus ID</th>
                <th className="px-4 py-3">Route</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Speed</th>
                <th className="px-4 py-3">GPS Location</th>
                <th className="px-4 py-3">Last Seen</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={7} className="p-4">
                    <div className="space-y-2">
                      <Skeleton className="h-10 w-full" />
                      <Skeleton className="h-10 w-full" />
                      <Skeleton className="h-10 w-full" />
                    </div>
                  </td>
                </tr>
              ) : !buses || buses.length === 0 ? (
                <tr>
                  <td colSpan={7} className="p-0">
                    <EmptyState 
                      icon={Bus}
                      title="Fleet Telemetry Offline"
                      description="No live buses or fleet telemetry data is currently being streamed from the backend API."
                      className="border-none bg-transparent my-8"
                    />
                  </td>
                </tr>
              ) : (
                buses.map(bus => (
                  <tr key={bus.id} className="border-b border-border/50 hover:bg-muted/20 transition-colors">
                    <td className="px-4 py-3 font-medium">{bus.fleet_number}</td>
                    <td className="px-4 py-3">{bus.route_id || '—'}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                        bus.status === 'ONLINE' ? 'bg-green-500/10 text-green-500' :
                        bus.status === 'WARNING' ? 'bg-amber-500/10 text-amber-500' :
                        'bg-gray-500/10 text-gray-500'
                      }`}>
                        {bus.status}
                      </span>
                    </td>
                    <td className="px-4 py-3">{bus.latest_telemetry?.speed ? `${bus.latest_telemetry.speed} km/h` : '—'}</td>
                    <td className="px-4 py-3 font-mono text-xs">
                      {bus.latest_telemetry 
                        ? `${bus.latest_telemetry.latitude.toFixed(4)}, ${bus.latest_telemetry.longitude.toFixed(4)}`
                        : 'NO DATA'}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {bus.latest_telemetry?.timestamp 
                        ? new Date(bus.latest_telemetry.timestamp).toLocaleTimeString() 
                        : '—'}
                    </td>
                    <td className="px-4 py-3 text-right text-muted-foreground text-xs">
                      <button className="hover:text-primary transition-colors">Details</button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
