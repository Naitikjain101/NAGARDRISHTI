import { useEffect, useState } from 'react';
import { Polyline } from 'react-leaflet';
import type { MapBus } from '@/hooks/useMapIntelligence';
import type { RoutePoint } from '@/lib/geo/interpolation';
import { getBusPositionAtTime } from '@/lib/geo/interpolation';

interface RouteLayerProps {
  bus: MapBus;
}

export function RouteLayer({ bus }: RouteLayerProps) {
  const [routePoints, setRoutePoints] = useState<RoutePoint[]>([]);

  useEffect(() => {
    const fetchRoute = async () => {
      try {
        const res = await fetch(`/api/missions/${bus.mission_id}/route`);
        const data = await res.json();
        const mappedPoints = (data.route_points || []).map((p: any) => ({
          timestamp: p.timestamp_seconds ?? p.timestamp,
          lat: p.latitude ?? p.lat,
          lng: p.longitude ?? p.lng
        }));
        setRoutePoints(mappedPoints);
      } catch (err) {
        console.error('Failed to fetch route for RouteLayer', bus.mission_id);
      }
    };
    fetchRoute();
  }, [bus.mission_id]);

  if (routePoints.length < 2) return null;

  // Find the exact split point based on the current timestamp
  const ts = bus.current_timestamp || 0;
  
  let splitIndex = 0;
  while (splitIndex < routePoints.length - 1 && routePoints[splitIndex + 1].timestamp < ts) {
    splitIndex++;
  }

  // To make the split perfectly smooth, we compute the interpolated current point
  const currentPos = getBusPositionAtTime(routePoints, ts);
  
  const traveledCoords: [number, number][] = routePoints
    .slice(0, splitIndex + 1)
    .map(p => [p.lat, p.lng]);
    
  if (currentPos) {
    traveledCoords.push([currentPos.lat, currentPos.lng]);
  }

  const remainingCoords: [number, number][] = [];
  if (currentPos) {
    remainingCoords.push([currentPos.lat, currentPos.lng]);
  }
  if (splitIndex < routePoints.length - 1) {
    remainingCoords.push(...routePoints.slice(splitIndex + 1).map(p => [p.lat, p.lng] as [number, number]));
  }

  return (
    <>
      {/* Traveled Route (Solid) */}
      <Polyline 
        positions={traveledCoords} 
        color="#3b82f6" 
        weight={4} 
        opacity={0.8}
      />
      {/* Remaining Route (Dashed) */}
      <Polyline 
        positions={remainingCoords} 
        color="#3b82f6" 
        weight={4} 
        opacity={0.4}
        dashArray="10, 10"
      />
    </>
  );
}
