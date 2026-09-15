import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { MapContainer, TileLayer, useMap } from 'react-leaflet';
import L from 'leaflet';
import { SyncBusMarker } from '@/components/map/SyncBusMarker';
import { DetectionOverlay } from '@/components/video/DetectionOverlay';

import { type RoutePoint, type InterpolatedPosition, getPositionAtTime } from '@/utils/routeInterpolation';
import { videoApi } from '@/api/video';
import { Loader2, ArrowLeft, Navigation, MapPin, AlertTriangle } from 'lucide-react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { DynamicRoadLayer, type SegmentIntelligence, type ActiveMapLayer } from '@/components/map/DynamicRoadLayer';
import { IncidentMarker } from '@/components/map/IncidentMarker';
import { IncidentDrawer } from '@/components/incidents/IncidentDrawer';
import type { MapIncident } from '@/hooks/useMapIntelligence';

// Fix for missing default icon paths in leaflet
import iconUrl from 'leaflet/dist/images/marker-icon.png';
import iconRetinaUrl from 'leaflet/dist/images/marker-icon-2x.png';
import shadowUrl from 'leaflet/dist/images/marker-shadow.png';

L.Icon.Default.mergeOptions({
  iconRetinaUrl,
  iconUrl,
  shadowUrl,
});

// Fit bounds to polyline once on load
function MapFitter({ routePoints }: { routePoints: RoutePoint[] }) {
  const map = useMap();
  useEffect(() => {
    if (routePoints && routePoints.length > 0) {
      const bounds = L.latLngBounds(routePoints.map(p => [p.latitude, p.longitude]));
      map.fitBounds(bounds, { padding: [50, 50] });
    }
  }, [map, routePoints]);
  return null;
}

interface JourneyReplayProps {
  missionId: string;
}

