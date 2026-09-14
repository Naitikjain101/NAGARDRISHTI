import { useState, useEffect, useMemo } from 'react';
import { Navigation, Car, Users, AlertTriangle, Loader2 } from 'lucide-react';
import { MetricCard } from '@/components/ui/MetricCard';
import { EmptyState } from '@/components/ui/EmptyState';

export function TrafficIntelligence() {
  const [missions, setMissions] = useState<any[]>([]);
  const [selectedVideo, setSelectedVideo] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const [trafficWindows, setTrafficWindows] = useState<any[]>([]);

  useEffect(() => {
    fetch('/api/missions/')
      .then(r => r.json())
      .then(data => {
        setMissions(data.missions || []);
        if (data.missions?.length > 0) {
          // Use the video_id from metadata for traffic history lookup
          const firstMission = data.missions[0];
          const meta = firstMission.metadata || {};
          const videoId = (typeof meta === 'object' ? meta.video_id : null) || firstMission.video_filename;
          setSelectedVideo(videoId || '');
        }
      })
      .catch(console.error);
  }, []);

  useEffect(() => {
    if (!selectedVideo) return;
    setIsLoading(true);
    fetch(`/api/traffic/history?video_id=${encodeURIComponent(selectedVideo)}`)
      .then(r => r.json())
      .then(data => {
        if (data && data.windows) {
          setTrafficWindows(data.windows);
        } else {
          setTrafficWindows([]);
        }
      })
      .catch(() => setTrafficWindows([]))
      .finally(() => setIsLoading(false));
  }, [selectedVideo]);

  const metrics = useMemo(() => {
    if (!trafficWindows || trafficWindows.length === 0) return null;
    
    let totalUniqueVehicles = 0;
    let peakFrameDensity = 0;
    const composition: Record<string, { count: number; percentage: number }> = {};
    const timeSeries: any[] = [];
    
    // Reverse because history is most-recent first
    const sortedWindows = [...trafficWindows].reverse();
    
    sortedWindows.forEach((w: any) => {
      totalUniqueVehicles += w.unique_vehicle_count || 0;
      if (w.unique_vehicle_count > peakFrameDensity) peakFrameDensity = w.unique_vehicle_count;
      
      const byClass = w.by_class || {};
      for (const [cls, count] of Object.entries(byClass)) {
         if (!composition[cls]) composition[cls] = { count: 0, percentage: 0 };
         composition[cls].count += (count as number);
      }
      
      timeSeries.push({
        timestamp: new Date(w.window_start).getTime(),
        totalActive: w.unique_vehicle_count,
        byClass: w.by_class
      });
    });
    
    let totalClassified = 0;
    for (const v of Object.values(composition)) {
       totalClassified += v.count;
    }
    if (totalClassified > 0) {
      for (const v of Object.values(composition)) {
         v.percentage = (v.count / totalClassified) * 100;
      }
    }
    
    const congestionScore = Math.min(100, Math.round((peakFrameDensity / 50) * 100));
    let congestionLabel = 'LOW';
    if (congestionScore >= 75) congestionLabel = 'CRITICAL';
    else if (congestionScore >= 50) congestionLabel = 'HIGH';
    else if (congestionScore >= 25) congestionLabel = 'MODERATE';
    
    return {
      totalUniqueVehicles,
      peakFrameDensity,
      congestionScore,
      congestionLabel,
      composition,
      timeSeries,
      helmetViolations: 'No data'
    };
  }, [trafficWindows]);

  return (
    <div className="space-y-6 flex flex-col h-full overflow-y-auto pb-10">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-2xl font-bold">Traffic Intelligence</h1>
          <p className="text-muted-foreground">Monitor traffic flow, congestion, and compliance from canonical AI observations.</p>
        </div>
        <select
          value={selectedVideo}
          onChange={e => setSelectedVideo(e.target.value)}
          className="bg-zinc-900 border border-border text-white text-sm rounded-md px-3 py-1.5 focus:outline-none focus:border-primary"
        >
          {missions.map(m => (
            <option key={m.id} value={m.video_filename}>
              {m.route_name} ({m.video_filename})
            </option>
          ))}
        </select>
      </div>

      {isLoading ? (
        <div className="flex-1 flex items-center justify-center min-h-[400px]">
          <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
        </div>
      ) : !metrics ? (
        <div className="flex-1 min-h-[400px]">
          <EmptyState 
            icon={Navigation}
            title="No Canonical Data Available"
            description="The selected journey has not been processed by the Unified AI Processor yet."
          />
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <MetricCard 
              title="Vehicles Observed" 
              value={metrics.totalUniqueVehicles} 
              icon={Car} 
              description="Unique tracking IDs across journey" 
            />
            <MetricCard 
              title="Avg Speed (km/h)" 
              value="—" 
              icon={Navigation} 
              description="Speed estimation unavailable" 
            />
            <MetricCard 
              title="Helmet Violations" 
              value={metrics.helmetViolations} 
              icon={Users} 
              description="Confirmed helmet violations" 
            />
            <MetricCard 
              title="Congestion Level" 
              value={metrics.congestionLabel} 
              icon={AlertTriangle} 
              description={`Score: ${metrics.congestionScore}/100 (Peak: ${metrics.peakFrameDensity})`} 
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="bg-zinc-900 border border-border rounded-xl p-6 lg:col-span-2">
              <div className="mb-4">
                <h3 className="text-sm font-medium text-muted-foreground">Traffic Flow Over Time</h3>
              </div>
              <div>
                <div className="h-64 flex items-end gap-1">
                  {metrics.timeSeries.map((ts, i) => {
                    const heightPct = Math.min(100, (ts.totalActive / Math.max(1, metrics.peakFrameDensity)) * 100);
                    return (
                      <div key={i} className="flex-1 bg-zinc-800 rounded-t relative group">
                        <div 
                          className="absolute bottom-0 w-full bg-primary rounded-t transition-all"
                          style={{ height: `${heightPct}%` }}
                        />
                        <div className="opacity-0 group-hover:opacity-100 absolute bottom-full mb-2 left-1/2 -translate-x-1/2 bg-black text-xs p-1 rounded z-10 whitespace-nowrap">
                          {ts.totalActive} vehicles
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            <div className="bg-zinc-900 border border-border rounded-xl p-6">
              <div className="mb-4">
                <h3 className="text-sm font-medium text-muted-foreground">Vehicle Composition</h3>
                <p className="text-xs text-amber-500/80 mt-1">
                  Note: Auto-rickshaws are not currently tracked as a distinct class; they may be included in Car, Motorcycle, or Bus counts.
                </p>
              </div>
              <div>
                <div className="space-y-4">
                  {Object.entries(metrics.composition)
                    .sort((a, b) => b[1].count - a[1].count)
                    .map(([cls, data]) => (
                    <div key={cls}>
                      <div className="flex justify-between text-xs mb-1">
                        <span className="font-medium text-white">{cls}</span>
                        <span className="text-muted-foreground">{data.percentage.toFixed(1)}% ({data.count})</span>
                      </div>
                      <div className="w-full bg-zinc-800 h-2 rounded-full overflow-hidden">
                        <div className="bg-primary h-full" style={{ width: `${data.percentage}%` }} />
                      </div>
                    </div>
                  ))}
                  {Object.keys(metrics.composition).length === 0 && (
                    <div className="text-xs text-muted-foreground text-center py-4">No classified vehicles</div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
