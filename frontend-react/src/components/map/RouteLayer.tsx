import { useEffect, useState, useMemo } from 'react';
import type { MapIncident } from '@/hooks/useMapIntelligence';
import { getPositionAtTime, type RoutePoint } from '@/utils/routeInterpolation';
import { fetchRaw } from '../../api/client';
import { DynamicRoadLayer, type ActiveMapLayer, type SegmentIntelligence } from './DynamicRoadLayer';

interface RouteLayerProps {
  missionId: string;
  currentTimestamp?: number;
  incidents: MapIncident[];
  activeLayer: ActiveMapLayer;
  onChunkClick?: (latlng: { lat: number; lng: number }) => void;
}

export function RouteLayer({ missionId, currentTimestamp, incidents, activeLayer, onChunkClick }: RouteLayerProps) {
  const [routePoints, setRoutePoints] = useState<RoutePoint[]>([]);
  const [videoDuration, setVideoDuration] = useState<number>(0);

  useEffect(() => {
    const fetchRoute = async () => {
      try {
        const res = await fetchRaw(`/api/missions/${missionId}/route`);
        const data = await res.json();
        const mappedPoints = (data.route_points || []).map((p: any) => ({
          timestamp_seconds: p.timestamp_seconds ?? p.timestamp,
          latitude: p.latitude ?? p.lat,
          longitude: p.longitude ?? p.lng
        }));
        setRoutePoints(mappedPoints);
        if (mappedPoints.length > 0) {
           setVideoDuration(mappedPoints[mappedPoints.length - 1].timestamp_seconds);
        }
      } catch (err) {
        console.error('Failed to fetch route for RouteLayer', missionId);
      }
    };
    fetchRoute();
  }, [missionId]);

  const segmentIntelligence = useMemo(() => {
    if (routePoints.length < 2) return {};
    
    const intel: Record<number, SegmentIntelligence> = {};
    const ts = currentTimestamp ?? Infinity;

    // 1. Mark observed segments
    let splitIndex = 0;
    while (splitIndex < routePoints.length - 1 && routePoints[splitIndex + 1].timestamp_seconds <= ts) {
      intel[splitIndex] = { observed: true, pothole: false, waterlogging: false };
      splitIndex++;
    }

    // 2. Map incidents to segments
    // We check both metadata.mission_id and source_mission_id
    const missionIncidents = incidents.filter(i => (i.metadata?.mission_id === missionId) || ((i as any).source_mission_id === missionId));
    
    for (const inc of missionIncidents) {
       // if we have metadata.video_time_sec, use it.
       const evTime = inc.metadata?.video_time_sec ?? inc.timestamp;
       if (typeof evTime === 'number') {
           const evPos = getPositionAtTime(routePoints, evTime, videoDuration);
           if (evPos) {
               const seq = evPos.currentSequence;
               if (!intel[seq]) intel[seq] = { observed: true, pothole: false, waterlogging: false };
               if (inc.incident_type === 'pothole' || inc.type === 'pothole') intel[seq].pothole = true;
               if (inc.incident_type === 'waterlogging' || inc.type === 'waterlogging') intel[seq].waterlogging = true;
               
               // Expand waterlogging duration if available
               const endEvTime = inc.metadata?.last_video_time_sec;
               if (typeof endEvTime === 'number' && endEvTime > evTime && (inc.incident_type === 'waterlogging' || inc.type === 'waterlogging')) {
                   const endPos = getPositionAtTime(routePoints, endEvTime, videoDuration);
                   if (endPos) {
                       for (let s = seq; s <= endPos.currentSequence; s++) {
                           if (!intel[s]) intel[s] = { observed: true, pothole: false, waterlogging: false };
                           intel[s].waterlogging = true;
                       }
                   }
               }
           }
       }
    }

    return intel;
  }, [routePoints, currentTimestamp, incidents, missionId, videoDuration]);

  if (routePoints.length < 2) return null;

  return (
    <DynamicRoadLayer 
       routePoints={routePoints} 
       segmentIntelligence={segmentIntelligence} 
       activeLayer={activeLayer}
       onChunkClick={onChunkClick}
    />
  );
}