export function JourneyReplay({ missionId }: JourneyReplayProps) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const videoRef = useRef<HTMLVideoElement>(null);
  
  const [followBus, setFollowBus] = useState(false);
  const [activeLayer, setActiveLayer] = useState<ActiveMapLayer>('observed');
  const [currentPos, setCurrentPos] = useState<InterpolatedPosition | null>(null);
  const [videoDuration, setVideoDuration] = useState<number>(0);
  
  // Phase 4 Intelligence States
  // Phase 4 Intelligence States
  const [segmentIntelligence, setSegmentIntelligence] = useState<Record<number, SegmentIntelligence>>({});
  const [incidents, setIncidents] = useState<MapIncident[]>([]);
  const [eventFeed, setEventFeed] = useState<{ time: string, message: string, severity: string }[]>([]);
  const [selectedIncident, setSelectedIncident] = useState<MapIncident | null>(null);

  // Fetch Journey Details
  const { data: mission, isLoading: isLoadingMission, error: missionError } = useQuery({
    queryKey: ['mission', missionId],
    queryFn: async () => {
      const res = await fetch(`/api/missions/${missionId}`);
      if (!res.ok) throw new Error('Failed to load journey');
      return res.json();
    }
  });

  // Fetch Route Points
  const { data: routeData, isLoading: isLoadingRoute } = useQuery({
    queryKey: ['mission_route', missionId],
    queryFn: async () => {
      const res = await fetch(`/api/missions/${missionId}/route`);
      if (!res.ok) throw new Error('Failed to load route');
      const data = await res.json();
      // Map backend response keys to RoutePoint interface
      if (data.route_points) {
        data.route_points = data.route_points.map((p: any) => ({
          ...p,
          latitude: p.latitude ?? p.lat,
          longitude: p.longitude ?? p.lng,
          timestamp_seconds: p.timestamp_seconds ?? p.timestamp
        }));
      }
      return data;
    }
  });

  const routePoints: RoutePoint[] = routeData?.route_points || [];
  const hasRoute = routePoints.length > 0;
  
  const videoId = mission?.metadata?.video_id || mission?.video_filename?.split('_')[0];
  const videoStreamUrl = videoId ? videoApi.getStreamUrl(videoId) : null;

  // Fetch AI Results (Precomputed Demo Mode)
  const { data: aiResults } = useQuery({
    queryKey: ['ai_results', videoId],
    queryFn: async () => {
      if (!videoId) return null;
      try {
        const res = await videoApi.getResults(videoId);
        return res;
      } catch (e) {
        return null;
      }
    },
    enabled: !!videoId
  });

  // Auto-seek to timestamp if provided via ?t= param
  useEffect(() => {
    const tParam = searchParams.get('t');
    if (tParam && videoRef.current && videoDuration > 0) {
      const targetTime = parseFloat(tParam);
      if (!isNaN(targetTime)) {
        videoRef.current.currentTime = targetTime;
        videoRef.current.play().catch(() => {}); // Attempt autoplay, ignore error
      }
    }
  }, [searchParams, videoDuration]);

  // Prepare events queue sorted by time
  const aiEvents = useMemo(() => {
    let events: any[] = [];
    if (aiResults?.pothole_events) {
      events = [...events, ...aiResults.pothole_events
        .filter((e: any) => e.max_confidence >= 0.65) // Strict production threshold
        .map((e: any) => ({ ...e, event_type: 'pothole', timestamp: e.first_seen_timestamp }))
      ];
    }
    if (aiResults?.density_windows) {
      events = [...events, ...aiResults.density_windows
        .map((e: any) => ({ ...e, event_type: 'traffic', timestamp: e.window_start, first_seen_timestamp: e.window_start }))
      ];
    }
    if (aiResults?.waterlogging_events) {
      events = [...events, ...aiResults.waterlogging_events
        .filter((e: any) => e.max_confidence >= 0.55) // Strict production threshold for WL
        .map((e: any) => ({ ...e, event_type: 'waterlogging', timestamp: e.first_seen_timestamp }))
      ];
    }
    return events.sort((a, b) => a.timestamp - b.timestamp);
  }, [aiResults]);
  
  const lastEventIndex = useRef(-1);

  // RESET STATE ON VIDEO ID CHANGE (P0 / P9 Forensic Fix)
  useEffect(() => {
    setIncidents([]);
    setSegmentIntelligence({});
    setEventFeed([]);
    lastEventIndex.current = -1;
  }, [videoId]);

  // Throttle state updates for UI performance (react state is slow)
  const lastUpdateTime = useRef(0);
  const handlePositionUpdate = useCallback((pos: InterpolatedPosition) => {
    const now = performance.now();
    
    // Throttle UI React State to ~2Hz (500ms)
    if (now - lastUpdateTime.current > 500) {
      lastUpdateTime.current = now;
      setCurrentPos(pos);

      if (videoRef.current && aiEvents.length > 0) {
        const currentTime = videoRef.current.currentTime;
        
        // Find newly triggered AI events
        let newIncidents: MapIncident[] = [];
        let newHealths: Record<number, SegmentIntelligence> = {};
        let newFeeds = [];
        
        // When seeking backwards, we must reset the event pipeline deterministically
        if (lastEventIndex.current >= 0 && currentTime < aiEvents[lastEventIndex.current].first_seen_timestamp) {
           // Reset state completely when rewinding
           lastEventIndex.current = -1;
           setIncidents([]);
           setSegmentIntelligence({});
           setEventFeed([]);
           return; 
        }
        
        let i = lastEventIndex.current + 1;
        while (i < aiEvents.length && aiEvents[i].timestamp <= currentTime) {
           const ev = aiEvents[i];
           // Calculate exactly where the bus was at this event's timestamp
           const evPos = getPositionAtTime(routePoints, ev.timestamp, videoDuration);
           if (evPos) {
             
             if (ev.event_type === 'pothole' || ev.event_type === 'waterlogging') {
               const incidentPrefix = ev.event_type === 'pothole' ? 'P' : 'W';
               const incidentId = `${incidentPrefix}-${String(i+1).padStart(3, '0')}`;
               // 1. Create Deduplicated MapIncident
               newIncidents.push({
                  id: incidentId,
                  incident_type: ev.event_type,
                  severity: ev.estimated_severity || 'MODERATE',
                  status: 'OPEN',
                  confidence: ev.max_confidence,
                  latitude: evPos.lat,
                  longitude: evPos.lng,
                  observation_count: ev.total_detections || 1,
                  observed_by: [mission?.bus_id || 'DEMO'],
                  dedup_status: 'PENDING',
                  first_seen_at: new Date().toISOString(),
                  last_seen_at: new Date().toISOString(),
                  observations: [{
                    id: `demo-obs-${i}`,
                    mission_id: mission?.id || 'demo',
                    bus_id: mission?.bus_id || 'Demo Bus',
                    video_timestamp: ev.timestamp,
                    confidence: ev.max_confidence,
                    bbox: null,
                    created_at: new Date().toISOString(),
                    route_name: mission?.route_name || 'AI Replay'
                  }]
               });

               // 2. Map Intelligence assignment (P3/P4 Continuous Event Spatial Mapping)
               const startPos = getPositionAtTime(routePoints, ev.first_seen_timestamp || ev.timestamp, videoDuration);
               const endPos = getPositionAtTime(routePoints, ev.last_seen_timestamp || ev.timestamp, videoDuration);
               
               if (startPos && endPos) {
                 for (let seq = startPos.currentSequence; seq <= endPos.currentSequence; seq++) {
                   if (!newHealths[seq]) {
                     newHealths[seq] = { observed: true, pothole: false, waterlogging: false };
                   }
                   if (ev.event_type === 'pothole') newHealths[seq].pothole = true;
                   if (ev.event_type === 'waterlogging') newHealths[seq].waterlogging = true;
                 }
               }

               // 3. Add to Event Feed
               const mm = Math.floor(ev.timestamp / 60).toString().padStart(2, '0');
               const ss = Math.floor(ev.timestamp % 60).toString().padStart(2, '0');
               newFeeds.push({
                 time: `${mm}:${ss}`,
                 message: `${ev.event_type.toUpperCase()} VALIDATED${ev.event_type === 'waterlogging' ? ' (TEST)' : ''}`,
                 severity: ev.estimated_severity || 'MODERATE'
               });
             } else if (ev.event_type === 'traffic') {
               let trafficSeverity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' = 'LOW';
               if (ev.density_level === 'MEDIUM') trafficSeverity = 'MEDIUM';
               if (ev.density_level === 'HIGH') trafficSeverity = 'HIGH';
               if (ev.density_level === 'VERY_HIGH') trafficSeverity = 'CRITICAL';
               
               if (!newHealths[evPos.currentSequence]) {
                 newHealths[evPos.currentSequence] = { observed: true, pothole: false, waterlogging: false };
               }
               newHealths[evPos.currentSequence].trafficDensity = trafficSeverity;

               const mm = Math.floor(ev.timestamp / 60).toString().padStart(2, '0');
               const ss = Math.floor(ev.timestamp % 60).toString().padStart(2, '0');
               newFeeds.push({
                 time: `${mm}:${ss}`,
                 message: `TRAFFIC DENSITY: ${ev.density_level}`,
                 severity: ev.density_level
               });
             }
           }
           lastEventIndex.current = i;
           i++;
        }
        // Update base observed status for all segments we've passed
        let observedUpdates: Record<number, SegmentIntelligence> = {};
        for (let s = 0; s <= pos.currentSequence; s++) {
          observedUpdates[s] = { observed: true, pothole: false, waterlogging: false };
        }

        setSegmentIntelligence(prev => {
          // Merge previous, new base observed, and new AI intelligence
          const next = { ...prev };
          for (let s = 0; s <= pos.currentSequence; s++) {
            if (!next[s]) next[s] = { observed: true, pothole: false, waterlogging: false };
            else next[s].observed = true;
          }
          for (const [seq, intel] of Object.entries(newHealths)) {
            const seqNum = Number(seq);
            if (!next[seqNum]) next[seqNum] = intel;
            else {
              if (intel.pothole) next[seqNum].pothole = true;
              if (intel.waterlogging) next[seqNum].waterlogging = true;
              if (intel.trafficDensity) next[seqNum].trafficDensity = intel.trafficDensity;
            }
          }
          return next;
        });

        if (newIncidents.length > 0) {
          setIncidents(prev => [...prev, ...newIncidents]);
          setEventFeed(prev => [...newFeeds, ...prev].slice(0, 5)); // keep last 5
        } else if (newFeeds.length > 0) {
          setEventFeed(prev => [...newFeeds, ...prev].slice(0, 5));
        }
      }
    }
  }, [aiEvents, routePoints, videoDuration, mission]);

  if (isLoadingMission) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground h-[calc(100vh-2rem)]">
        <Loader2 className="w-8 h-8 animate-spin mb-4 text-primary" />
        <p>Loading journey details...</p>
      </div>
    );
  }

  if (missionError || !mission) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center h-[calc(100vh-2rem)]">
        <div className="bg-destructive/10 text-destructive p-6 rounded-lg border border-destructive/20 text-center max-w-md">
          <p className="font-semibold mb-2">Journey Unavailable</p>
          <p className="text-sm opacity-80">This journey could not be found or failed to load.</p>
          <button onClick={() => navigate('/fleet')} className="mt-4 px-4 py-2 bg-background border border-border rounded-md text-sm text-foreground hover:bg-muted">Return to Fleet</button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-2rem)] space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button 
            onClick={() => navigate('/fleet')}
            className="p-2 bg-secondary text-secondary-foreground hover:bg-secondary/80 rounded-md transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold tracking-tight text-foreground">{mission.route_name}</h1>
              <span className="text-[10px] font-mono bg-purple-500/20 text-purple-400 px-2 py-0.5 rounded uppercase font-bold tracking-wider border border-purple-500/30">AI Replay Mode</span>
            </div>
            <p className="text-sm text-muted-foreground mt-1 font-mono">Bus: {mission.bus_id} | Journey ID: {mission.id.split('-')[0]}</p>
          </div>
        </div>
      </div>
      
      {/* Split Screen Container */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-4 h-full min-h-0">
        
        {/* Left Side: Video & Metrics */}
        <div className="col-span-1 lg:col-span-4 flex flex-col gap-4 overflow-hidden">
          <div className="relative w-full aspect-video bg-black rounded-xl border border-border overflow-hidden shadow-xl shrink-0 group">
            {videoStreamUrl ? (
              <video
                ref={videoRef}
                src={videoStreamUrl}
                className="w-full h-full object-contain"
                controls
                autoPlay={false}
                onLoadedMetadata={(e) => setVideoDuration(e.currentTarget.duration)}
                crossOrigin="anonymous"
              />
            ) : (
              <div className="flex items-center justify-center h-full text-foreground opacity-70 italic">
                Video feed unavailable
              </div>
            )}
            
            {aiResults?.frames && videoRef.current && videoDuration > 0 && (
              <DetectionOverlay 
                frames={aiResults.frames}
                potholeEvents={aiResults.pothole_events}
                waterloggingEvents={aiResults.waterlogging_events}
                videoRef={videoRef as any}
                showVehicles={false}
                showPotholes={activeLayer === 'potholes' || activeLayer === 'observed'}
                showWaterlogging={activeLayer === 'observed' || activeLayer === 'waterlogging'} // Show waterlogging if observed or waterlogging is selected
              />
            )}
            
            {!hasRoute && !isLoadingRoute && (
              <div className="absolute top-4 right-4 bg-amber-500/90 text-black px-3 py-1.5 rounded-md text-xs font-bold shadow-lg flex items-center gap-2">
                <MapPin className="w-3.5 h-3.5" />
                ROUTE NOT ASSIGNED
              </div>
            )}
          </div>

          {/* AI Event Feed */}
          <div className="bg-card border border-border rounded-xl p-5 flex-1 flex flex-col gap-4 min-h-0 shadow-sm overflow-hidden">
            <h3 className="text-xs font-bold uppercase tracking-widest text-muted-foreground border-b border-border/50 pb-2">AI Event Feed</h3>
            
            <div className="flex-1 overflow-y-auto space-y-2 pr-2">
              {eventFeed.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-foreground opacity-60 text-sm">
                  Waiting for events...
                </div>
              ) : (
                eventFeed.map((feed, i) => (
                  <div key={i} className="flex gap-3 bg-muted/50 p-2.5 rounded-lg border border-border/50 text-sm animate-in slide-in-from-top-2">
                    <div className="font-mono text-xs text-muted-foreground mt-0.5">{feed.time}</div>
                    <div>
                      <div className="flex items-center gap-1.5 font-bold tracking-tight">
                        <AlertTriangle className="w-3.5 h-3.5 text-primary" />
                        {feed.message}
                      </div>
                      <div className="text-[10px] font-mono text-muted-foreground uppercase mt-0.5">Severity: <span className="font-bold text-foreground">{feed.severity}</span></div>
                    </div>
                  </div>
                ))
              )}
            </div>
            
            {hasRoute && (
              <div className="pt-3 border-t border-border/50">
                <div className="flex justify-between items-center mb-1">
                  <span className="text-[10px] uppercase font-bold text-muted-foreground">Route Segment</span>
                  <span className="font-mono text-xs font-bold">{currentPos?.currentSequence || 0}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-[10px] uppercase font-bold text-muted-foreground">Active Intelligence</span>
                  <span className="font-mono text-[10px] font-bold px-1.5 py-0.5 rounded bg-muted text-primary">
                    {activeLayer.toUpperCase()}
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right Side: Map */}
        <div className="col-span-1 lg:col-span-8 bg-muted border border-border rounded-xl overflow-hidden relative shadow-xl">
          {isLoadingRoute ? (
            <div className="absolute inset-0 flex items-center justify-center bg-background/50 backdrop-blur z-[1000]">
              <Loader2 className="w-6 h-6 animate-spin text-primary" />
            </div>
          ) : !hasRoute ? (
             <div className="absolute inset-0 flex flex-col items-center justify-center bg-background/95 z-[1000] text-muted-foreground border-border border-dashed border-2 m-8 rounded-2xl">
               <MapPin className="w-12 h-12 mb-4 opacity-50" />
               <h2 className="text-lg font-semibold">Route Not Assigned</h2>
               <p className="text-sm mt-1 max-w-xs text-center opacity-70">This journey was created without GPS route mapping. The map feature is disabled.</p>
             </div>
          ) : (
            <>
              {/* Floating map controls */}
              <div className="absolute top-4 left-4 z-[400] flex flex-col gap-2">
                <button
                  onClick={() => setFollowBus(!followBus)}
                  className={`px-3 py-1.5 rounded-full text-xs font-bold shadow-md transition-colors border flex items-center gap-1.5 self-start
                    ${followBus ? 'bg-primary text-primary-foreground border-primary' : 'bg-card text-foreground border-border hover:bg-secondary'}`}
                >
                  <Navigation className={`w-3.5 h-3.5 ${followBus ? 'animate-pulse' : ''}`} />
                  {followBus ? 'FOLLOWING BUS' : 'FOLLOW BUS'}
                </button>

                <div className="bg-background/90 backdrop-blur border border-border rounded-lg shadow-md flex flex-col mt-2 p-1">
                  <button onClick={() => setActiveLayer('observed')} className={`px-3 py-1.5 text-xs font-bold rounded-md transition-colors ${activeLayer === 'observed' ? 'bg-primary/20 text-primary' : 'hover:bg-muted text-foreground opacity-80 hover:opacity-100'}`}>OBSERVED ROAD</button>
                  <button onClick={() => setActiveLayer('traffic')} className={`px-3 py-1.5 text-xs font-bold rounded-md transition-colors ${activeLayer === 'traffic' ? 'bg-amber-500/20 text-amber-500' : 'hover:bg-muted text-foreground opacity-80 hover:opacity-100'}`}>TRAFFIC DENSITY</button>
                  <button onClick={() => setActiveLayer('potholes')} className={`px-3 py-1.5 text-xs font-bold rounded-md transition-colors ${activeLayer === 'potholes' ? 'bg-red-500/20 text-red-500' : 'hover:bg-muted text-foreground opacity-80 hover:opacity-100'}`}>POTHOLES ONLY</button>
                  <button onClick={() => setActiveLayer('waterlogging')} className={`px-3 py-1.5 text-xs font-bold rounded-md transition-colors ${activeLayer === 'waterlogging' ? 'bg-blue-500/20 text-blue-500' : 'hover:bg-muted text-foreground opacity-80 hover:opacity-100'}`}>WATERLOGGING (TEST)</button>
                </div>
              </div>

              <MapContainer 
                center={[26.9124, 75.7873]} 
                zoom={12} 
                className="w-full h-full"
                zoomControl={true}
              >
                <TileLayer
                  attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                  maxZoom={19}
                />

                <MapFitter routePoints={routePoints} />
                
                {/* Dynamically painted route geometry based on observations and segment intelligence */}
                <DynamicRoadLayer 
                  routePoints={routePoints} 
                  segmentIntelligence={segmentIntelligence} 
                  activeLayer={activeLayer}
                />
                
                {/* Validated AI Incidents (Secondary layer) */}
                {['observed', 'potholes'].includes(activeLayer) && incidents.filter(i => i.incident_type === 'pothole').map(inc => (
                  <IncidentMarker 
                    key={inc.id} 
                    incident={inc}
                    onClick={() => setSelectedIncident(inc)}
                  />
                ))}
                
                {['observed', 'waterlogging'].includes(activeLayer) && incidents.filter(i => i.incident_type === 'waterlogging').map(inc => (
                  <IncidentMarker 
                    key={inc.id} 
                    incident={inc}
                    onClick={() => setSelectedIncident(inc)}
                  />
                ))}

                {/* Highly optimized moving bus marker (High Frequency RAF Loop) */}
                <SyncBusMarker 
                  videoRef={videoRef}
                  routePoints={routePoints}
                  videoDuration={videoDuration}
                  onPositionUpdate={handlePositionUpdate}
                  followBus={followBus}
                />
              </MapContainer>
            </>
          )}

          {/* Evidence Trail / Incident Drawer */}
          <IncidentDrawer 
            incident={selectedIncident} 
            onClose={() => setSelectedIncident(null)} 
          />
        </div>
      </div>
    </div>
  );
}
