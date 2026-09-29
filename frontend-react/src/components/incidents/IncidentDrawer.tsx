import { X, MapPin, CheckCircle2, Video, Loader2, Calendar } from 'lucide-react';
import { useIncidentEvidence } from '@/hooks/useMapIntelligence';
import type { MapIncident } from '@/hooks/useMapIntelligence';
import { useEffect, useState, useRef } from 'react';
import { formatDistanceToNow } from 'date-fns';
import { cn } from '@/lib/utils';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { videoApi } from '@/api/video';
import { DetectionOverlay } from '@/components/video/DetectionOverlay';
import { formatVideoTimestamp } from '@/utils/time';
import { fetchRaw } from '../../api/client';

interface IncidentDrawerProps {
  incident: MapIncident | null;
  onClose: () => void;
}

export function IncidentDrawer({ incident, onClose }: IncidentDrawerProps) {
  const { evidence, isLoading, fetchEvidence, clearEvidence } = useIncidentEvidence();
  const [selectedObs, setSelectedObs] = useState<any>(null);
  const imgRef = useRef<HTMLImageElement>(null);

  const [isActionLoading, setIsActionLoading] = useState(false);
  const [isResolving, setIsResolving] = useState(false);
  const [resolutionNote, setResolutionNote] = useState('');
  
  const [localAction, setLocalAction] = useState(incident?.action);
  const queryClient = useQueryClient();
  const [createError, setCreateError] = useState<string | null>(null);

  useEffect(() => {
    setLocalAction(incident?.action);
    setCreateError(null);
    
    if (incident && !incident.id.startsWith('demo-') && incident.id.length > 30) {
      fetchRaw(`/api/incidents/${incident.id}/actions`)
        .then(res => res.ok ? res.json() : null)
        .then(action => { if (action) setLocalAction(action); })
        .catch(console.error);
    }
  }, [incident]);

  useEffect(() => {
    if (incident) {
      fetchEvidence(incident.id);
      // Wait to set selectedObs until evidence is loaded in the next effect
      setSelectedObs(null);
    } else {
      clearEvidence();
    }
  }, [incident]);

  // Auto-select the first observation when evidence loads
  useEffect(() => {
    if (evidence?.observations && evidence.observations.length > 0 && !selectedObs) {
      setSelectedObs(evidence.observations[0]);
    }
  }, [evidence, selectedObs]);

  // Derived video state for evidence viewer
  const videoId = (incident as any)?.metadata?.video_id 
               || (selectedObs?.video_filename ? selectedObs.video_filename.split('_')[0] : null)
               || incident?.id.split('-')[0];
               
  const { data: aiResults } = useQuery({
    queryKey: ['ai_results', videoId],
    queryFn: async () => {
      if (!videoId) return null;
      try { return await videoApi.getResults(videoId); } catch { return null; }
    },
    enabled: !!videoId && selectedObs !== null
  });


  // Directly fetch Supabase signed URL for video — bypasses Render backend entirely
  const [signedVideoUrl, setSignedVideoUrl] = useState<string | null>(null);
  const [videoLoading, setVideoLoading] = useState(false);

  useEffect(() => {
    if (!videoId) { setSignedVideoUrl(null); return; }
    setVideoLoading(true);
    setSignedVideoUrl(null);
    videoApi.getSignedStreamUrl(videoId).then(url => {
      setSignedVideoUrl(url);
      setVideoLoading(false);
    });
  }, [videoId]);

  if (!incident) return null;

  const isConfirmed = incident.dedup_status === 'CONFIRMED';
  const typeLabel = (incident.incident_type || incident.type || 'Unknown').replace('_', ' ');
  const severityBadgeClass = incident.severity === 'CRITICAL' ? 'bg-red-500 text-white' :
                             incident.severity === 'HIGH' ? 'bg-orange-500 text-white' :
                             incident.severity === 'MEDIUM' ? 'bg-yellow-500 text-white' : 'bg-emerald-500 text-white';

  const lat = incident.latitude ?? (incident as any).location?.lat ?? 0;
  const lng = incident.longitude ?? (incident as any).location?.lng ?? 0;

  const handleJumpToFrame = (obs: any) => setSelectedObs(obs);

  const handleCreateWorkOrder = async () => {
    setIsActionLoading(true);
    setCreateError(null);
    try {
      const res = await fetchRaw(`/api/incidents/${incident.id}/actions`, { method: 'POST' });
      const data = await res.json();
      
      if (res.ok) {
        setLocalAction(data);
        queryClient.invalidateQueries({ queryKey: ['maintenance'] });
      } else {
        throw new Error(data.detail || "API Failed to create work order");
      }
    } catch (e: any) {
      setCreateError(e.message);
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleUpdateAction = async (status: string, note?: string) => {
    if (!localAction) return;
    setIsActionLoading(true);
    try {
      const payload = { status, resolution_note: note };
      const res = await fetchRaw(`/api/actions/${localAction.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        const updatedAction = await res.json();
        setLocalAction(updatedAction);
        queryClient.invalidateQueries({ queryKey: ['maintenance'] });
        queryClient.invalidateQueries({ queryKey: ['map_incidents'] });
        if (status === 'RESOLVED') setIsResolving(false);
      } else {
        throw new Error("API Update Failed");
      }
    } catch (e) {
      console.error(e);
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

  const observationsList = (() => {
    const list = ((evidence?.observations && evidence.observations.length > 0) ? evidence.observations : ((incident as any).observations || []));
    if (list.length > 0) return list;
    if (incident.metadata?.video_time_sec != null) {
      return [{
         id: 'synth-obs',
         video_timestamp: incident.metadata.video_time_sec,
         video_filename: incident.metadata.video_id || '',
         route_name: incident.metadata.route_name || 'Detected Issue',
         confidence: incident.confidence,
         created_at: incident.created_at,
      }];
    }
    return [];
  })();

  return (
    <div className="fixed top-0 right-0 h-full w-full max-w-[480px] bg-card border-l border-border shadow-2xl z-[9999] overflow-y-auto transform transition-transform duration-300 ease-in-out">
      
      {/* ---------------- HEADER ---------------- */}
      <div className="px-6 pt-6 pb-4 border-b border-border bg-card sticky top-0 z-20 flex justify-between items-start">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className={cn("px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider", severityBadgeClass)}>
              {incident.severity}
            </span>
            {isConfirmed && (
              <span className="flex items-center gap-1 text-[10px] font-bold tracking-widest uppercase bg-emerald-500/10 text-emerald-500 px-1.5 py-0.5 rounded-sm">
                <CheckCircle2 className="w-3 h-3" /> Confirmed
              </span>
            )}
          </div>
          <h2 className="text-xl font-bold capitalize text-foreground">{typeLabel}</h2>
          <div className="text-xs text-muted-foreground mt-1 flex flex-col gap-0.5">
            <span className="font-mono">ID: {incident.id.split('-')[0]}</span>
            <span className="flex items-center gap-1">
              <MapPin className="w-3 h-3 shrink-0" />
              {lat.toFixed(5)}, {lng.toFixed(5)}
            </span>
          </div>
        </div>
        <button onClick={onClose} className="p-2 bg-secondary/50 hover:bg-secondary rounded-full transition-colors text-muted-foreground hover:text-foreground">
          <X className="h-5 w-5" />
        </button>
      </div>

      <div className="p-6 space-y-8">

        {/* ---------------- EVIDENCE ---------------- */}
        <section className="space-y-4">
          <h3 className="text-[11px] font-bold text-muted-foreground uppercase tracking-widest border-b border-border pb-1">Evidence</h3>
          
          <div className="rounded-xl border border-border bg-secondary/10 overflow-hidden">
            {selectedObs !== null ? (
              <div className="p-3">
                <div className="relative w-full aspect-video bg-black rounded-lg overflow-hidden border border-border/50 mb-3">
                  {videoLoading && (
                    <div className="absolute inset-0 flex items-center justify-center bg-black/80 z-10">
                      <Loader2 className="w-7 h-7 text-primary animate-spin" />
                      <span className="ml-2 text-xs text-white/60">Loading video...</span>
                    </div>
                  )}
                  {signedVideoUrl ? (
                    <video
                      key={signedVideoUrl}
                      src={signedVideoUrl}
                      controls
                      autoPlay={false}
                      className="w-full h-full object-contain"
                      onError={() => setSignedVideoUrl(null)}
                    />
                  ) : !videoLoading && videoId && selectedObs && (
                    <img
                      ref={imgRef}
                      src={`/api/video/${videoId}/frame?time=${selectedObs.video_timestamp}`}
                      alt="Evidence Frame"
                      className="w-full h-full object-contain"
                    />
                  )}
                  {aiResults?.frames && imgRef && (
                    <DetectionOverlay 
                      frames={aiResults.frames}
                      potholeEvents={aiResults.pothole_events || (incident.incident_type === 'pothole' ? [{ event_id: incident.id, status: 'CONFIRMED' }] : [])}
                      waterloggingEvents={aiResults.waterlogging_events || (incident.incident_type === 'waterlogging' ? [{ event_id: incident.id, status: 'CONFIRMED' }] : [])}
                      imageRef={imgRef as React.RefObject<HTMLImageElement>}
                      fixedTime={selectedObs.video_timestamp}
                      showVehicles={true}
                      showPotholes={incident.incident_type === 'pothole'}
                      showWaterlogging={incident.incident_type === 'waterlogging'}
                    />
                  )}
                </div>
                <div className="flex justify-between items-center bg-background border border-border/50 rounded p-2 text-xs">
                  <div>
                    <span className="text-[10px] uppercase text-muted-foreground block mb-0.5">Timestamp</span>
                    <span className="font-mono font-bold text-foreground">{selectedObs.video_timestamp.toFixed(2)}s</span>
                  </div>
                  <div className="text-right">
                    <span className="text-[10px] uppercase text-muted-foreground block mb-0.5">Confidence</span>
                    <span className="font-mono font-bold text-foreground">
                      {selectedObs.confidence != null ? `${Math.round(selectedObs.confidence * 100)}%` : 'Unavailable'}
                    </span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-10 px-4 text-center">
                <Video className="h-8 w-8 text-muted-foreground/30 mb-2" />
                <p className="text-sm font-medium text-foreground">No Evidence Selected</p>
                <p className="text-xs text-muted-foreground mt-1">Select an observation below to view canonical evidence.</p>
              </div>
            )}
          </div>
          
          <div className="space-y-2">
            <h4 className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Observation History ({incident.observation_count})</h4>
            {isLoading ? (
              <div className="h-12 bg-secondary/30 rounded border border-border/50 animate-pulse" />
            ) : observationsList.length > 0 ? (
              <div className="space-y-1.5 max-h-48 overflow-y-auto custom-scrollbar pr-1">
                {observationsList.map((obs: any) => (
                  <button
                    key={obs.id}
                    onClick={() => handleJumpToFrame(obs)}
                    className={cn(
                      "w-full text-left p-2.5 rounded border transition-colors flex justify-between items-center group text-xs",
                      selectedObs?.id === obs.id 
                        ? "bg-primary/5 border-primary/30" 
                        : "bg-card border-border hover:bg-secondary/50"
                    )}
                  >
                    <div>
                      <div className="font-medium text-foreground">{obs.route_name || 'Journey'}</div>
                      <div className="text-muted-foreground text-[10px] mt-0.5">
                        {obs.created_at ? formatDistanceToNow(new Date(obs.created_at), { addSuffix: true }) : 'Recent'}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="font-mono font-bold">{obs.video_timestamp.toFixed(1)}s</div>
                      <div className="text-[10px] text-muted-foreground">
                        {obs.confidence != null ? `${Math.round(obs.confidence * 100)}% Conf` : 'Unavailable'}
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            ) : (
              <div className="text-xs text-muted-foreground italic bg-secondary/20 p-3 rounded border border-border/50">
                No observation history recorded.
              </div>
            )}
          </div>
        </section>

        {/* ---------------- INCIDENT DETAILS ---------------- */}
        <section className="space-y-3">
          <h3 className="text-[11px] font-bold text-muted-foreground uppercase tracking-widest border-b border-border pb-1">Incident Details</h3>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="bg-secondary/20 p-3 rounded border border-border/50">
              <span className="text-[10px] uppercase text-muted-foreground font-bold block mb-1">Type</span>
              <span className="capitalize font-medium">{typeLabel}</span>
            </div>
            <div className="bg-secondary/20 p-3 rounded border border-border/50">
              <span className="text-[10px] uppercase text-muted-foreground font-bold block mb-1">Severity</span>
              <span className={cn("font-medium", 
                incident.severity === 'CRITICAL' ? 'text-red-500' :
                incident.severity === 'HIGH' ? 'text-orange-500' :
                incident.severity === 'MEDIUM' ? 'text-yellow-500' : 'text-emerald-500'
              )}>{incident.severity}</span>
            </div>
            <div className="bg-secondary/20 p-3 rounded border border-border/50">
              <span className="text-[10px] uppercase text-muted-foreground font-bold block mb-1 flex items-center gap-1">
                <Calendar className="w-3 h-3" /> First Detected
              </span>
              {incident.timestamp !== undefined && incident.timestamp !== null ? (
                <>
                  <span className="font-mono font-medium">{formatVideoTimestamp(incident.timestamp)}</span>
                  <span className="block text-[9px] text-muted-foreground mt-0.5">Source Video Time</span>
                </>
              ) : (
                <>
                  <span className="font-medium block">{new Date(incident.first_seen_at).toLocaleTimeString()}</span>
                  <span className="block text-[9px] text-muted-foreground mt-0.5">{new Date(incident.first_seen_at).toLocaleDateString()}</span>
                </>
              )}
            </div>
            <div className="bg-secondary/20 p-3 rounded border border-border/50">
              <span className="text-[10px] uppercase text-muted-foreground font-bold block mb-1">Observation Count</span>
              <span className="font-mono font-medium block">{incident.observation_count}</span>
              <span className="block text-[9px] text-muted-foreground mt-0.5">Unique sightings</span>
            </div>
          </div>
        </section>

        {/* ---------------- MAINTENANCE ---------------- */}
        <section className="space-y-3 pb-8">
          <h3 className="text-[11px] font-bold text-muted-foreground uppercase tracking-widest border-b border-border pb-1">Maintenance</h3>
          
          <div className="rounded border border-border bg-card p-4 space-y-4 shadow-sm">
            {!localAction ? (
              <div className="space-y-4">
                <div className="flex justify-between items-center">
                  <div className="text-xs">
                    <span className="block font-bold text-muted-foreground uppercase mb-1">Status</span>
                    <span className="font-medium">UNASSIGNED</span>
                  </div>
                  <div className="text-xs text-right">
                    <span className="block font-bold text-muted-foreground uppercase mb-1">Recommendation</span>
                    <span className="font-medium">{getRecommendedAction(incident.incident_type || (incident as any).type || '')}</span>
                  </div>
                </div>
                {createError && <p className="text-xs text-red-500 bg-red-500/10 p-2 rounded">{createError}</p>}
                <button 
                  onClick={handleCreateWorkOrder} 
                  disabled={isActionLoading}
                  className="w-full py-2 bg-primary text-primary-foreground text-xs font-bold tracking-widest rounded transition-colors hover:bg-primary/90 disabled:opacity-50 flex justify-center items-center gap-2"
                >
                  {isActionLoading && <Loader2 className="w-4 h-4 animate-spin" />}
                  CREATE WORK ORDER & ASSIGN
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-y-3 text-xs">
                  <div>
                    <span className="text-muted-foreground block text-[10px] uppercase font-bold mb-0.5">Status</span>
                    <span className={cn("font-bold px-1.5 py-0.5 rounded-sm inline-block uppercase text-[10px]", 
                      localAction.status === 'ASSIGNED' ? 'bg-blue-500/10 text-blue-500 border border-blue-500/20' :
                      localAction.status === 'IN_PROGRESS' ? 'bg-orange-500/10 text-orange-500 border border-orange-500/20' :
                      localAction.status === 'RESOLVED' ? 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20' :
                      'bg-secondary text-muted-foreground'
                    )}>
                      {localAction.status ? localAction.status.replace('_', ' ') : 'Unknown'}
                    </span>
                  </div>
                  <div>
                    <span className="text-muted-foreground block text-[10px] uppercase font-bold mb-0.5">Work Order</span>
                    <span className="font-mono font-bold">WO-{(localAction.id || '').split('-')[0].toUpperCase()}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground block text-[10px] uppercase font-bold mb-0.5">Department</span>
                    <span className="font-medium">{localAction.assigned_department}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground block text-[10px] uppercase font-bold mb-0.5">Action</span>
                    <span className="font-medium">{localAction.action_type}</span>
                  </div>
                </div>

                {localAction.resolution_note && (
                  <div className="bg-emerald-500/10 border border-emerald-500/20 rounded p-2 text-xs">
                    <span className="text-[10px] font-bold text-emerald-600 uppercase block mb-1">Resolution Note</span>
                    <span className="text-emerald-700 italic">"{localAction.resolution_note}"</span>
                  </div>
                )}

                {/* State Machine Mutations */}
                {localAction.status !== 'RESOLVED' && localAction.status !== 'REJECTED' && (
                  <div className="pt-3 border-t border-border">
                    {!isResolving ? (
                      <div className="flex gap-2">
                        {localAction.status === 'UNASSIGNED' && (
                          <button 
                            disabled={isActionLoading}
                            onClick={() => handleUpdateAction('ASSIGNED')} 
                            className="flex-1 py-1.5 bg-indigo-500 text-white text-[10px] font-bold tracking-widest rounded hover:bg-indigo-600 transition-colors flex justify-center items-center gap-1 shadow-sm"
                          >
                            ASSIGN TEAM
                          </button>
                        )}
                        {localAction.status === 'ASSIGNED' && (
                          <button 
                            disabled={isActionLoading}
                            onClick={() => handleUpdateAction('IN_PROGRESS')} 
                            className="flex-1 py-1.5 bg-blue-500 text-white text-[10px] font-bold tracking-widest rounded hover:bg-blue-600 transition-colors flex justify-center items-center gap-1 shadow-sm"
                          >
                            START WORK
                          </button>
                        )}
                        {(localAction.status === 'ASSIGNED' || localAction.status === 'IN_PROGRESS') && (
                          <button 
                            disabled={isActionLoading}
                            onClick={() => setIsResolving(true)} 
                            className="flex-1 py-1.5 bg-emerald-500 text-white text-[10px] font-bold tracking-widest rounded hover:bg-emerald-600 transition-colors flex justify-center items-center gap-1 shadow-sm"
                          >
                            RESOLVE
                          </button>
                        )}
                      </div>
                    ) : (
                      <div className="space-y-2 animate-in fade-in">
                        <textarea
                          placeholder="Required: Describe the resolution (e.g. Pothole filled)..."
                          className="w-full bg-background border border-border/50 rounded p-2 text-xs focus:outline-none focus:border-emerald-500/50 resize-none h-16"
                          value={resolutionNote}
                          onChange={(e) => setResolutionNote(e.target.value)}
                        />
                        <div className="flex gap-2">
                          <button 
                            onClick={() => handleUpdateAction('RESOLVED', resolutionNote)}
                            disabled={!resolutionNote.trim() || isActionLoading}
                            className="flex-1 py-1.5 bg-emerald-500 text-white text-[10px] font-bold tracking-widest rounded hover:bg-emerald-600 disabled:opacity-50 transition-colors flex justify-center items-center gap-1 shadow-sm"
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
                  </div>
                )}
              </div>
            )}
          </div>
        </section>

      </div>
    </div>
  );
}
