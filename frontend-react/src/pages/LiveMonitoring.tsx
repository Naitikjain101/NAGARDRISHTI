import { Maximize2, PlayCircle, Activity } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { fleetApi, type Journey } from '@/api/fleet';
import { useNavigate } from 'react-router-dom';

export function LiveMonitoring() {
  const navigate = useNavigate();

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



  return (
    <div className="space-y-6 flex flex-col h-full">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold">Live Monitoring</h1>
          <p className="text-muted-foreground">Real-time CCTV grid view across the urban network.</p>
        </div>
        <button className="flex items-center gap-2 px-4 py-2 bg-secondary text-secondary-foreground rounded-md hover:bg-secondary/80 transition-colors">
          <Maximize2 className="h-4 w-4" />
          <span>Full Screen Grid</span>
        </button>
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
              {/* Fake video thumbnail backdrop */}
              <div className="absolute inset-0 bg-gradient-to-t from-black/80 to-transparent z-10 pointer-events-none" />
              <Activity className="absolute inset-0 m-auto w-16 h-16 text-primary opacity-20 pointer-events-none" />
              
              <div className="relative z-20 text-center p-4">
                <PlayCircle className="w-12 h-12 text-primary mx-auto mb-2 opacity-80 group-hover:opacity-100 group-hover:scale-110 transition-all duration-300" />
                <h3 className="text-white font-bold text-lg mb-1">{journey.route_name || 'Urban Survey'}</h3>
                <p className="text-xs text-green-400 font-mono">READY FOR REPLAY</p>
              </div>
            </div>
          </div>
        ))}

      </div>
    </div>
  );
}
