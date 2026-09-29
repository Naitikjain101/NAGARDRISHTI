import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { fleetApi, type Journey } from '@/api/fleet';
import { videoApi } from '@/api/video';
import { PageHeader } from '@/components/ui/PageHeader';
import { Button } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { useToast } from '@/components/ui/Toast';
import { Activity, RotateCcw, Video, MapPin, Navigation, Clock, ShieldCheck, ActivitySquare, AlertTriangle, Droplets, Loader2 } from 'lucide-react';
import { VideoPlayer } from '@/components/video/VideoPlayer';
import { TrafficDensityPanel } from '@/components/video/TrafficDensityPanel';
import { MapContainer, TileLayer, useMap } from 'react-leaflet';
import L from 'leaflet';
import { SyncBusMarker } from '@/components/map/SyncBusMarker';
import { DynamicRoadLayer, type SegmentIntelligence, type ActiveMapLayer } from '@/components/map/DynamicRoadLayer';
import { IncidentMarker } from '@/components/map/IncidentMarker';
import { type RoutePoint, getPositionAtTime } from '@/utils/routeInterpolation';
import type { MapIncident } from '@/hooks/useMapIntelligence';
import { IncidentDrawer } from '@/components/incidents/IncidentDrawer';

import iconUrl from 'leaflet/dist/images/marker-icon.png';
import iconRetinaUrl from 'leaflet/dist/images/marker-icon-2x.png';
import shadowUrl from 'leaflet/dist/images/marker-shadow.png';
import { fetchRaw } from '../api/client';
import { useVideoStreamUrl } from '@/hooks/useVideoStreamUrl';

L.Icon.Default.mergeOptions({
  iconRetinaUrl,
  iconUrl,
  shadowUrl,
});

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

