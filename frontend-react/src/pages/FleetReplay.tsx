import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { MapContainer, TileLayer, useMap, Marker } from 'react-leaflet';
import L from 'leaflet';
import { DetectionOverlay } from '@/components/video/DetectionOverlay';
import { type InterpolatedPosition, getPositionAtTime } from '@/utils/routeInterpolation';
import { videoApi } from '@/api/video';
import { Loader2, ArrowLeft, Play, Pause, ShieldAlert, Activity, AlertTriangle, Layers } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { IncidentMarker } from '@/components/map/IncidentMarker';
import { IncidentDrawer } from '@/components/incidents/IncidentDrawer';
import type { MapIncident } from '@/hooks/useMapIntelligence';
import { calculatePriorityScore } from '@/lib/priorityScore';
import { cn } from '@/lib/utils';
import { DynamicRoadLayer, type SegmentIntelligence, type ActiveMapLayer } from '@/components/map/DynamicRoadLayer';

// Haversine distance in meters
function getDistance(lat1: number, lon1: number, lat2: number, lon2: number) {
  const R = 6371e3;
  const p1 = lat1 * Math.PI/180;
  const p2 = lat2 * Math.PI/180;
  const dp = (lat2-lat1) * Math.PI/180;
  const dl = (lon2-lon1) * Math.PI/180;
  const a = Math.sin(dp/2) * Math.sin(dp/2) + Math.cos(p1) * Math.cos(p2) * Math.sin(dl/2) * Math.sin(dl/2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
  return R * c;
}

// Map Bounds Fitter
function MapFitter({ points }: { points: [number, number][] }) {
  const map = useMap();
  useEffect(() => {
    if (points && points.length > 0) {
      const bounds = L.latLngBounds(points);
      map.fitBounds(bounds, { padding: [50, 50] });
    }
  }, [map, points]);
  return null;
}

// Controller for Incident Selection in Replay
function MapController({ selectedIncident }: { selectedIncident: MapIncident | null }) {
  const map = useMap();
  useMemo(() => {
    if (selectedIncident?.latitude && selectedIncident?.longitude) {
      map.flyTo([selectedIncident.latitude, selectedIncident.longitude], 17, { duration: 1.5 });
    }
  }, [selectedIncident, map]);
  return null;
}

// Individual Fleet Journey Video Player
interface FleetJourneyPlayerProps {
  mission: any;
  aiResults: any;
  videoId: string;
  fleetElapsedTime: number;
}
function FleetJourneyPlayer({ mission, aiResults, videoId, fleetElapsedTime }: FleetJourneyPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [videoDuration, setVideoDuration] = useState(0);
  
  const videoStreamUrl = videoId ? videoApi.getStreamUrl(videoId) : null;

  // Throttled sync of video.currentTime to fleetElapsedTime
  const lastSyncTime = useRef(-1);
  useEffect(() => {
    if (videoRef.current && videoDuration > 0) {
      const diff = Math.abs(videoRef.current.currentTime - fleetElapsedTime);
      if (diff > 0.5) {
        videoRef.current.currentTime = fleetElapsedTime;
      }
      
      const now = performance.now();
      if (now - lastSyncTime.current > 100) {
          videoRef.current.currentTime = fleetElapsedTime;
          lastSyncTime.current = now;
      }
    }
  }, [fleetElapsedTime, videoDuration]);

  return (
    <div className="flex gap-4 items-center bg-card p-2 rounded-lg border border-border shadow-sm">
      <div className="relative w-32 aspect-video bg-black rounded overflow-hidden shrink-0 border border-border/50">
        {videoStreamUrl && (
          <video
            ref={videoRef}
            src={videoStreamUrl}
            className="w-full h-full object-cover"
            onLoadedMetadata={(e) => setVideoDuration(e.currentTarget.duration)}
            crossOrigin="anonymous"
            muted
            playsInline
          />
        )}
        {aiResults?.frames && videoRef.current && videoDuration > 0 && (
          <DetectionOverlay 
            frames={aiResults.frames}
            potholeEvents={aiResults.pothole_events}
            waterloggingEvents={aiResults.waterlogging_events}
            videoRef={videoRef as any}
            showVehicles={true}
            showPotholes={true}
            showWaterlogging={true}
          />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="font-bold font-mono text-sm truncate text-primary">{mission.bus_id}</span>
        </div>
        <div className="text-[10px] text-muted-foreground truncate uppercase font-bold tracking-widest">{mission.route_name}</div>
        <div className="text-[10px] font-mono mt-1 text-muted-foreground">TIME: {fleetElapsedTime.toFixed(1)}s</div>
      </div>
    </div>
  );
}

// MAIN FLEET REPLAY
export function FleetReplay() {
  const navigate = useNavigate();
  const FLEET_REPLAY_MATCH_RADIUS_METERS = 25;

  // Global Timeline State
  const [fleetElapsedTime, setFleetElapsedTime] = useState(0);
  const [isPlaying, setIsPlaying] = useState(true);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [maxDuration, setMaxDuration] = useState(100);

  // Map Filter State
  const [activeLayer, setActiveLayer] = useState<ActiveMapLayer>('observed');
  
  // Data State
  const [selectedIncident, setSelectedIncident] = useState<MapIncident | null>(null);

  // Computed State
  const [fleetIncidents, setFleetIncidents] = useState<MapIncident[]>([]);
  const [eventFeed, setEventFeed] = useState<{time: string, message: string, severity: string, busId: string}[]>([]);
  const [segmentIntelligences, setSegmentIntelligences] = useState<Record<string, Record<number, SegmentIntelligence>>>({});
  const [currentPositions, setCurrentPositions] = useState<Record<string, InterpolatedPosition>>({});

  // 1. Intelligent Demo Selection
  const { data: eligibleMissions, isLoading: isLoadingMissions } = useQuery({
    queryKey: ['demo_fleet_missions'],
    queryFn: async () => {
      const res = await fetch('/api/missions');
      const data = await res.json();
      
      const eligible = data.filter((m: any) => m.bus_id && m.video_filename && m.route_name && m.status === 'READY');
      
      const distinctMissions = [];
      const seenBuses = new Set();
      for (const m of eligible) {
        if (!seenBuses.has(m.bus_id)) {
          seenBuses.add(m.bus_id);
          distinctMissions.push(m);
          if (distinctMissions.length === 6) break; // Fetch up to 6
        }
      }
      return distinctMissions;
    }
  });

  // 2. Load all routes and AI data
  const { data: fleetData, isLoading: isLoadingData } = useQuery({
    queryKey: ['fleet_demo_data', eligibleMissions?.map((m: any) => m.id).join(',')],
    queryFn: async () => {
      if (!eligibleMissions) return { results: [], maxLen: 100 };
      const results = [];
      let maxLen = 100;
      for (const mission of eligibleMissions) {
         try {
             const routeRes = await fetch(`/api/missions/${mission.id}/route`);
             let routeData = await routeRes.json();
             
             if (routeData.route_points) {
               routeData.route_points = routeData.route_points.map((p: any) => ({
                 ...p,
                 latitude: p.latitude ?? p.lat,
                 longitude: p.longitude ?? p.lng,
                 timestamp_seconds: p.timestamp_seconds ?? p.timestamp
               }));
             }
             
             const videoId = mission.metadata?.video_id || mission.video_filename?.split('_')[0];
             let aiResults = null;
             try {
                aiResults = await videoApi.getResults(videoId);
                if (aiResults && aiResults.metadata && aiResults.metadata.video_duration) {
                   maxLen = Math.max(maxLen, aiResults.metadata.video_duration);
                }
             } catch(e){}
             
             results.push({
                 mission,
                 routePoints: routeData.route_points || [],
                 aiResults,
                 videoId
             });
         } catch(e) {
             console.error("Failed to load mission data", mission.id, e);
         }
      }
      return { results, maxLen };
    },
    enabled: !!eligibleMissions && eligibleMissions.length > 0
  });

  useEffect(() => {
    if (fleetData?.maxLen) {
      setMaxDuration(fleetData.maxLen);
    }
  }, [fleetData]);

  // 3. Prepare centralized event timeline
  const allEvents = useMemo(() => {
     if (!fleetData?.results) return [];
     let events: any[] = [];
     fleetData.results.forEach(({ mission, aiResults, routePoints }) => {
        if (!aiResults || routePoints.length === 0) return;
        
        // Potholes
        if (aiResults.pothole_events) {
           events = [...events, ...aiResults.pothole_events
             .filter((e: any) => e.max_confidence >= 0.65)
             .map((e: any) => ({ ...e, event_type: 'pothole', timestamp: e.first_seen_timestamp, mission, routePoints }))
           ];
        }
        
        // Waterlogging
        if (aiResults.waterlogging_events) {
           events = [...events, ...aiResults.waterlogging_events
             .filter((e: any) => e.max_confidence >= 0.55)
             .map((e: any) => ({ ...e, event_type: 'waterlogging', timestamp: e.first_seen_timestamp, mission, routePoints }))
           ];
        }
        
        // Traffic
        if (aiResults.density_windows) {
           events = [...events, ...aiResults.density_windows
             .map((e: any) => ({ ...e, event_type: 'traffic', timestamp: e.window_start, first_seen_timestamp: e.window_start, mission, routePoints }))
           ];
        }
     });
     
     return events.sort((a,b) => a.timestamp - b.timestamp);
  }, [fleetData]);

  // 4. Centralized Animation Loop
  const lastFrameTime = useRef(performance.now());
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    if (!isPlaying) {
      lastFrameTime.current = performance.now();
      return;
    }
    const loop = (time: number) => {
      const dt = (time - lastFrameTime.current) / 1000;
      lastFrameTime.current = time;
      
      setFleetElapsedTime(prev => {
        const next = prev + dt * playbackSpeed;
        if (next >= maxDuration) {
          setIsPlaying(false);
          return maxDuration;
        }
        return next;
      });
      rafRef.current = requestAnimationFrame(loop);
    };
    lastFrameTime.current = performance.now();
    rafRef.current = requestAnimationFrame(loop);
    
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    }
  }, [isPlaying, playbackSpeed, maxDuration]);


  // 5. Compute Map State incrementally
  const lastProcessedTime = useRef(-1);
  const [observedRouteKm, setObservedRouteKm] = useState(0);

  // RESET STATE ON DATA CHANGE (P0 / P9 Forensic Fix)
  useEffect(() => {
    setFleetIncidents([]);
    setEventFeed([]);
    setSegmentIntelligences({});
    setCurrentPositions({});
    setFleetElapsedTime(0);
    lastProcessedTime.current = -1;
  }, [fleetData]);

  const rebuildState = useCallback((startTime: number, endTime: number, isReset: boolean) => {
      setFleetIncidents(prevIncidents => {
         let currentIncidents = isReset ? [] : [...prevIncidents];
         let currentFeed = isReset ? [] : [...eventFeed];
         let currentSegInt = isReset ? {} : {...segmentIntelligences};
         
         const eventsInWindow = allEvents.filter(e => e.timestamp > startTime && e.timestamp <= endTime);
         
         for (const ev of eventsInWindow) {
             const evPos = getPositionAtTime(ev.routePoints, ev.timestamp, maxDuration);
             if (!evPos) continue;
             
             // Dynamic Segment Intelligence (P3/P4 Continuous Event Spatial Mapping)
             const mId = ev.mission.id;
             if (!currentSegInt[mId]) currentSegInt[mId] = {};
             
             const startPos = getPositionAtTime(ev.routePoints, ev.first_seen_timestamp || ev.timestamp, maxDuration);
             const endPos = getPositionAtTime(ev.routePoints, ev.last_seen_timestamp || ev.timestamp, maxDuration);
             
             if (startPos && endPos) {
                 for (let seq = startPos.currentSequence; seq <= endPos.currentSequence; seq++) {
                     if (!currentSegInt[mId][seq]) {
                         currentSegInt[mId][seq] = { observed: true, pothole: false, waterlogging: false };
                     }
                     if (ev.event_type === 'pothole') currentSegInt[mId][seq].pothole = true;
                     if (ev.event_type === 'waterlogging') currentSegInt[mId][seq].waterlogging = true;
                 }
             }
             
             // Cross-Bus Consensus
             let matchedIncident: MapIncident | null = null;
             for (const inc of currentIncidents) {
               const dist = getDistance(inc.latitude, inc.longitude, evPos.lat, evPos.lng);
               if (dist <= FLEET_REPLAY_MATCH_RADIUS_METERS && inc.incident_type === ev.event_type) {
                 matchedIncident = inc;
                 break;
               }
             }

             if (matchedIncident) {
               // Update existing
               currentIncidents = currentIncidents.map(inc => {
                 if (inc.id === matchedIncident!.id) {
                   const observedBy = new Set(inc.observed_by);
                   observedBy.add(ev.mission.bus_id);
                   const journeys = new Set((inc as any).journeys || []);
                   journeys.add(ev.mission.id);

                   const updated = {
                     ...inc,
                     observation_count: inc.observation_count + 1,
                     observed_by: Array.from(observedBy),
                     unique_journey_count: journeys.size,
                     dedup_status: observedBy.size >= 2 ? 'CONFIRMED' : inc.dedup_status,
                     last_seen_at: new Date().toISOString(),
                   };
                   (updated as any).journeys = Array.from(journeys);
                   
                   const p = calculatePriorityScore(updated);
                   updated.priority_score = p.score;
                   updated.priority_level = p.level;
                   return updated;
                 }
                 return inc;
               });
               
               currentFeed.unshift({
                  time: `00:${Math.floor(ev.timestamp).toString().padStart(2, '0')}`,
                  message: `Existing ${ev.event_type.replace('_', ' ')} observed again`,
                  severity: 'CONFIRMED',
                  busId: ev.mission.bus_id
               });
             } else {
               // Create new
               const newInc: Partial<MapIncident> = {
                 id: `F-${Date.now()}-${Math.floor(Math.random()*1000)}`,
                 incident_type: ev.event_type,
                 severity: ev.estimated_severity || 'MODERATE',
                 status: 'OPEN',
                 confidence: ev.max_confidence || 0,
                 latitude: evPos.lat,
                 longitude: evPos.lng,
                 observation_count: 1,
                 observed_by: [ev.mission.bus_id],
                 unique_journey_count: 1,
                 dedup_status: 'PENDING',
                 first_seen_at: new Date().toISOString(),
                 last_seen_at: new Date().toISOString(),
                 metadata: { video_id: ev.mission.metadata?.video_id || ev.mission.video_filename?.split('_')[0] }
               } as any;
               (newInc as any).journeys = [ev.mission.id];
               
               const p = calculatePriorityScore(newInc);
               const finalInc = { ...newInc, priority_score: p.score, priority_level: p.level } as MapIncident;
               
               currentIncidents.push(finalInc);
               
               currentFeed.unshift({
                  time: `00:${Math.floor(ev.timestamp).toString().padStart(2, '0')}`,
                  message: `New ${ev.event_type.replace('_', ' ')} detected`,
                  severity: finalInc.severity,
                  busId: ev.mission.bus_id
               });
             }
         }
         
         if (currentFeed.length > 50) currentFeed = currentFeed.slice(0, 50);
         
         setEventFeed(currentFeed);
         setSegmentIntelligences(currentSegInt);
         
         return currentIncidents;
      });
  }, [allEvents, maxDuration]);

  // Handle bus positions and dynamic road layer (Green for observed)
  useEffect(() => {
     if (!fleetData?.results) return;
     
     // Throttled UI updates for positions
     if (Math.abs(fleetElapsedTime - lastProcessedTime.current) > 0.5) {
         
         let currentPositionsLocal: Record<string, InterpolatedPosition> = {};
         let currentSegInt = {...segmentIntelligences};
         let updatedKm = 0;
         
         fleetData.results.forEach(({ mission, routePoints }) => {
            if (routePoints.length === 0) return;
            const pos = getPositionAtTime(routePoints, fleetElapsedTime, maxDuration);
            if (pos) {
               currentPositionsLocal[mission.id] = pos;
               
               // Mark segments up to current as observed (green) unless they are already red/blue
               const mId = mission.id;
               if (!currentSegInt[mId]) currentSegInt[mId] = {};
               for (let i = 0; i <= pos.currentSequence; i++) {
                   if (!currentSegInt[mId][i]) {
                       currentSegInt[mId][i] = { observed: true, pothole: false, waterlogging: false };
                   } else {
                       currentSegInt[mId][i].observed = true;
                   }
               }
               updatedKm += (pos.currentSequence * 0.05); // rough estimate
            }
         });
         
         setCurrentPositions(currentPositionsLocal);
         setSegmentIntelligences(currentSegInt);
         setObservedRouteKm(updatedKm);
     }

     if (fleetElapsedTime < lastProcessedTime.current) {
        // Seek backward
        rebuildState(0, fleetElapsedTime, true);
     } else {
        // Normal playback or forward seek
        rebuildState(lastProcessedTime.current, fleetElapsedTime, false);
     }
     
     lastProcessedTime.current = fleetElapsedTime;
  }, [fleetElapsedTime, fleetData, rebuildState]);

  const allRoutePoints = useMemo(() => {
    let pts: [number, number][] = [];
    if (fleetData?.results) {
      fleetData.results.forEach((r: any) => {
        pts = [...pts, ...r.routePoints.map((p: any) => [p.latitude, p.longitude] as [number, number])];
      });
    }
    return pts;
  }, [fleetData]);

  const getPriorityColor = (level?: string) => {
    switch (level) {
      case 'CRITICAL': return 'text-red-500 bg-red-500/10 border-red-500/20';
      case 'HIGH': return 'text-orange-500 bg-orange-500/10 border-orange-500/20';
      case 'MEDIUM': return 'text-yellow-500 bg-yellow-500/10 border-yellow-500/20';
      default: return 'text-emerald-500 bg-emerald-500/10 border-emerald-500/20';
    }
  };

  if (isLoadingMissions || isLoadingData) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground h-[calc(100vh-2rem)]">
        <Loader2 className="w-8 h-8 animate-spin mb-4 text-primary" />
        <p className="font-mono text-sm tracking-widest uppercase">Initializing Precomputed AI Fleet...</p>
      </div>
    );
  }
  
  const totalBuses = fleetData?.results.length || 0;
  const totalIncidents = fleetIncidents.length;
  const confirmedIncidents = fleetIncidents.filter(i => i.dedup_status === 'CONFIRMED').length;

  return (
    <div className="flex flex-col h-[calc(100vh-2rem)] space-y-4">
      {/* Header & KPI */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button 
            onClick={() => navigate('/map')}
            className="p-2 bg-secondary text-secondary-foreground hover:bg-secondary/80 rounded-md transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold tracking-tight text-foreground">City-Wide Intelligence Demo</h1>
              <span className="text-[10px] font-mono bg-purple-500/20 text-purple-400 px-2 py-0.5 rounded uppercase font-bold tracking-wider border border-purple-500/30 shadow-sm shadow-purple-500/10">AI REPLAY</span>
            </div>
            <p className="text-sm text-muted-foreground mt-1">Cross-bus spatial deduplication from recorded journeys.</p>
          </div>
        </div>
        
        {/* KPI Strip */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 bg-card border border-border/50 rounded-lg shadow-sm">
            <Activity className="w-4 h-4 text-emerald-500 opacity-80" />
            <div className="flex flex-col">
              <span className="text-[9px] uppercase font-bold text-muted-foreground tracking-widest">Active Buses</span>
              <span className="text-sm font-black leading-none">{totalBuses}</span>
            </div>
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 bg-card border border-border/50 rounded-lg shadow-sm">
            <Layers className="w-4 h-4 text-indigo-500 opacity-80" />
            <div className="flex flex-col">
              <span className="text-[9px] uppercase font-bold text-muted-foreground tracking-widest">Observed Road</span>
              <span className="text-sm font-black leading-none">{observedRouteKm.toFixed(1)} km</span>
            </div>
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 bg-card border border-border/50 rounded-lg shadow-sm">
            <ShieldAlert className="w-4 h-4 text-orange-500 opacity-80" />
            <div className="flex flex-col">
              <span className="text-[9px] uppercase font-bold text-muted-foreground tracking-widest">Confirmed Issues</span>
              <span className="text-sm font-black leading-none text-orange-500">{confirmedIncidents} / {totalIncidents}</span>
            </div>
          </div>
        </div>
      </div>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-4 h-full min-h-0">
        
        {/* Left Side: Videos & Feed */}
        <div className="col-span-1 lg:col-span-3 flex flex-col gap-4 overflow-y-auto pr-1 pb-4">
          <div className="grid grid-cols-1 gap-2">
            {fleetData?.results.map((data: any) => (
              <FleetJourneyPlayer 
                 key={data.mission.id}
                 mission={data.mission}
                 aiResults={data.aiResults}
                 videoId={data.videoId}
                 fleetElapsedTime={fleetElapsedTime}
              />
            ))}
          </div>
          
          {/* Feed */}
          <div className="bg-card border border-border rounded-xl flex flex-col flex-1 min-h-[300px] overflow-hidden shadow-sm">
             <div className="p-3 border-b border-border/50 bg-muted/30">
               <h3 className="text-xs font-bold uppercase tracking-widest text-foreground flex items-center gap-2">
                 <AlertTriangle className="w-4 h-4 text-primary" /> Live Replay Events
               </h3>
             </div>
             <div className="flex-1 overflow-y-auto p-2 space-y-2">
               {eventFeed.map((feed, idx) => (
                 <div key={idx} className="flex gap-2 text-sm p-2 bg-muted/30 rounded-lg border border-border/30 animate-in slide-in-from-top-2">
                   <div className="text-[10px] font-mono text-muted-foreground mt-0.5">{feed.time}</div>
                   <div className="flex-1">
                     <div className="flex justify-between items-center">
                        <span className="text-[10px] font-bold text-primary">{feed.busId}</span>
                        <span className={cn("text-[9px] font-black tracking-widest px-1.5 rounded border border-transparent", 
                            feed.severity === 'CONFIRMED' ? 'bg-red-500/10 text-red-500 border-red-500/20' : getPriorityColor(feed.severity)
                        )}>
                            {feed.severity}
                        </span>
                     </div>
                     <p className="text-xs font-medium mt-0.5">{feed.message}</p>
                   </div>
                 </div>
               ))}
               {eventFeed.length === 0 && (
                 <div className="flex flex-col items-center justify-center h-40 text-muted-foreground opacity-60">
                   <p className="text-sm">Waiting for events...</p>
                 </div>
               )}
             </div>
          </div>
        </div>

        {/* Right Side: Map & Playback Controls */}
        <div className="col-span-1 lg:col-span-9 flex flex-col gap-4 min-h-0">
            
          <div className="flex-1 bg-muted border border-border rounded-xl overflow-hidden relative shadow-xl">
            {/* Playback Overlay Controls */}
            <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-[1000] bg-background/95 backdrop-blur-md border border-border shadow-2xl rounded-full px-6 py-3 flex items-center gap-6 transition-all">
                <button onClick={() => setIsPlaying(!isPlaying)} className="w-10 h-10 bg-primary text-primary-foreground rounded-full flex items-center justify-center hover:bg-primary/90 transition-transform hover:scale-105 shadow-lg shadow-primary/20">
                  {isPlaying ? <Pause className="w-5 h-5 fill-current" /> : <Play className="w-5 h-5 fill-current ml-1" />}
                </button>
                
                <div className="flex flex-col gap-1 w-64">
                   <div className="flex justify-between text-[10px] font-mono font-bold text-muted-foreground">
                      <span>{fleetElapsedTime.toFixed(1)}s</span>
                      <span>{maxDuration.toFixed(1)}s</span>
                   </div>
                   <input 
                     type="range" 
                     min={0} 
                     max={maxDuration} 
                     step={0.1}
                     value={fleetElapsedTime}
                     onChange={(e) => {
                       setIsPlaying(false);
                       setFleetElapsedTime(parseFloat(e.target.value));
                     }}
                     className="w-full h-2 bg-secondary rounded-lg appearance-none cursor-pointer accent-primary"
                   />
                </div>
                
                <div className="flex items-center bg-secondary/50 rounded-full p-1 border border-border/50">
                   {[0.5, 1, 2, 4].map(speed => (
                      <button 
                        key={speed}
                        onClick={() => setPlaybackSpeed(speed)}
                        className={cn(
                          "w-8 h-8 rounded-full text-xs font-black flex items-center justify-center transition-colors",
                          playbackSpeed === speed ? "bg-primary text-primary-foreground shadow-sm" : "text-muted-foreground hover:bg-secondary"
                        )}
                      >
                         {speed}x
                      </button>
                   ))}
                </div>
            </div>

            {/* Map Filter Controls */}
            <div className="absolute top-4 left-4 z-[400] flex flex-col gap-2">
              <div className="bg-background/90 backdrop-blur border border-border rounded-lg shadow-md flex flex-col p-1">
                <button onClick={() => setActiveLayer('observed')} className={`px-3 py-1.5 text-xs font-bold rounded-md transition-colors ${activeLayer === 'observed' ? 'bg-primary/20 text-primary' : 'hover:bg-muted text-muted-foreground'}`}>OBSERVED ROAD</button>
                <button onClick={() => setActiveLayer('traffic')} className={`px-3 py-1.5 text-xs font-bold rounded-md transition-colors ${activeLayer === 'traffic' ? 'bg-amber-500/20 text-amber-500' : 'hover:bg-muted text-muted-foreground'}`}>TRAFFIC DENSITY</button>
                <button onClick={() => setActiveLayer('potholes')} className={`px-3 py-1.5 text-xs font-bold rounded-md transition-colors ${activeLayer === 'potholes' ? 'bg-red-500/20 text-red-500' : 'hover:bg-muted text-muted-foreground'}`}>POTHOLES ONLY</button>
                <button onClick={() => setActiveLayer('waterlogging')} className={`px-3 py-1.5 text-xs font-bold rounded-md transition-colors flex items-center justify-between gap-2 ${activeLayer === 'waterlogging' ? 'bg-blue-500/20 text-blue-500' : 'hover:bg-muted text-muted-foreground'}`}>
                  WATERLOGGING <span className="bg-red-500 text-white text-[8px] px-1 rounded-sm tracking-widest font-black">TEST MODE</span>
                </button>
              </div>
            </div>

            <MapContainer 
              center={[26.9124, 75.7873]} 
              zoom={12} 
              className="w-full h-full"
              zoomControl={true}
            >
              <TileLayer
                attribution='&copy; OpenStreetMap contributors'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                maxZoom={19}
              />
              
              <MapFitter points={allRoutePoints} />
              <MapController selectedIncident={selectedIncident} />

              {/* Dynamic Road Layers (One per mission) */}
              {fleetData?.results.map((data: any) => (
                 <DynamicRoadLayer 
                    key={data.mission.id}
                    routePoints={data.routePoints}
                    segmentIntelligence={segmentIntelligences[data.mission.id] || {}}
                    activeLayer={activeLayer}
                 />
              ))}

              {/* Render dynamic markers based on interpolated current positions */}
              {Object.entries(currentPositions).map(([missionId, pos]) => {
                  return (
                     <Marker 
                        key={missionId}
                        position={[pos.lat, pos.lng]}
                        icon={L.divIcon({
                            className: 'custom-bus-marker',
                            html: `<div style="background-color: #3b82f6; width: 12px; height: 12px; border-radius: 50%; border: 2px solid white; box-shadow: 0 0 4px rgba(0,0,0,0.5);"></div>`,
                            iconSize: [12, 12]
                        })}
                     />
                  );
              })}

              {/* Render dynamically merged fleet incidents */}
              {fleetIncidents.map(inc => {
                  if (activeLayer === 'potholes' && inc.incident_type !== 'pothole') return null;
                  if (activeLayer === 'waterlogging' && inc.incident_type !== 'waterlogging') return null;
                  return (
                    <IncidentMarker 
                      key={inc.id} 
                      incident={inc}
                      onClick={() => setSelectedIncident(inc)}
                    />
                  );
              })}
            </MapContainer>

            <IncidentDrawer 
              incident={selectedIncident} 
              onClose={() => setSelectedIncident(null)} 
            />
          </div>
        </div>
      </div>
    </div>
  );
}
