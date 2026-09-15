import { Activity, Car, Bus, Truck, Bike } from 'lucide-react';
import { useMemo } from 'react';
import { cn } from '@/lib/utils';

interface TrafficDensityPanelProps {
  results: any;
  currentTime: number;
}

export function TrafficDensityPanel({ results, currentTime }: TrafficDensityPanelProps) {
  // Extract overall counts
  const vehicleCounts = results?.vehicle_counts || { total_unique_vehicles: 0, by_class: {} };
  const densityWindows = results?.density_windows || [];

  // Find the active window based on currentTime, or fallback to the most recent past window
  const currentWindow = useMemo(() => {
    if (!densityWindows.length) return null;
    
    // Exact match
    let match = densityWindows.find(
      (w: any) => currentTime >= w.window_start && currentTime <= w.window_end
    );
    
    if (!match) {
      // Find the most recent window that has already started
      const pastWindows = [...densityWindows].filter(w => w.window_start <= currentTime);
      if (pastWindows.length > 0) {
        // Sort descending by start time
        pastWindows.sort((a, b) => b.window_start - a.window_start);
        match = pastWindows[0];
      }
    }
    
    return match || densityWindows[0];
  }, [densityWindows, currentTime]);

  const densityLevel = currentWindow?.density_level?.toUpperCase() || 'UNKNOWN';
  const densityColor = 
    densityLevel === 'HIGH' ? 'text-red-600 bg-red-50 border-red-200' :
    densityLevel === 'MEDIUM' ? 'text-amber-600 bg-amber-50 border-amber-200' :
    densityLevel === 'LOW' ? 'text-green-600 bg-green-50 border-green-200' :
    'text-gray-600 bg-gray-50 border-gray-200';

  const formatClass = (cls: string) => cls.replace(/_/g, ' ');

  // Get icons for vehicle types
  const getIcon = (type: string) => {
    const t = type.toLowerCase();
    if (t.includes('bus')) return Bus;
    if (t.includes('truck')) return Truck;
    if (t.includes('motorcycle') || t.includes('bike')) return Bike;
    return Car;
  };

  return (
    <div className="bg-card border border-border rounded-lg shadow-sm flex flex-col h-full">
      <div className="px-4 py-3 border-b border-border flex items-center gap-2 shrink-0">
        <Activity className="h-4 w-4 text-primary" />
        <h3 className="font-semibold text-sm">Traffic Density</h3>
      </div>
      
      {!results ? (
        <div className="flex-1 p-4 flex items-center justify-center text-sm text-muted-foreground italic">
          No traffic data available.
        </div>
      ) : (
        <div className="p-4 flex-1 flex flex-col gap-5">
          <div className="flex items-center justify-between">
            {currentWindow ? (
              <>
                <div>
                  <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Current Density</p>
                  <div className="flex items-baseline gap-2">
                    <span className={cn('px-2.5 py-0.5 rounded text-xs font-bold border', densityColor)}>
                      {densityLevel}
                    </span>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Vehicles / min</p>
                  <p className="text-2xl font-bold text-foreground">
                    {currentWindow.unique_vehicle_count}
                  </p>
                </div>
              </>
            ) : (
              <div className="text-xs text-muted-foreground italic py-2">
                No traffic observation at this timestamp.
              </div>
            )}
          </div>

          <div>
            <p className="text-xs text-muted-foreground uppercase tracking-wider mb-2">Total Journey Distribution</p>
            {Object.keys(vehicleCounts.by_class || {}).length === 0 ? (
              <p className="text-xs text-muted-foreground italic">No vehicles detected.</p>
            ) : (
              <div className="space-y-2">
                {Object.entries(vehicleCounts.by_class).map(([cls, count]) => {
                  const countNum = count as number;
                  if (countNum === 0) return null;
                  const Icon = getIcon(cls);
                  return (
                    <div key={cls} className="flex items-center justify-between text-sm">
                      <div className="flex items-center gap-2 text-muted-foreground">
                        <Icon className="h-3.5 w-3.5" />
                        <span className="capitalize">{formatClass(cls)}</span>
                      </div>
                      <span className="font-semibold">{countNum}</span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
