import { useState } from 'react';
import { Bus, Clock, AlertTriangle, Activity, Plus, PlayCircle, Loader2, FileVideo, Trash2, Edit2 } from 'lucide-react';
import { MetricCard } from '@/components/ui/MetricCard';
import { EmptyState } from '@/components/ui/EmptyState';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { fleetApi } from '@/api/fleet';
import { Skeleton } from '@/components/ui/Skeleton';
import { AddJourneyModal } from '@/components/fleet/AddJourneyModal';
import { useNavigate } from 'react-router-dom';

export function Fleet() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);

  const { data: buses, isLoading } = useQuery({
    queryKey: ['fleet'],
    queryFn: fleetApi.getBuses,
    // Poll every 5 s while any journey is actively processing; stop when all settle.
    refetchInterval: (query: any) => {
      const data = query.state.data as any[];
      const hasActive = data?.some((bus: any) =>
        bus.journeys?.some((j: any) => {
          const s = (j.status || '').toUpperCase();
          return s === 'QUEUED' || s === 'PROCESSING';
        })
      );
      return hasActive ? 5000 : false;
    },
  });

  const totalBuses = buses?.length || 0;
  const onlineBuses = buses?.filter(b => b.status === 'ONLINE').length || 0;
  const warningBuses = buses?.filter(b => b.status === 'WARNING').length || 0;
  const offlineBuses = buses?.filter(b => b.status === 'OFFLINE' || b.status === 'MAINTENANCE').length || 0;

  const formatDuration = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  const getStatusColor = (status: string) => {
    switch (status.toUpperCase()) {
      case 'READY': return 'bg-green-500 text-green-500';
      case 'QUEUED': return 'bg-amber-500 text-amber-500';
      case 'PROCESSING': return 'bg-blue-500 text-blue-500';
      case 'FAILED': return 'bg-red-500 text-red-500';
      default: return 'bg-gray-500 text-gray-500';
    }
  };

  const handleDeleteJourney = async (journeyId: string) => {
    if (!window.confirm("Are you sure you want to delete this journey? This will remove all AI insights linked to it.")) return;
    try {
      const res = await fetch(`/api/missions/${journeyId}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Failed to delete journey');
      queryClient.invalidateQueries({ queryKey: ['fleet'] });
    } catch (e) {
      console.error(e);
      alert('Error deleting journey');
    }
  };

  const handleEditJourney = async (journeyId: string, currentName: string) => {
    const newName = window.prompt("Enter new route name:", currentName);
    if (!newName || newName === currentName) return;
    try {
      const res = await fetch(`/api/missions/${journeyId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ journey_name: newName })
      });
      if (!res.ok) throw new Error('Failed to update journey');
      queryClient.invalidateQueries({ queryKey: ['fleet'] });
    } catch (e) {
      console.error(e);
      alert('Error updating journey');
    }
  };

  const getStatusLabel = (status: string) => {
    if (status.toUpperCase() === 'READY') return 'READY FOR REPLAY';
    return status.toUpperCase();
  };

  return (
    <div className="space-y-6 flex flex-col h-full overflow-y-auto pb-8">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-2xl font-bold">Fleet & Journeys</h1>
          <p className="text-muted-foreground">Manage buses and recorded survey journeys.</p>
        </div>
        <button 
          onClick={() => setIsAddModalOpen(true)}
          className="bg-primary text-primary-foreground px-4 py-2 rounded-md font-medium text-sm flex items-center gap-2 hover:bg-primary/90 transition-colors"
        >
          <Plus className="w-4 h-4" />
          ADD BUS JOURNEY
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard title="Total Buses" value={isLoading ? "—" : totalBuses} icon={Bus} description="Registered in network" />
        <MetricCard title="Online" value={isLoading ? "—" : onlineBuses} icon={Activity} description="Active telemetry" />
        <MetricCard title="Warning" value={isLoading ? "—" : warningBuses} icon={AlertTriangle} description="Deviations/delays" />
        <MetricCard title="Offline" value={isLoading ? "—" : offlineBuses} icon={Clock} description="Maintenance or parked" />
      </div>

      <div className="space-y-8 mt-6">
        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {[1, 2, 3].map(i => (
              <Skeleton key={i} className="h-64 w-full rounded-xl" />
            ))}
          </div>
        ) : !buses || buses.length === 0 ? (
          <EmptyState 
            icon={Bus}
            title="No Buses Found"
            description="Add your first bus journey to start monitoring."
            className="border-none bg-transparent my-12"
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {buses.map((bus) => (
              <div key={bus.id} className="bg-card border border-border rounded-xl shadow-sm overflow-hidden flex flex-col">
                {/* Bus Header */}
                <div className="p-4 bg-secondary/30 border-b border-border flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-primary/10 rounded-lg text-primary">
                      <Bus className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="font-bold text-lg leading-tight">{bus.fleet_number}</h3>
                      <p className="text-xs text-muted-foreground">{bus.route_id || 'Unknown Route'}</p>
                    </div>
                  </div>
                  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                    bus.status === 'ONLINE' ? 'bg-green-500/10 text-green-500' :
                    bus.status === 'WARNING' ? 'bg-amber-500/10 text-amber-500' :
                    'bg-gray-500/10 text-gray-500'
                  }`}>
                    {bus.status}
                  </span>
                </div>

                {/* Journeys List */}
                <div className="p-4 flex-1 flex flex-col gap-4">
                  {!bus.journeys || bus.journeys.length === 0 ? (
                    <div className="flex-1 flex items-center justify-center py-6 text-sm text-muted-foreground italic">
                      No journeys recorded
                    </div>
                  ) : (
                    bus.journeys.map((journey) => (
                      <div key={journey.id} className="bg-background border border-border rounded-lg p-3 flex flex-col gap-3 transition-colors hover:border-primary/30 group">
                        <div className="flex justify-between items-start gap-2">
                          <h4 className="font-semibold text-sm line-clamp-1" title={journey.route_name}>
                            {journey.route_name}
                          </h4>
                          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button onClick={() => handleEditJourney(journey.id, journey.route_name)} className="p-1 hover:bg-secondary rounded text-muted-foreground hover:text-foreground">
                              <Edit2 className="w-3.5 h-3.5" />
                            </button>
                            <button onClick={() => handleDeleteJourney(journey.id)} className="p-1 hover:bg-red-500/10 rounded text-red-500/70 hover:text-red-500">
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </div>

                        <div className="text-xs text-muted-foreground flex flex-col gap-1">
                          {journey.metadata?.start_location && journey.metadata?.destination ? (
                            <>
                              <div className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-green-500 shrink-0"></span><span className="truncate" title={journey.metadata.start_location}>{journey.metadata.start_location}</span></div>
                              <div className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-red-500 shrink-0"></span><span className="truncate" title={journey.metadata.destination}>{journey.metadata.destination}</span></div>
                            </>
                          ) : (
                            <div className="italic opacity-70">Route not assigned</div>
                          )}
                        </div>
                        
                        <div className="flex items-center gap-2">
                          <span className="relative flex h-2.5 w-2.5">
                            <span className={`absolute inline-flex h-full w-full rounded-full opacity-75 ${journey.status === 'PROCESSING' ? 'animate-ping ' + getStatusColor(journey.status).split(' ')[0] : ''}`}></span>
                            <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${getStatusColor(journey.status).split(' ')[0]}`}></span>
                          </span>
                          <span className={`text-[10px] font-bold uppercase tracking-wider ${getStatusColor(journey.status).split(' ')[1]}`}>
                            {getStatusLabel(journey.status)}
                          </span>
                        </div>
                        
                        {journey.status === 'PROCESSING' && (journey.metadata as any)?.telemetry && (() => {
                          const telemetry: any = (journey.metadata as any)?.telemetry || {};
                          const progress = telemetry.progress_frames || 0;
                          const total = telemetry.total_frames || 1;
                          const pct = Math.round((progress / total) * 100);
                          return (
                            <div className="mt-1 space-y-2.5 bg-primary/5 p-3 rounded-lg border border-primary/20">
                              <div className="flex justify-between text-[10px] font-bold tracking-wide uppercase text-primary">
                                <span>AI Processing</span>
                                <span>{pct}%</span>
                              </div>
                              
                              <div className="w-full bg-primary/10 rounded-full h-1.5 overflow-hidden">
                                <div 
                                  className="bg-primary h-1.5 rounded-full transition-all duration-500 ease-out" 
                                  style={{ width: `${Math.min(100, pct)}%` }}
                                ></div>
                              </div>
                              
                              <div className="grid grid-cols-2 gap-2 text-xs">
                                <div className="flex flex-col">
                                  <span className="text-muted-foreground text-[9px] uppercase tracking-wider">Frames</span>
                                  <span className="font-mono">{progress.toLocaleString()} / {total.toLocaleString()}</span>
                                </div>
                                <div className="flex flex-col text-right">
                                  <span className="text-muted-foreground text-[9px] uppercase tracking-wider">Speed & ETA</span>
                                  <span className="font-mono">{telemetry.processing_fps} FPS • {formatDuration(telemetry.eta_seconds)}</span>
                                </div>
                              </div>
                              
                              <div className="mt-4 grid grid-cols-3 gap-2">
                                <div className="bg-background rounded-lg p-2 border border-border/50">
                                  <p className="text-[10px] text-muted-foreground uppercase font-bold tracking-widest mb-1">Vehicles</p>
                                  <p className="text-lg font-black">{telemetry.vehicles_found || 0}</p>
                                </div>
                                <div className="bg-background rounded-lg p-2 border border-border/50">
                                  <p className="text-[10px] text-muted-foreground uppercase font-bold tracking-widest mb-1">Potholes</p>
                                  <p className="text-lg font-black text-orange-500">{telemetry.potholes_found || 0}</p>
                                </div>
                                <div className="bg-background rounded-lg p-2 border border-border/50">
                                  <p className="text-[10px] text-muted-foreground uppercase font-bold tracking-widest mb-1">Waterlogging</p>
                                  <p className="text-lg font-black text-blue-500">{telemetry.waterlogging_found || 0}</p>
                                </div>
                              </div>
                            </div>
                          );
                        })()}
                        
                        <div className="flex items-center gap-2 text-xs text-muted-foreground bg-secondary/40 p-2 rounded-md font-mono mt-1">
                          <FileVideo className="w-3.5 h-3.5 shrink-0" />
                          <span className="truncate flex-1" title={journey.video_filename}>{journey.video_filename}</span>
                          <span className="shrink-0 font-medium">
                            {formatDuration(journey.duration_seconds || 0)}
                          </span>
                        </div>
                        
                        <button 
                          onClick={() => navigate(`/map?mission=${journey.id}`)}
                          disabled={journey.status.toUpperCase() !== 'READY'}
                          className={`w-full py-1.5 rounded-md text-xs font-semibold flex items-center justify-center gap-2 transition-all
                            ${journey.status.toUpperCase() === 'READY' 
                              ? 'bg-primary/10 text-primary hover:bg-primary hover:text-primary-foreground' 
                              : 'bg-secondary text-muted-foreground cursor-not-allowed opacity-70'}`}
                        >
                          {journey.status.toUpperCase() === 'READY' ? (
                            <><PlayCircle className="w-4 h-4" /> OPEN FEED</>
                          ) : journey.status.toUpperCase() === 'PROCESSING' ? (
                            <><Loader2 className="w-4 h-4 animate-spin" /> PROCESSING AI...</>
                          ) : (
                            <><Clock className="w-4 h-4" /> PENDING PROCESSING</>
                          )}
                        </button>
                      </div>
                    ))
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <AddJourneyModal 
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
      />
    </div>
  );
}
