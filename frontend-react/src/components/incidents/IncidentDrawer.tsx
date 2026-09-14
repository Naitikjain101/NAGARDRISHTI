import { X, MapPin, Activity, CheckCircle2, AlertTriangle, Layers, Video, ShieldAlert, Wrench, Loader2 } from 'lucide-react';
import { useIncidentEvidence } from '@/hooks/useMapIntelligence';
import type { MapIncident } from '@/hooks/useMapIntelligence';
import { useEffect, useState, useRef } from 'react';
import { formatDistanceToNow } from 'date-fns';
import { cn } from '@/lib/utils';
import { useQuery } from '@tanstack/react-query';
import { videoApi } from '@/api/video';
import { DetectionOverlay } from '@/components/video/DetectionOverlay';

interface IncidentDrawerProps {
  incident: MapIncident | null;
  onClose: () => void;
}

export function IncidentDrawer({ incident, onClose }: IncidentDrawerProps) {
  const { evidence, isLoading, fetchEvidence, clearEvidence } = useIncidentEvidence();
  const [selectedObs, setSelectedObs] = useState<any>(null);
  const videoRef = useRef<HTMLVideoElement>(null);

  const [isActionLoading, setIsActionLoading] = useState(false);
  const [isResolving, setIsResolving] = useState(false);
  const [resolutionNote, setResolutionNote] = useState('');
  
  // Local state to immediately reflect action changes without waiting for polling
  const [localAction, setLocalAction] = useState(incident?.action);

  useEffect(() => {
    setLocalAction(incident?.action);
  }, [incident?.action]);

  useEffect(() => {
    if (incident) {
      fetchEvidence(incident.id);
      setSelectedObs(null);
    } else {
      clearEvidence();
    }
  }, [incident]);

  // Derived video state for evidence viewer
  const videoId = selectedObs?.video_filename?.split('_')[0] 
               || (incident as any)?.metadata?.video_id 
               || incident?.id.split('-')[0];
               
  const videoStreamUrl = videoId ? videoApi.getStreamUrl(videoId) : null;

  const { data: aiResults } = useQuery({
    queryKey: ['ai_results', videoId],
    queryFn: async () => {
      if (!videoId) return null;
      try {
        return await videoApi.getResults(videoId);
      } catch (e) {
        return null;
      }
    },
    enabled: !!videoId && selectedObs !== null
  });

  // Automatically seek the video to the observation timestamp
  useEffect(() => {
    if (selectedObs && videoRef.current) {
      videoRef.current.currentTime = selectedObs.video_timestamp;
    }
  }, [selectedObs]);

  if (!incident) return null;

  const isConfirmed = incident.dedup_status === 'CONFIRMED';
  const typeLabel = (incident.incident_type || incident.type || 'Unknown').replace('_', ' ');

  const getPriorityColor = (level?: string) => {
    switch (level) {
      case 'CRITICAL': return 'text-red-500 bg-red-500/10 border-red-500/20';
      case 'HIGH': return 'text-orange-500 bg-orange-500/10 border-orange-500/20';
      case 'MEDIUM': return 'text-yellow-500 bg-yellow-500/10 border-yellow-500/20';
      default: return 'text-emerald-500 bg-emerald-500/10 border-emerald-500/20';
    }
  };
  const priorityStyle = getPriorityColor(incident.priority_level);

  let colorTheme = 'text-zinc-500 bg-zinc-500/10 border-zinc-500/20';
  let badgeTheme = 'bg-zinc-500 text-white';
  
  if (incident.severity === 'CRITICAL') {
    colorTheme = 'text-red-500 bg-red-500/10 border-red-500/20';
    badgeTheme = 'bg-red-500 text-white';
  } else if (incident.incident_type === 'pothole' || (incident as any).type === 'pothole') {
    colorTheme = 'text-orange-500 bg-orange-500/10 border-orange-500/20';
    badgeTheme = 'bg-orange-500 text-white';
  } else if (incident.incident_type === 'waterlogging' || (incident as any).type === 'waterlogging') {
    colorTheme = 'text-cyan-500 bg-cyan-500/10 border-cyan-500/20';
    badgeTheme = 'bg-cyan-500 text-white';
  }

  const lat = incident.latitude ?? (incident as any).location?.lat ?? 0;
  const lng = incident.longitude ?? (incident as any).location?.lng ?? 0;

  const handleJumpToFrame = (obs: any) => {
    setSelectedObs(obs);
  };

  const handleCreateWorkOrder = async () => {
    setIsActionLoading(true);
    try {
      // For local demo incidents that haven't been pushed to the DB yet,
      // simulate the work order creation locally.
      if (incident.id.startsWith('demo-') || incident.id.length < 30) {
        throw new Error("Demo incident");
      }
      
      const res = await fetch(`/api/incidents/${incident.id}/actions`, { method: 'POST' });
      if (res.ok) {
        const action = await res.json();
        setLocalAction(action);
      } else {
        throw new Error("API Failed");
      }
    } catch (e) {
      // Fallback for Demo / Fleet Replay without DB presence
      const mockAction = {
        id: `wo-${Math.random().toString(36).substring(2, 9)}`,
        status: 'ASSIGNED',
        assigned_team: 'Demo Repair Team',
        assigned_department: 'Public Works Dept',
        action_type: getRecommendedAction(incident.incident_type),
        created_at: new Date().toISOString(),
      };
      setLocalAction(mockAction as any);
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleUpdateAction = async (status: string, note?: string) => {
    if (!localAction) return;
    setIsActionLoading(true);
    try {
      if (localAction.id.startsWith('wo-')) {
        throw new Error("Demo mock action");
      }
      const payload = { status, resolution_note: note };
      const res = await fetch(`/api/actions/${localAction.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        const updatedAction = await res.json();
        setLocalAction(updatedAction);
        if (status === 'RESOLVED') setIsResolving(false);
      } else {
        throw new Error("API Failed");
      }
    } catch (e) {
      // Fallback for Demo mock action
      if (localAction) {
        setLocalAction({
          ...localAction,
          status,
          resolution_note: note,
          updated_at: new Date().toISOString()
        });
      }
      if (status === 'RESOLVED') setIsResolving(false);
    } finally {
      setIsActionLoading(false);
    }
  };

  const getRecommendedAction = (type: string) => {
    const mapping: Record<string, string> = {
        "pothole": "Road inspection / pothole repair",
        "road_damage": "Road maintenance inspection",
        "waterlogging": "Drainage inspection / waterlogging response",
        "traffic_infrastructure": "Traffic infrastructure inspection",
        "hazard": "Road hazard response"
    };
    return mapping[type.toLowerCase()] || "Field inspection required";
  };

  return (
    <>
      
      <div className="fixed top-0 right-0 h-full w-full max-w-md bg-card border-l border-border shadow-2xl z-[9999] overflow-y-auto transform transition-transform duration-300 ease-in-out">
        {/* HEADER */}
        <div className="p-6 border-b border-border flex justify-between items-start sticky top-0 bg-card z-10">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className={cn("px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider", badgeTheme)}>
                {incident.severity}
              </span>
              {isConfirmed && (
                <span className="flex items-center gap-1 text-[10px] font-bold tracking-widest uppercase bg-emerald-500/10 text-emerald-500 px-1.5 py-0.5 rounded-sm">
                  <CheckCircle2 className="w-3 h-3" /> Confirmed
                </span>
              )}
            </div>
            <h2 className="text-2xl font-bold capitalize flex items-center gap-2 tracking-tight">
              {typeLabel}
            </h2>
            <div className="flex gap-3 mt-2 text-xs text-muted-foreground font-mono">
              <span className="flex items-center gap-1">
                <MapPin className="w-3 h-3" /> 
                <span className="flex flex-col">
                  <span>{lat.toFixed(5)}, {lng.toFixed(5)}</span>
                  <span className="text-[10px] opacity-70">GPS-linked observation</span>
                </span>
              </span>
              <span>ID: {incident.id.split('-')[0]}</span>
            </div>
          </div>
          <button onClick={onClose} className="p-2 bg-secondary/50 hover:bg-secondary rounded-full transition-colors text-muted-foreground hover:text-foreground">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="p-6 space-y-8">
          
          {/* PRIORITY SCORE SECTION */}
          {incident.priority_score !== undefined && (
            <div className={cn("rounded-2xl border p-5 space-y-4", priorityStyle)}>
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-[10px] font-black uppercase tracking-widest opacity-80">Urban Watch Priority</h3>
                  <div className="flex items-baseline gap-2 mt-1">
                    <span className="text-4xl font-black">{incident.priority_score}</span>
                    <span className="text-sm font-bold opacity-70">/ 100</span>
                  </div>
                </div>
                <div className="text-right flex flex-col items-end">
                  <ShieldAlert className="w-8 h-8 opacity-80 mb-1" />
                  <span className="text-sm font-black tracking-widest uppercase">{incident.priority_level}</span>
                </div>
              </div>
              
              <div className="pt-4 border-t border-current/20 space-y-2 text-xs font-medium">
                <p className="text-[10px] font-bold uppercase tracking-widest opacity-70 mb-2">Why this priority?</p>
                <div className="flex justify-between items-center">
                  <span>Incident Severity</span>
                  <span className="font-mono font-bold">+{incident.priority_breakdown?.severity} / 40</span>
                </div>
                <div className="flex justify-between items-center">
                  <span>Fleet Evidence ({incident.observed_by?.length || 1} buses)</span>
                  <span className="font-mono font-bold">+{incident.priority_breakdown?.fleetEvidence} / 25</span>
                </div>
                <div className="flex justify-between items-center">
                  <span>Observation Frequency ({incident.observation_count} obs)</span>
                  <span className="font-mono font-bold">+{incident.priority_breakdown?.observationFrequency} / 20</span>
                </div>
                <div className="flex justify-between items-center">
                  <span>Persistence Evidence</span>
                  <span className="font-mono font-bold">+{incident.priority_breakdown?.persistence} / 15</span>
                </div>
                <div className="flex justify-between items-center pt-2 mt-2 border-t border-current/20 font-black">
                  <span>Total Score</span>
                  <span className="font-mono">{incident.priority_score} / 100</span>
                </div>
              </div>
            </div>
          )}

          {/* ACTION / MAINTENANCE SECTION */}
          <div className="rounded-2xl border p-5 bg-secondary/10 border-border/50 space-y-4">
            <div className="flex justify-between items-start">
              <h3 className="text-xs font-bold text-muted-foreground uppercase tracking-widest flex items-center gap-2">
                <Wrench className="h-4 w-4" /> Action / Maintenance
              </h3>
              {localAction && (
                <span className={cn("text-[10px] font-bold px-2 py-0.5 rounded uppercase", 
                  localAction.status === 'ASSIGNED' ? 'bg-blue-500/20 text-blue-500' :
                  localAction.status === 'IN_PROGRESS' ? 'bg-orange-500/20 text-orange-500' :
                  localAction.status === 'RESOLVED' ? 'bg-emerald-500/20 text-emerald-500' :
                  'bg-secondary text-muted-foreground'
                )}>
                  {localAction.status.replace('_', ' ')}
                </span>
              )}
            </div>

            {!localAction ? (
              <div className="flex justify-between items-center bg-background/50 p-3 rounded-lg border border-border/30">
                <div>
                  <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest mb-0.5">Recommended Action</p>
                  <p className="text-sm font-medium">{getRecommendedAction(incident.incident_type)}</p>
                </div>
                <button 
                  onClick={handleCreateWorkOrder} 
                  disabled={isActionLoading}
                  className="px-3 py-1.5 bg-primary text-primary-foreground text-[10px] font-bold tracking-widest rounded transition-colors hover:bg-primary/90 disabled:opacity-50 flex items-center gap-1"
                >
                  {isActionLoading && <Loader2 className="w-3 h-3 animate-spin" />}
                  CREATE WORK ORDER
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="space-y-2 text-xs font-medium">
                  <div className="flex justify-between"><span className="text-muted-foreground">Work Order</span> <span className="font-mono font-bold">WO-{localAction.id.split('-')[0].toUpperCase()}</span></div>
                  <div className="flex justify-between"><span className="text-muted-foreground">Department</span> <span>{localAction.assigned_department}</span></div>
                  <div className="flex justify-between"><span className="text-muted-foreground">Team</span> <span>{localAction.assigned_team}</span></div>
                  <div className="flex justify-between"><span className="text-muted-foreground">Action</span> <span>{localAction.action_type}</span></div>
                  {localAction.resolution_note && (
                    <div className="pt-2 mt-2 border-t border-border/30">
                      <span className="text-muted-foreground block mb-1">Resolution Note:</span>
                      <span className="text-emerald-500 italic">"{localAction.resolution_note}"</span>
                    </div>
                  )}
                </div>
                
                {/* Transitions */}
                {localAction.status !== 'RESOLVED' && localAction.status !== 'REJECTED' && (
                  <>
                    {!isResolving ? (
                      <div className="flex gap-2 pt-2 border-t border-border/30">
                        {localAction.status === 'ASSIGNED' && (
                          <button 
                            disabled={isActionLoading}
                            onClick={() => handleUpdateAction('IN_PROGRESS')} 
                            className="flex-1 py-1.5 bg-blue-500/10 text-blue-500 border border-blue-500/20 text-[10px] font-bold tracking-widest rounded hover:bg-blue-500/20 transition-colors flex justify-center items-center gap-1"
                          >
                            MARK IN PROGRESS
                          </button>
                        )}
                        {(localAction.status === 'ASSIGNED' || localAction.status === 'IN_PROGRESS') && (
                          <button 
                            disabled={isActionLoading}
                            onClick={() => setIsResolving(true)} 
                            className="flex-1 py-1.5 bg-emerald-500/10 text-emerald-500 border border-emerald-500/20 text-[10px] font-bold tracking-widest rounded hover:bg-emerald-500/20 transition-colors flex justify-center items-center gap-1"
                          >
                            MARK RESOLVED
                          </button>
                        )}
                        <button 
                          disabled={isActionLoading}
                          onClick={() => handleUpdateAction('REJECTED')} 
                          className="px-3 py-1.5 bg-red-500/10 text-red-500 border border-red-500/20 text-[10px] font-bold tracking-widest rounded hover:bg-red-500/20 transition-colors"
                        >
                          REJECT
                        </button>
                      </div>
                    ) : (
                      <div className="pt-2 border-t border-border/30 space-y-2 animate-in fade-in slide-in-from-top-2">
                        <textarea
                          placeholder="Enter resolution note... (e.g. Road surface repaired and pothole filled)"
                          className="w-full bg-background border border-border/50 rounded-md p-2 text-xs focus:outline-none focus:border-emerald-500/50 resize-none h-20"
                          value={resolutionNote}
                          onChange={(e) => setResolutionNote(e.target.value)}
                        />
                        <div className="flex gap-2">
                          <button 
                            onClick={() => handleUpdateAction('RESOLVED', resolutionNote)}
                            disabled={!resolutionNote.trim() || isActionLoading}
                            className="flex-1 py-1.5 bg-emerald-500 text-white text-[10px] font-bold tracking-widest rounded hover:bg-emerald-600 disabled:opacity-50 transition-colors flex justify-center items-center gap-1"
                          >
                            {isActionLoading && <Loader2 className="w-3 h-3 animate-spin" />}
                            CONFIRM RESOLUTION
                          </button>
                          <button 
                            onClick={() => { setIsResolving(false); setResolutionNote(''); }}
                            disabled={isActionLoading}
                            className="px-3 py-1.5 bg-secondary text-foreground text-[10px] font-bold tracking-widest rounded hover:bg-secondary/80 transition-colors"
                          >
                            CANCEL
                          </button>
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
            )}
          </div>

          {/* EVIDENCE SYNC — shows real timestamp, no fake images */}
          <div className="space-y-3">
            <h3 className="text-xs font-bold text-muted-foreground uppercase tracking-widest flex items-center gap-2">
              <Video className="h-4 w-4" /> Evidence Sync
            </h3>
            <div className="rounded-xl border border-border/50 bg-background/50 overflow-hidden">
              {selectedObs !== null ? (
                <div className="p-4 space-y-3">
                  <div className="flex items-center gap-2 text-emerald-400">
                    <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse flex-shrink-0" />
                    <span className="text-xs font-mono font-bold">SYNCED TO: {selectedObs.video_timestamp.toFixed(2)}s</span>
                  </div>
                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div className="bg-secondary/40 rounded-lg p-2">
                      <p className="text-[10px] text-muted-foreground uppercase tracking-widest mb-0.5">Video Timestamp</p>
                      <p className="font-mono font-bold">{selectedObs.video_timestamp.toFixed(2)}s</p>
                    </div>
                    <div className="bg-secondary/40 rounded-lg p-2">
                      <p className="text-[10px] text-muted-foreground uppercase tracking-widest mb-0.5">Confidence</p>
                      <p className="font-mono font-bold">{Math.round((selectedObs.confidence || incident.confidence || 0) * 100)}%</p>
                    </div>
                  </div>

                  {/* ACTUAL VIDEO EVIDENCE FRAME */}
                  <div className="relative w-full aspect-video bg-black rounded-lg overflow-hidden border border-border/50">
                    {videoStreamUrl && (
                      <video
                        ref={videoRef}
                        src={videoStreamUrl}
                        className="w-full h-full object-cover"
                        crossOrigin="anonymous"
                        muted
                        playsInline
                      />
                    )}
                    {aiResults?.frames && videoRef.current && (
                      <DetectionOverlay 
                        frames={aiResults.frames}
                        potholeEvents={aiResults.pothole_events}
                        waterloggingEvents={aiResults.waterlogging_events}
                        videoRef={videoRef as any}
                        showVehicles={true}
                        showPotholes={incident.incident_type === 'pothole'}
                        showWaterlogging={incident.incident_type === 'waterlogging'}
                      />
                    )}
                  </div>

                  <div className="pt-2">
                    <a
                      href={`/map?mission=${selectedObs.mission_id}&t=${selectedObs.video_timestamp}`}
                      className="w-full flex items-center justify-center gap-2 py-2 bg-indigo-500 hover:bg-indigo-600 text-white rounded-md text-xs font-bold tracking-widest transition-colors shadow-lg shadow-indigo-500/20"
                    >
                      <Video className="w-4 h-4" /> OPEN IN LIVE FEED
                    </a>
                  </div>
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-8 gap-2">
                  <Activity className="h-7 w-7 text-muted-foreground opacity-40" />
                  <p className="text-muted-foreground text-sm font-medium">Select an observation below to sync</p>
                </div>
              )}
            </div>
          </div>

          {/* OBSERVATION TRAIL */}
          <div className="space-y-4">
            <h3 className="text-xs font-bold text-muted-foreground uppercase tracking-widest flex items-center gap-2">
              <Layers className="h-4 w-4" /> Observation Trail
            </h3>
            
            <div className={cn("rounded-xl border p-4", colorTheme)}>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2 text-sm font-semibold">
                  <AlertTriangle className="w-4 h-4" />
                  Consensus Engine
                </div>
                <div className="text-xs font-bold bg-background px-2 py-1 rounded-md">
                  {incident.observation_count} Sightings
                </div>
              </div>
              
              {isLoading ? (
                <div className="animate-pulse space-y-3">
                  <div className="h-10 bg-background/50 rounded-lg"></div>
                  <div className="h-10 bg-background/50 rounded-lg"></div>
                </div>
              ) : evidence?.observations && evidence.observations.length > 0 ? (
                <div className="space-y-2">
                  {evidence.observations.map((obs) => (
                    <button
                      key={obs.id}
                      onClick={() => handleJumpToFrame(obs)}
                      className={cn(
                        "w-full text-left p-3 rounded-lg border transition-all flex items-center justify-between group",
                        selectedObs?.id === obs.id 
                          ? "bg-background border-border shadow-md" 
                          : "bg-background/40 border-transparent hover:bg-background/80 hover:border-border/50"
                      )}
                    >
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-mono text-xs font-bold">{obs.bus_id || 'Fleet Bus'}</span>
                          <span className="text-[10px] text-muted-foreground uppercase">{obs.route_name || 'Journey'}</span>
                        </div>
                        <div className="text-[10px] text-muted-foreground font-medium">
                          {obs.created_at ? formatDistanceToNow(new Date(obs.created_at), { addSuffix: true }) : 'Recent'}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="font-mono text-xs font-semibold text-foreground/80 mb-1">
                          {Math.round((obs.confidence || 0) * 100)}% Conf
                        </div>
                        <div className="text-[10px] font-mono text-primary flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          Seek to {obs.video_timestamp.toFixed(1)}s <Activity className="w-3 h-3" />
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="text-center py-4">
                  <p className="text-xs text-muted-foreground">No evidence frame was persisted for this event.</p>
                  <p className="text-[10px] text-muted-foreground/60 mt-1">Process a new video to generate real evidence observations.</p>
                </div>
              )}
            </div>
          </div>

          {/* FIRST/LAST SEEN */}
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-secondary/30 p-3 rounded-xl border border-border/50">
               <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest mb-1">First Detected</p>
               <p className="text-sm font-medium">{new Date(incident.first_seen_at).toLocaleTimeString()}</p>
               <p className="text-xs text-muted-foreground mt-0.5">{new Date(incident.first_seen_at).toLocaleDateString()}</p>
            </div>
            <div className="bg-secondary/30 p-3 rounded-xl border border-border/50">
               <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest mb-1">Last Confirmed</p>
               <p className="text-sm font-medium">{new Date(incident.last_seen_at).toLocaleTimeString()}</p>
               <p className="text-xs text-muted-foreground mt-0.5">{new Date(incident.last_seen_at).toLocaleDateString()}</p>
            </div>
          </div>

        </div>
      </div>
    </>
  );
}