export function LiveMonitoring() {
  const queryClient = useQueryClient();
  const toast = useToast();
  
  const [isResetConfirmOpen, setIsResetConfirmOpen] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  
  const [selectedJourneyId, setSelectedJourneyId] = useState<string | null>(null);
  const [selectedIncident, setSelectedIncident] = useState<MapIncident | null>(null);
  
  // Feed/Playback state
  const [currentTime, setCurrentTime] = useState<number>(0);
  const [videoDuration, setVideoDuration] = useState<number>(0);
  
  // Incident & Map State
  const [segmentIntelligence, setSegmentIntelligence] = useState<Record<number, SegmentIntelligence>>({});
  const [activeLayer, setActiveLayer] = useState<ActiveMapLayer>('observed');
  const [followBus] = useState(true);

  // 1. Fetch Fleet for READY journeys
  const { data: buses } = useQuery({
    queryKey: ['fleet'],
    queryFn: fleetApi.getBuses,
    refetchInterval: 5000,
  });

  const readyJourneys: Journey[] = useMemo(() => {
    const journeys: Journey[] = [];
    if (buses) {
      buses.forEach(bus => {
        if (bus.journeys) {
          bus.journeys.forEach(j => {
            if (j.status.toUpperCase() === 'READY') {
              journeys.push(j);
            }
          });
        }
      });
    }
    return journeys;
  }, [buses]);
  
  // Select first ready journey by default if none selected
  useEffect(() => {
    if (!selectedJourneyId && readyJourneys.length > 0) {
      setSelectedJourneyId(readyJourneys[0].id);
    }
  }, [readyJourneys, selectedJourneyId]);

  const selectedJourney = readyJourneys.find(j => j.id === selectedJourneyId);
  const videoId = selectedJourney?.metadata?.video_id || selectedJourney?.video_filename?.split('_')[0];
  const { url: videoStreamUrl, isLoading: isVideoUrlLoading, error: videoUrlError } = useVideoStreamUrl(videoId);

  // 2. Fetch Journey Route
  const { data: routeData } = useQuery({
    queryKey: ['mission_route', selectedJourneyId],
    queryFn: async () => {
      if (!selectedJourneyId) return null;
      const res = await fetchRaw(`/api/missions/${selectedJourneyId}/route`);
      if (!res.ok) throw new Error('Failed to load route');
      const data = await res.json();
      if (data.route_points) {
        data.route_points = data.route_points.map((p: any) => ({
          ...p,
          latitude: p.latitude ?? p.lat,
          longitude: p.longitude ?? p.lng,
          timestamp_seconds: p.timestamp_seconds ?? p.timestamp
        }));
      }
      return data;
    },
    enabled: !!selectedJourneyId
  });

  const routePoints: RoutePoint[] = routeData?.route_points || [];

  // 3. Fetch canonical AI Results
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
    enabled: !!videoId
  });

  // Combine & sort AI events for incident generation
  const aiEvents = useMemo(() => {
    let events: any[] = [];
    if (aiResults?.pothole_events) {
      events = [...events, ...aiResults.pothole_events
        .filter((e: any) => e.max_confidence >= 0.65)
        .map((e: any) => ({ ...e, event_type: 'pothole', timestamp: e.first_seen_timestamp }))
      ];
    }
    if (aiResults?.waterlogging_events) {
      const wEvents = aiResults.waterlogging_events.filter((e: any) => e.max_confidence >= 0.55);
      wEvents.forEach((e: any) => {
        // Generate just ONE event for the entire waterlogging duration, placed at the start
        events.push({ ...e, event_type: 'waterlogging', timestamp: e.first_seen_timestamp, event_id: e.event_id });
      });
    }
    return events.sort((a, b) => a.timestamp - b.timestamp);
  }, [aiResults]);

  // 4. Fetch Canonical DB Incidents for this journey
  const { data: dbIncidents } = useQuery<MapIncident[]>({
    queryKey: ['mission_incidents', selectedJourneyId],
    queryFn: async () => {
      if (!selectedJourneyId) return [];
      // Fetch incidents ONLY for this specific mission
      const res = await fetchRaw(`/api/missions/${selectedJourneyId}/incidents?_t=${Date.now()}`);
      if (!res.ok) return [];
      const data = await res.json();
      // Filter by mission_id
      const items = Array.isArray(data) ? data : data.incidents || data.items || data.data || [];
      return items.filter((i: any) => i.metadata?.mission_id === selectedJourneyId || i.source_mission_id === selectedJourneyId).map((inc: any) => ({
        id: inc.id,
        incident_type: inc.incident_type,
        severity: inc.severity,
        status: inc.status,
        confidence: inc.confidence,
        latitude: inc.latitude,
        longitude: inc.longitude,
        observation_count: inc.observation_count,
        observed_by: inc.observed_by || [inc.bus_id],
        first_seen_at: inc.first_seen_at || inc.created_at,
        last_seen_at: inc.last_seen_at || inc.created_at,
        dedup_status: inc.dedup_status || 'PENDING',
        action: null,
        metadata: inc.metadata,
        tracking_id: inc.tracking_id
      }));
    },
    enabled: !!selectedJourneyId,
    refetchInterval: 2000
  });

  const displayedIncidents = useMemo(() => {
    if (!dbIncidents) return [];
    return dbIncidents.filter(inc => {
      const incTime = inc.metadata?.video_time_sec || 0;
      return currentTime >= incTime;
    });
  }, [dbIncidents, currentTime]);

  const lastTime = useRef<number>(-1);
  const processedEventsRef = useRef<Set<string>>(new Set());

  // Prevent duplicate insertion by populating processed events from DB
  useEffect(() => {
    if (dbIncidents) {
      dbIncidents.forEach(inc => {
        const tId = inc.metadata?.tracking_id || (inc as any).tracking_id || (inc as any).event_id;
        if (tId) {
          processedEventsRef.current.add(String(tId));
        }
      });
    }
  }, [dbIncidents]);

  // Reset local state when journey changes
  useEffect(() => {
    setSegmentIntelligence({});
    lastTime.current = -1;
    processedEventsRef.current.clear();
    setCurrentTime(0);
  }, [selectedJourneyId]);
  
  // Use results.frames to infer duration if metadata hasn't loaded yet
  useEffect(() => {
    if (aiResults?.frames?.length > 0 && videoDuration === 0) {
      setVideoDuration(aiResults.frames[aiResults.frames.length - 1].timestamp);
    }
  }, [aiResults, videoDuration]);

  // 4. Time Update Logic (Generates Incidents)
  const handleTimeUpdate = useCallback(async (time: number) => {
    setCurrentTime(time);
    
    // When seeking backwards, reset idempotency set so we don't double-fire but allow re-firing if needed.
    // Wait, the user said: "Repeated playback must NOT create duplicate incidents."
    // Because we use `upsert` on the backend with a fixed ID (`demo_${missionId}_${event.event_id}`),
    // we can safely fire it again, but avoiding network spam is good.
    // If they seek back, we just let it be. If they seek far back, maybe clear `processedEvents` 
    // so they trigger the POST again for visual feedback? 
    // Actually, letting `processedEvents` persist is safer. It won't spam.
    if (time < lastTime.current) {
      // Seek backward happened.
    }
    lastTime.current = time;

    // We only process if we have a journey and route points
    if (!selectedJourneyId || routePoints.length === 0 || !aiResults) return;

    const currentInterpolatedPos = getPositionAtTime(routePoints, time, videoDuration);
    if (currentInterpolatedPos) {
      const seq = currentInterpolatedPos.currentSequence;
      
      // Find matching traffic density window
      const densityWindows = aiResults?.density_windows || [];
      const activeWindow = densityWindows.find((w: any) => time >= w.window_start && time <= w.window_end)
        || densityWindows.filter((w: any) => w.window_start <= time).sort((a: any, b: any) => b.window_start - a.window_start)[0]
        || null;
      const trafficDensity: SegmentIntelligence['trafficDensity'] = activeWindow
        ? (activeWindow.density_level?.toUpperCase() as SegmentIntelligence['trafficDensity'])
        : undefined;

      // Update road segment observed intelligence
      setSegmentIntelligence(prev => {
        const next = { ...prev };
        for (let s = 0; s <= seq; s++) {
          if (!next[s]) next[s] = { observed: true, pothole: false, waterlogging: false, trafficDensity };
          else { next[s].observed = true; if (trafficDensity) next[s].trafficDensity = trafficDensity; }
        }
        return next;
      });
    }

    // Update road segment hazard intelligence more accurately based on duration
    const updates: Record<number, Partial<SegmentIntelligence>> = {};

    if (aiResults?.pothole_events) {
      for (const ev of aiResults.pothole_events) {
         if (ev.max_confidence >= 0.65 && time >= ev.first_seen_timestamp) {
             const evPos = getPositionAtTime(routePoints, ev.first_seen_timestamp, videoDuration);
             if (evPos) updates[evPos.currentSequence] = { pothole: true };
         }
      }
    }
    
    if (aiResults?.waterlogging_events) {
      for (const ev of aiResults.waterlogging_events) {
         if (ev.max_confidence >= 0.55 && time >= ev.first_seen_timestamp) {
             // For waterlogging, we highlight the entire duration
             const startPos = getPositionAtTime(routePoints, ev.first_seen_timestamp, videoDuration);
             // We restrict the end highlight up to the current time, so the line fills up realistically as the bus drives
             const endTimestampToHighlight = Math.min(time, ev.last_seen_timestamp || ev.first_seen_timestamp);
             const endPos = getPositionAtTime(routePoints, endTimestampToHighlight, videoDuration);
             if (startPos && endPos) {
                 for (let s = startPos.currentSequence; s <= endPos.currentSequence; s++) {
                     updates[s] = { ...updates[s], waterlogging: true };
                 }
             }
         }
      }
    }

    if (Object.keys(updates).length > 0) {
       setSegmentIntelligence(prev => {
         const next = { ...prev };
         for (const [s, data] of Object.entries(updates)) {
             const seq = parseInt(s);
             if (!next[seq]) next[seq] = { observed: true, pothole: false, waterlogging: false };
             if (data.pothole) next[seq].pothole = true;
             if (data.waterlogging) next[seq].waterlogging = true;
         }
         return next;
       });
    }

    // Auto-save incidents to database via POST
    for (const ev of aiEvents) {
      if (time >= ev.timestamp) {
        if (!processedEventsRef.current.has(String(ev.event_id))) {
          const evPos = getPositionAtTime(routePoints, ev.timestamp, videoDuration);
          processedEventsRef.current.add(String(ev.event_id));
          
          fetchRaw('/api/incidents/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              // We omit 'id' so Supabase auto-generates a UUID
              source_mission_id: selectedJourneyId,
              incident_type: ev.event_type,
              severity: ev.max_confidence >= 0.8 ? 'HIGH' : 'MEDIUM',
              status: 'OPEN',
              latitude: evPos?.lat || routePoints[0]?.latitude || 26.9124,
              longitude: evPos?.lng || routePoints[0]?.longitude || 75.7873,
              confidence: ev.max_confidence,
              first_seen_at: new Date().toISOString(),
              tracking_id: String(ev.event_id),
              metadata: { 
                is_demo: "true", 
                video_time_sec: ev.first_seen_timestamp || ev.timestamp, 
                last_video_time_sec: ev.last_seen_timestamp || ev.first_seen_timestamp || ev.timestamp,
                video_id: aiResults.video?.id || aiResults.video?.filename,
                mission_id: selectedJourneyId 
              },
              observation: {
                mission_id: selectedJourneyId,
                video_filename: aiResults.video?.id || aiResults.video?.filename,
                video_timestamp: ev.timestamp,
                confidence: ev.max_confidence,
                bbox: ev.representative_bbox || ev.bbox,
                bus_id: selectedJourney?.bus_id,
                metadata: { is_demo: "true" }
              }
            })
          }).then(res => {
            if (res.ok) {
              queryClient.invalidateQueries({ queryKey: ['map_incidents'] });
            }
          }).catch(console.error);
        }
      }
    }
  }, [selectedJourneyId, routePoints, videoDuration, aiResults, aiEvents, selectedJourney, toast, queryClient]);

  const handleReset = async () => {
    setIsResetting(true);
    try {
      const res = await fetchRaw('/api/missions/reset', { method: 'POST' });
      if (res.ok) {
        queryClient.invalidateQueries({ queryKey: ['fleet'] });
        queryClient.invalidateQueries({ queryKey: ['map_incidents'] });
        queryClient.invalidateQueries({ queryKey: ['mission_incidents'] });
        processedEventsRef.current.clear();
        
        toast.success('Session reset', 'Live Monitoring session reset and demo incidents cleared.');
        setSelectedJourneyId(null);
      } else {
        throw new Error('Reset failed');
      }
    } catch (e) {
      toast.error('Reset failed', 'Unable to reset the session. Please try again.');
    } finally {
      setIsResetting(false);
      setIsResetConfirmOpen(false);
    }
  };

  return (
    <div className="page-content h-[calc(100vh-2rem)] flex flex-col min-h-0">
      <PageHeader
        title="Live Monitoring"
        description="Replay AI-processed survey journeys and generate live incident alerts."
        icon={ActivitySquare}
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              icon={RotateCcw}
              onClick={() => setIsResetConfirmOpen(true)}
              className="text-destructive border-destructive/30 hover:bg-red-50"
            >
              Reset Demo Session
            </Button>
          </div>
        }
      />

      <div className="flex-1 flex gap-4 min-h-0 overflow-hidden">
        {/* Left Sidebar: Ready Journeys */}
        <div className="w-80 flex flex-col gap-3 overflow-y-auto pr-2 custom-scrollbar shrink-0">
          <h3 className="text-sm font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
            <ShieldCheck className="w-4 h-4" /> Prepared Journeys
          </h3>
          
          {readyJourneys.length === 0 ? (
            <EmptyState
              icon={Video}
              title="No Ready Journeys"
              description="Process a video in Fleet and add it to Live Monitoring."
              className="bg-card border-dashed py-8 mt-4"
            />
          ) : (
            readyJourneys.map(journey => (
              <div
                key={journey.id}
                onClick={() => setSelectedJourneyId(journey.id)}
                className={`p-3 rounded-xl border cursor-pointer transition-all ${
                  selectedJourneyId === journey.id 
                    ? 'bg-primary/5 border-primary shadow-sm ring-1 ring-primary/20' 
                    : 'bg-card border-border hover:border-primary/50 hover:bg-secondary/30'
                }`}
              >
                <div className="flex justify-between items-start mb-2">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                    <span className="font-bold text-sm text-foreground">{journey.bus_id}</span>
                  </div>
                  <span className="text-[10px] font-bold uppercase tracking-wider text-green-600 bg-green-50 px-1.5 py-0.5 rounded border border-green-200">
                    READY
                  </span>
                </div>
                <div className="text-xs text-muted-foreground font-mono space-y-1">
                  <div className="flex items-center gap-1.5"><Navigation className="w-3.5 h-3.5" /> {journey.route_name || 'Urban Route'}</div>
                  <div className="flex items-center gap-1.5"><Clock className="w-3.5 h-3.5" /> Demo AI Replay</div>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Main Dashboard Area */}
        {selectedJourney ? (
          <div className="flex-1 flex flex-col min-h-0 bg-background rounded-xl border border-border shadow-sm overflow-hidden relative">
            
            {/* Top Pane: Video & Map */}
            <div className="flex-[3] flex flex-row min-h-0 border-b border-border">
              {/* Video Player */}
              <div className="flex-1 bg-black relative flex flex-col justify-center min-w-0 border-r border-border">
                {isVideoUrlLoading && (
                  <div className="text-white/50 text-center text-sm font-mono flex flex-col items-center justify-center h-full">
                    <Loader2 className="w-8 h-8 mb-2 animate-spin text-primary" />
                    Loading Stream...
                  </div>
                )}
                {videoStreamUrl ? (
                  <VideoPlayer 
                    src={videoStreamUrl}
                    results={aiResults}
                    onTimeUpdate={handleTimeUpdate}
                  />
                ) : !isVideoUrlLoading && (
                  <div className="text-white/50 text-center text-sm font-mono flex flex-col items-center">
                    <Video className="w-8 h-8 mb-2 opacity-50" />
                    {videoUrlError ? (
                      <>
                        <span className="text-red-400 mb-1">Failed to load video</span>
                        <span className="text-[10px] text-white/30">{videoUrlError}</span>
                        <span className="text-[10px] text-white/20 mt-1">Video ID: {videoId || 'none'}</span>
                      </>
                    ) : (
                      <span>No video available</span>
                    )}
                  </div>
                )}
              </div>

              {/* Map */}
              <div className="flex-1 relative z-0 flex flex-col min-h-0">
                <div className="flex-1 relative z-0">
                  {routePoints.length > 0 ? (
                    <MapContainer 
                      center={[26.9124, 75.7873]} 
                      zoom={13} 
                      className="w-full h-full"
                      zoomControl={false}
                    >
                      <TileLayer
                        attribution='&copy; OpenStreetMap'
                        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                        maxZoom={19}
                      />
                      <MapFitter routePoints={routePoints} />
                      <DynamicRoadLayer 
                        routePoints={routePoints} 
                        segmentIntelligence={segmentIntelligence} 
                        activeLayer={activeLayer}
                        onChunkClick={(latlng) => {
                          if (displayedIncidents.length > 0) {
                             let nearest = displayedIncidents[0];
                             let minDist = Infinity;
                             for (const inc of displayedIncidents) {
                               const dist = Math.pow(inc.latitude - latlng.lat, 2) + Math.pow(inc.longitude - latlng.lng, 2);
                               if (dist < minDist) {
                                  minDist = dist;
                                  nearest = inc;
                               }
                             }
                             setSelectedIncident(nearest);
                          }
                        }}
                      />
                      {displayedIncidents.map(inc => (
                        <IncidentMarker 
                          key={inc.id} 
                          incident={inc}
                          onClick={setSelectedIncident}
                        />
                      ))}
                      <SyncBusMarker 
                        videoRef={{ current: { currentTime, duration: videoDuration } } as any}
                        routePoints={routePoints}
                        videoDuration={videoDuration}
                        onPositionUpdate={() => {}}
                        followBus={followBus}
                      />
                    </MapContainer>
                  ) : (
                    <div className="w-full h-full bg-secondary flex flex-col items-center justify-center text-muted-foreground">
                      <MapPin className="w-8 h-8 opacity-50 mb-2" />
                      <span className="text-sm">No GPS Route Available</span>
                    </div>
                  )}
                  
                  {/* Real-time Detections Overlay */}
                  <div className="absolute top-4 left-4 z-[400] flex flex-col gap-2">
                    <div className="bg-background/95 backdrop-blur border border-border p-3 rounded-lg shadow-md min-w-[200px]">
                      <h4 className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest mb-2 border-b border-border/50 pb-1">Real-time Detections</h4>
                      <div className="space-y-2 text-xs">
                        <div className="flex justify-between">
                          <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.5)]"></span>Potholes</span>
                          <span className="font-mono font-bold">{displayedIncidents.filter(i => (i.incident_type || i.type) === 'pothole').length}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.5)]"></span>Waterlogging</span>
                          <span className="font-mono font-bold">{displayedIncidents.filter(i => (i.incident_type || i.type) === 'waterlogging').length}</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Map Controls */}
                  <div className="absolute top-4 right-4 z-[400] flex flex-col gap-2">
                    <div className="bg-background/95 backdrop-blur border border-border rounded-lg shadow-md flex overflow-hidden">
                      <button onClick={() => setActiveLayer('observed')} className={`px-3 py-1.5 text-[10px] font-bold transition-colors ${activeLayer === 'observed' ? 'bg-primary text-primary-foreground' : 'hover:bg-muted text-foreground'}`}>ROADS</button>
                      <button onClick={() => setActiveLayer('traffic')} className={`px-3 py-1.5 text-[10px] font-bold transition-colors border-l border-border ${activeLayer === 'traffic' ? 'bg-amber-500 text-white' : 'hover:bg-muted text-foreground'}`}>TRAFFIC</button>
                      <button onClick={() => setActiveLayer('potholes')} className={`px-3 py-1.5 text-[10px] font-bold transition-colors border-l border-border ${activeLayer === 'potholes' ? 'bg-red-500 text-white' : 'hover:bg-muted text-foreground'}`}>POTHOLES</button>
                      <button onClick={() => setActiveLayer('waterlogging')} className={`px-3 py-1.5 text-[10px] font-bold transition-colors border-l border-border ${activeLayer === 'waterlogging' ? 'bg-blue-500 text-white' : 'hover:bg-muted text-foreground'}`}>WATER</button>
                    </div>
                    {/* Legend */}
                    <div className="bg-background/95 backdrop-blur border border-border rounded-lg shadow-md p-2 flex flex-col gap-1.5 text-[9px] font-bold uppercase tracking-wider">
                      {activeLayer === 'traffic' ? (
                        <>
                          <div className="flex items-center gap-1.5"><span className="inline-block w-4 h-2 rounded" style={{background:'#facc15'}} />Low</div>
                          <div className="flex items-center gap-1.5"><span className="inline-block w-4 h-2 rounded" style={{background:'#f97316'}} />Medium</div>
                          <div className="flex items-center gap-1.5"><span className="inline-block w-4 h-2 rounded" style={{background:'#ef4444'}} />High</div>
                          <div className="flex items-center gap-1.5"><span className="inline-block w-4 h-2 rounded" style={{background:'#7f1d1d'}} />Critical</div>
                        </>
                      ) : activeLayer === 'potholes' ? (
                        <>
                          <div className="flex items-center gap-1.5"><span className="inline-block w-4 h-2 rounded bg-red-500" />Pothole</div>
                          <div className="flex items-center gap-1.5"><span className="inline-block w-4 h-2 rounded bg-green-500" />Clear</div>
                        </>
                      ) : activeLayer === 'waterlogging' ? (
                        <>
                          <div className="flex items-center gap-1.5"><span className="inline-block w-4 h-2 rounded bg-blue-500" />Waterlogged</div>
                          <div className="flex items-center gap-1.5"><span className="inline-block w-4 h-2 rounded bg-green-500" />Clear</div>
                        </>
                      ) : (
                        <>
                          <div className="flex items-center gap-1.5"><span className="inline-block w-4 h-2 rounded bg-green-500" />Clear</div>
                          <div className="flex items-center gap-1.5"><span className="inline-block w-4 h-2 rounded bg-red-500" />Pothole</div>
                          <div className="flex items-center gap-1.5"><span className="inline-block w-4 h-2 rounded bg-blue-500" />Waterlog</div>
                          <div className="flex items-center gap-1.5"><span className="inline-block w-4 h-2 rounded bg-slate-500" />Unscanned</div>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Bottom Pane: System Intelligence */}
            <div className="flex-[2] bg-card flex flex-col min-h-0 shrink-0 z-10">
              <div className="p-2 px-4 border-b border-border bg-secondary/30 flex justify-between items-center shrink-0">
                <h3 className="font-bold text-sm">System Intelligence</h3>
                <span className="text-[10px] font-mono px-2 py-0.5 bg-blue-100 text-blue-700 rounded border border-blue-200">LIVE FEED</span>
              </div>
              
              <div className="flex-1 flex flex-row min-h-0 p-3 gap-6 overflow-hidden">
                
                {/* Column 1: Traffic Density Panel */}
                <div className="flex-1 flex flex-col min-h-0 border-r border-border pr-6">
                  {aiResults ? (
                    <TrafficDensityPanel
                      currentTime={currentTime}
                      results={aiResults}
                    />
                  ) : (
                    <div className="h-full flex items-center justify-center text-xs text-muted-foreground italic">
                      Traffic density unavailable.
                    </div>
                  )}
                </div>

                {/* Column 2: Live Detections */}
                <div className="w-64 flex flex-col min-h-0 shrink-0 border-r border-border pr-6">
                  <h4 className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground mb-3">Live Detections</h4>
                  <div className="flex flex-col gap-3">
                    <div className="bg-secondary/30 rounded-lg p-3 flex items-center justify-between border border-border">
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-orange-500"></div>
                        <span className="text-xs uppercase font-bold text-foreground">Potholes</span>
                      </div>
                      <span className="text-2xl font-black text-orange-500">{displayedIncidents.filter(i => (i.incident_type || i.type) === 'pothole').length}</span>
                    </div>
                    <div className="bg-secondary/30 rounded-lg p-3 flex items-center justify-between border border-border">
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-cyan-500"></div>
                        <span className="text-xs uppercase font-bold text-foreground">Waterlogging</span>
                      </div>
                      <span className="text-2xl font-black text-cyan-500">{displayedIncidents.filter(i => (i.incident_type || i.type) === 'waterlogging').length}</span>
                    </div>
                  </div>
                </div>

                {/* Column 3: Recent Alerts Feed */}
                <div className="flex-1 flex flex-col min-h-0">
                  <h4 className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground mb-3">Recent Alerts</h4>
                  <div className="flex-1 overflow-y-auto custom-scrollbar space-y-2 pr-2">
                    {displayedIncidents.length === 0 ? (
                      <div className="text-center text-muted-foreground text-xs py-8 italic bg-background rounded-lg border border-border border-dashed">
                        Waiting for incidents to be detected...
                      </div>
                    ) : (
                      [...displayedIncidents].reverse().map(inc => (
                        <div key={inc.id} className="bg-background border border-border/60 rounded-lg p-2.5 shadow-sm flex items-center justify-between animate-in fade-in slide-in-from-right-2">
                          <div className="flex items-center gap-3">
                            <div className={`w-8 h-8 rounded-md flex items-center justify-center ${inc.incident_type === 'pothole' ? 'bg-orange-100 text-orange-600' : 'bg-cyan-100 text-cyan-600'}`}>
                              {inc.incident_type === 'pothole' ? <AlertTriangle className="w-4 h-4" /> : <Droplets className="w-4 h-4" />}
                            </div>
                            <div className="flex flex-col">
                              <span className="text-xs font-bold uppercase text-foreground">{inc.incident_type}</span>
                              <div className="text-[10px] text-muted-foreground font-mono mt-0.5">
                                Conf: {Math.round((inc.confidence || 0) * 100)}%
                              </div>
                            </div>
                          </div>
                          <span className={`text-[9px] font-bold uppercase px-2 py-1 rounded-sm ${inc.severity === 'HIGH' || inc.severity === 'CRITICAL' ? 'bg-red-100 text-red-700' : 'bg-orange-100 text-orange-700'}`}>
                            {inc.severity}
                          </span>
                        </div>
                      ))
                    )}
                  </div>
                </div>

              </div>
            </div>
            
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center border-2 border-dashed border-border rounded-xl bg-card">
            <EmptyState
              icon={Activity}
              title="Select a Journey"
              description="Choose a prepared journey from the sidebar to begin the Live Monitoring demonstration."
            />
          </div>
        )}
      </div>

      <ConfirmDialog
        isOpen={isResetConfirmOpen}
        onClose={() => setIsResetConfirmOpen(false)}
        onConfirm={handleReset}
        loading={isResetting}
        title="Reset Demo Session?"
        description="This will clear the current demonstration session and remove all demo-generated incidents. Historical production data will NOT be affected."
        confirmLabel="Confirm Reset"
        variant="destructive"
      />
      {selectedIncident && (
        <IncidentDrawer 
          incident={selectedIncident} 
          onClose={() => setSelectedIncident(null)} 
        />
      )}
    </div>
  );
}
