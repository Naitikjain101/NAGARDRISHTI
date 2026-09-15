import { Maximize2, PlayCircle, Activity, Trash2, AlertTriangle } from 'lucide-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { fleetApi, type Journey } from '@/api/fleet';
import { videoApi } from '@/api/video';
import { useNavigate } from 'react-router-dom';
import { useState } from 'react';

export function LiveMonitoring() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [isResetConfirmOpen, setIsResetConfirmOpen] = useState(false);
  const [isResetting, setIsResetting] = useState(false);

  const { data: buses } = useQuery({
    queryKey: ['fleet'],
    queryFn: fleetApi.getBuses,
    refetchInterval: 5000,
  });

  // Extract all READY journeys
  const readyJourneys: Journey[] = [];
  if (buses) {
    buses.forEach(bus => {
      if (bus.journeys) {
        bus.journeys.forEach(j => {
          if (j.status.toUpperCase() === 'READY') {
            readyJourneys.push(j);
          }
        });
      }
    });
  }



  const handleReset = async () => {
    setIsResetting(true);
    try {
      const res = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/missions/reset`, {
        method: 'POST',
      });
      if (res.ok) {
        queryClient.invalidateQueries({ queryKey: ['fleet'] });
        queryClient.invalidateQueries({ queryKey: ['map_incidents'] });
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsResetting(false);
      setIsResetConfirmOpen(false);
    }
  };

  return (
    <div className="space-y-6 flex flex-col h-full">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold">Live Monitoring</h1>
          <p className="text-muted-foreground">Real-time CCTV grid view across the urban network.</p>
        </div>
        <div className="flex items-center gap-2">
          <button 
            onClick={() => setIsResetConfirmOpen(true)}
            className="flex items-center gap-2 px-4 py-2 bg-destructive/10 text-destructive border border-destructive/20 rounded-md hover:bg-destructive hover:text-destructive-foreground transition-colors"
          >
            <Trash2 className="h-4 w-4" />
            <span>Reset Data</span>
          </button>
          <button className="flex items-center gap-2 px-4 py-2 bg-secondary text-secondary-foreground rounded-md hover:bg-secondary/80 transition-colors">
            <Maximize2 className="h-4 w-4" />
            <span>Full Screen Grid</span>
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 flex-1">
        {/* Render Ready Journeys */}
        {readyJourneys.map((journey) => (
          <div key={journey.id} className="bg-card border border-primary/30 rounded-lg overflow-hidden flex flex-col h-[250px] shadow-[0_0_15px_rgba(34,197,94,0.15)] ring-1 ring-primary/20">
            <div className="p-2 border-b border-border bg-primary/10 flex justify-between items-center">
              <span className="text-xs font-medium font-mono text-primary">BUS_{journey.bus_id || 'DEMO'}</span>
              <div className="flex items-center gap-1">
                <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
                <span className="text-[10px] uppercase font-bold text-green-500 tracking-wider">Recorded AI Replay</span>
              </div>
            </div>
            <div className="flex-1 flex flex-col items-center justify-center bg-black relative group cursor-pointer" onClick={() => navigate(`/map?mission=${journey.id}`)}>
              {/* Actual video thumbnail backdrop */}
              {journey.metadata?.video_id && (
                <video 
                  src={`${videoApi.getStreamUrl(journey.metadata.video_id)}#t=2.0`}
                  className="absolute inset-0 w-full h-full object-cover opacity-60"
                  muted 
                  playsInline
                />
              )}
              {!journey.metadata?.video_id && (
                <Activity className="absolute inset-0 m-auto w-16 h-16 text-primary opacity-20 pointer-events-none" />
              )}
              <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent z-10 pointer-events-none" />
              
              <div className="relative z-20 text-center p-4 mt-auto w-full">
                <PlayCircle className="w-12 h-12 text-primary mx-auto mb-2 opacity-80 group-hover:opacity-100 group-hover:scale-110 transition-all duration-300" />
                <h3 className="text-white font-bold text-lg mb-1">{journey.route_name || 'Urban Survey'}</h3>
                <p className="text-xs text-green-400 font-mono">READY FOR REPLAY</p>
              </div>
            </div>
          </div>
        ))}

        {/* Empty state if no journeys */}
        {readyJourneys.length === 0 && (
          <div className="col-span-full h-[400px] flex flex-col items-center justify-center border-2 border-dashed border-border rounded-xl opacity-50">
            <Activity className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-bold text-muted-foreground">No Active Sessions</h3>
            <p className="text-sm text-muted-foreground max-w-md text-center mt-2">
              Upload videos in the Fleet section and add them to Live Monitoring to see them here.
            </p>
          </div>
        )}
      </div>

      {/* Reset Confirmation Modal */}
      {isResetConfirmOpen && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-xl shadow-2xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="p-6">
              <div className="w-12 h-12 rounded-full bg-destructive/20 flex items-center justify-center mb-4">
                <AlertTriangle className="h-6 w-6 text-destructive" />
              </div>
              <h2 className="text-xl font-bold mb-2">Reset Live Monitoring?</h2>
              <p className="text-sm text-muted-foreground mb-6">
                This will remove all Live Monitoring sessions and their associated incidents. This cannot be undone. Confirm?
              </p>
              
              <div className="flex justify-end gap-3">
                <button
                  onClick={() => setIsResetConfirmOpen(false)}
                  disabled={isResetting}
                  className="px-4 py-2 rounded-md font-medium text-sm hover:bg-secondary transition-colors disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleReset}
                  disabled={isResetting}
                  className="px-4 py-2 bg-destructive text-destructive-foreground rounded-md font-medium text-sm hover:bg-destructive/90 transition-colors disabled:opacity-50 flex items-center gap-2"
                >
                  {isResetting ? 'Resetting...' : 'Confirm Reset'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
