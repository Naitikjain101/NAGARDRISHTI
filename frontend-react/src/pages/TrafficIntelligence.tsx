import { useState, useEffect, useMemo } from 'react';
import { Navigation, Car, Activity, BarChart3, Bus, Truck, Bike } from 'lucide-react';
import { PageHeader } from '@/components/ui/PageHeader';

function densityColor(level: string) {
  const l = level?.toUpperCase();
  if (l === 'HIGH' || l === 'CRITICAL') return { bg: 'bg-red-100', text: 'text-red-700', bar: '#ef4444' };
  if (l === 'MEDIUM') return { bg: 'bg-amber-100', text: 'text-amber-700', bar: '#f97316' };
  return { bg: 'bg-green-100', text: 'text-green-700', bar: '#22c55e' };
}

function vehicleIcon(type: string) {
  const t = type.toLowerCase();
  if (t.includes('bus')) return Bus;
  if (t.includes('truck')) return Truck;
  if (t.includes('motorcycle') || t.includes('bicycle') || t.includes('bike')) return Bike;
  return Car;
}

export function TrafficIntelligence() {
  const [missions, setMissions] = useState<any[]>([]);
  const [selectedVideo, setSelectedVideo] = useState<string>('all');
  const [trafficWindows, setTrafficWindows] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetch('/api/missions/')
      .then(r => r.json())
      .then(data => setMissions(data.missions || []))
      .catch(console.error);
  }, []);

  useEffect(() => {
    setIsLoading(true);
    const url = selectedVideo !== 'all'
      ? `/api/traffic/history?video_id=${encodeURIComponent(selectedVideo)}`
      : `/api/traffic/history`;

    fetch(url)
      .then(r => r.json())
      .then(data => setTrafficWindows(data.windows || []))
      .catch(() => setTrafficWindows([]))
      .finally(() => setIsLoading(false));
  }, [selectedVideo]);

  const { currentConditions, composition, totalVehicles, peakWindow } = useMemo(() => {
    if (!trafficWindows || trafficWindows.length === 0) {
      return { currentConditions: [], composition: {}, totalVehicles: 0, peakWindow: null };
    }

    const missionMap = new Map(missions.map(m => {
      const meta = m.metadata || {};
      const vId = meta.video_id || m.video_filename;
      return [vId, m.route_name || 'Urban Route'];
    }));

    // Latest window per route_name for current conditions
    const latestPerRoute = new Map<string, any>();
    trafficWindows.forEach(w => {
      const vId = w.video_id || 'unknown';
      const routeName = missionMap.get(vId) || 'Urban Route';
      
      if (!latestPerRoute.has(routeName)) {
        latestPerRoute.set(routeName, w);
      } else {
        const existing = latestPerRoute.get(routeName);
        if (new Date(w.window_start).getTime() > new Date(existing.window_start).getTime()) {
          latestPerRoute.set(routeName, w);
        }
      }
    });

    const currentConditions = Array.from(latestPerRoute.entries()).map(([rName, w]) => ({
      ...w,
      route_name: rName
    }));

    // Aggregate vehicle composition across all windows
    const composition: Record<string, number> = {};
    trafficWindows.forEach(w => {
      const byClass = w.by_class || {};
      Object.entries(byClass).forEach(([cls, count]) => {
        composition[cls] = (composition[cls] || 0) + (count as number);
      });
    });

    const totalVehicles = Object.values(composition).reduce((a, b) => a + b, 0);

    const peakWindow = trafficWindows.reduce((best: any, w: any) =>
      (w.unique_vehicle_count || 0) > (best?.unique_vehicle_count || 0) ? w : best
    , null);

    return { currentConditions, composition, totalVehicles, peakWindow };
  }, [trafficWindows, missions]);

  const missionOptions = useMemo(() => {
    const seen = new Set<string>();
    return missions.filter(m => {
      const vId = m.metadata?.video_id || m.video_filename;
      if (!vId || seen.has(vId)) return false;
      seen.add(vId);
      return true;
    });
  }, [missions]);

  const avgVehicles = trafficWindows.length
    ? Math.round(trafficWindows.reduce((s: number, w: any) => s + (w.unique_vehicle_count || 0), 0) / trafficWindows.length)
    : 0;

  return (
    <div className="page-content overflow-y-auto custom-scrollbar pb-10">
      <PageHeader
        title="Traffic Intelligence"
        description="Analytical operational workspace for monitoring traffic density and vehicle distributions."
        icon={Activity}
        actions={
          <select
            value={selectedVideo}
            onChange={e => setSelectedVideo(e.target.value)}
            className="text-sm bg-card border border-border rounded-lg px-3 py-1.5 text-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
          >
            <option value="all">All Journeys</option>
            {missionOptions.map(m => {
              const vId = m.metadata?.video_id || m.video_filename;
              return <option key={vId} value={vId}>{m.route_name || vId}</option>;
            })}
          </select>
        }
      />

      {/* KPI Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Data Windows', value: trafficWindows.length, color: 'text-primary' },
          { label: 'Avg Vehicles / Window', value: avgVehicles, color: 'text-amber-500' },
          { label: 'Total Vehicles Tracked', value: totalVehicles, color: 'text-blue-500' },
          { label: 'Peak Count', value: peakWindow?.unique_vehicle_count || 0, color: 'text-red-500' },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-card border border-border rounded-xl p-4 shadow-sm">
            <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest mb-1">{label}</p>
            <p className={`text-3xl font-black ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      {/* Current Conditions */}
      <section className="space-y-3">
        <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
          <Activity className="w-4 h-4" /> Current Traffic Conditions
        </h3>

        {isLoading ? (
          <div className="h-24 rounded-lg bg-secondary/30 animate-pulse" />
        ) : currentConditions.length === 0 ? (
          <div className="bg-card border border-border rounded-xl p-8 text-center text-muted-foreground text-sm">
            No active conditions — run a video analysis to populate traffic data.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {currentConditions.map((c, i) => {
              const dc = densityColor(c.congestion_level || c.density_level || 'LOW');
              return (
                <div key={i} className="bg-card border border-border rounded-xl p-4 shadow-sm space-y-3">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="font-bold text-sm text-foreground">{c.route_name}</p>
                      <p className="text-[10px] text-muted-foreground font-mono mt-0.5">
                        {c.video_id ? `Video: ${c.video_id.split('-')[0]}...` : 'Live Feed'}
                      </p>
                    </div>
                    <span className={`text-[10px] font-black px-2 py-1 rounded-md uppercase tracking-wider ${dc.bg} ${dc.text}`}>
                      {(c.congestion_level || c.density_level || 'LOW').toUpperCase()}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div className="bg-secondary/30 rounded-lg p-2">
                      <p className="text-[9px] text-muted-foreground uppercase font-bold mb-0.5">Vehicles</p>
                      <p className="font-black text-lg">{c.unique_vehicle_count}</p>
                    </div>
                    <div className="bg-secondary/30 rounded-lg p-2">
                      <p className="text-[9px] text-muted-foreground uppercase font-bold mb-0.5">Congestion</p>
                      <p className="font-black text-lg">{c.congestion_score ?? 'N/A'}</p>
                    </div>
                  </div>
                  {c.by_class && Object.keys(c.by_class).length > 0 && (
                    <div className="space-y-1.5">
                      {Object.entries(c.by_class).map(([cls, cnt]) => {
                        const Icon = vehicleIcon(cls);
                        const pct = c.unique_vehicle_count > 0 ? Math.round(((cnt as number) / c.unique_vehicle_count) * 100) : 0;
                        return (
                          <div key={cls} className="flex items-center gap-2 text-xs">
                            <Icon className="w-3 h-3 text-muted-foreground shrink-0" />
                            <span className="w-20 capitalize text-muted-foreground">{cls.toLowerCase()}</span>
                            <div className="flex-1 bg-secondary/50 rounded h-1.5">
                              <div className="h-full rounded" style={{ width: `${pct}%`, background: dc.bar }} />
                            </div>
                            <span className="font-bold text-foreground w-6 text-right">{cnt as number}</span>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* Bottom analytics row */}
      {Object.keys(composition).length > 0 && (
        <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Fleet composition */}
          <div className="bg-card border border-border rounded-xl p-5 shadow-sm space-y-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
              <BarChart3 className="w-4 h-4" /> Fleet Vehicle Distribution
            </h3>
            {Object.entries(composition)
              .sort(([, a], [, b]) => (b as number) - (a as number))
              .map(([cls, cnt]) => {
                const pct = totalVehicles > 0 ? Math.round(((cnt as number) / totalVehicles) * 100) : 0;
                const Icon = vehicleIcon(cls);
                return (
                  <div key={cls}>
                    <div className="flex items-center justify-between text-sm mb-1.5">
                      <div className="flex items-center gap-2 text-foreground font-medium">
                        <Icon className="w-4 h-4 text-muted-foreground" />
                        <span className="capitalize">{cls.toLowerCase()}</span>
                      </div>
                      <span className="text-muted-foreground font-mono">{pct}% ({cnt as number})</span>
                    </div>
                    <div className="h-2 bg-secondary/50 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full bg-primary transition-all duration-500"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
          </div>

          {/* Density timeline */}
          <div className="bg-card border border-border rounded-xl p-5 shadow-sm space-y-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
              <Navigation className="w-4 h-4" /> Congestion Timeline (Recent Windows)
            </h3>
            <div className="space-y-2 overflow-y-auto max-h-72 pr-1 custom-scrollbar">
              {[...trafficWindows]
                .sort((a, b) => new Date(b.window_start).getTime() - new Date(a.window_start).getTime())
                .slice(0, 20)
                .map((w, i) => {
                  const dc = densityColor(w.congestion_level || w.density_level || 'LOW');
                  return (
                    <div key={i} className="flex items-center gap-3 py-1.5 border-b border-border last:border-0">
                      <div className="w-2 h-2 rounded-full shrink-0" style={{ background: dc.bar }} />
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-medium text-foreground truncate">
                          {w.unique_vehicle_count} vehicles &nbsp;
                          <span className={`text-[9px] font-bold uppercase px-1.5 py-0.5 rounded ${dc.bg} ${dc.text}`}>
                            {(w.congestion_level || w.density_level || 'LOW').toUpperCase()}
                          </span>
                        </p>
                        <p className="text-[10px] text-muted-foreground font-mono">
                          {new Date(w.window_start).toLocaleTimeString()}
                        </p>
                      </div>
                    </div>
                  );
                })}
            </div>
          </div>
        </section>
      )}
    </div>
  );
}

