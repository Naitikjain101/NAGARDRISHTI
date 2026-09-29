import { useEffect, useState, useRef } from 'react';
import { Marker, Tooltip } from 'react-leaflet';
import L from 'leaflet';
import type { MapBus } from '@/hooks/useMapIntelligence';
import { getBusPositionAtTime } from '@/lib/geo/interpolation';
import type { RoutePoint, BusPosition } from '@/lib/geo/interpolation';
import { fetchRaw } from '../../api/client';

interface BusMarkerProps {
  bus: MapBus;
}

export function BusMarker({ bus }: BusMarkerProps) {
  const [currentPos, setCurrentPos] = useState<BusPosition | null>(null);
  const animationRef = useRef<number | undefined>(undefined);

  // Use refs to avoid closure stale state in rAF loop
  const latestBusRef = useRef(bus);
  const routePointsRef = useRef<RoutePoint[]>([]);

  useEffect(() => {
    latestBusRef.current = bus;
  }, [bus]);

  // Fetch route points on mount
  useEffect(() => {
    const fetchRoute = async () => {
      try {
        const res = await fetchRaw(`/api/missions/${bus.mission_id}/route`);
        const data = await res.json();
        const mappedPoints = (data.route_points || []).map((p: any) => ({
          timestamp: p.timestamp_seconds ?? p.timestamp,
          lat: p.latitude ?? p.lat,
          lng: p.longitude ?? p.lng
        }));
        routePointsRef.current = mappedPoints;
      } catch (err) {
        console.error('Failed to fetch route for bus', bus.mission_id);
      }
    };
    fetchRoute();
  }, [bus.mission_id]);

  // Animation Loop for smooth sub-second movement
  useEffect(() => {
    let lastTickTime = performance.now();
    let currentTs = latestBusRef.current.current_timestamp || 0;

    const animate = (time: DOMHighResTimeStamp) => {
      const b = latestBusRef.current;
      const pts = routePointsRef.current;
      
      // If we received a new timestamp from the server, sync to it.
      // But only jump if it's significantly different to allow local interpolation.
      if (b.current_timestamp !== undefined && Math.abs(currentTs - b.current_timestamp) > 2.0) {
         currentTs = b.current_timestamp;
         lastTickTime = time;
      }
      
      if (pts.length > 0 && b) {
        // Interpolate time forward based on frame delta
        const deltaSec = (time - lastTickTime) / 1000.0;
        lastTickTime = time;
        
        // We cap delta to avoid massive jumps if tab was backgrounded
        if (deltaSec < 1.0) {
          currentTs += deltaSec;
        }

        const interpolated = getBusPositionAtTime(pts, currentTs);
        if (interpolated) {
          setCurrentPos(interpolated);
        } else {
          // Fallback to server position
          setCurrentPos({
            lat: b.current_lat,
            lng: b.current_lng,
            heading: 0,
            speedKmh: b.speed_kmh || 0,
            segmentIndex: 0
          });
        }
      }
      
      animationRef.current = requestAnimationFrame(animate);
    };
    
    animationRef.current = requestAnimationFrame(animate);
    
    return () => {
      if (animationRef.current) cancelAnimationFrame(animationRef.current);
    };
  }, []);

  if (bus.current_lat === null || bus.current_lng === null) return null;

  // Use interpolated position if available, else fallback to raw bus telemetry
  const lat = currentPos ? currentPos.lat : bus.current_lat;
  const lng = currentPos ? currentPos.lng : bus.current_lng;
  const heading = currentPos ? currentPos.heading : 0;
  
  // Custom SVG icon for Bus with CSS transform for rotation
  const icon = L.divIcon({
    className: 'bg-transparent border-none',
    html: `
      <div class="relative flex items-center justify-center w-8 h-8" style="transform: rotate(${heading}deg); transition: transform 100ms linear;">
        <div class="absolute w-full h-full rounded-full animate-ping opacity-50 bg-blue-500"></div>
        <div class="relative flex items-center justify-center w-6 h-6 rounded-full border-2 border-white shadow-lg bg-blue-600 text-white shadow-blue-500/50 z-10">
          <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M8 6v6"/><path d="M15 6v6"/><path d="M2 12h19.6"/><path d="M18 18h3s.5-1.7.8-2.8c.1-.4.2-.8.2-1.2 0-.4-.1-.8-.2-1.2l-1.4-5C20.1 6.8 19.1 6 18 6H4a2 2 0 0 0-2 2v10h3"/><circle cx="7" cy="18" r="2"/><circle cx="17" cy="18" r="2"/>
          </svg>
        </div>
      </div>
    `,
    iconSize: [32, 32],
    iconAnchor: [16, 16],
  });

  return (
    <Marker 
      position={[lat, lng]} 
      icon={icon}
      zIndexOffset={1000}
    >
      <Tooltip direction="top" offset={[0, -12]} opacity={1} className="custom-tooltip">
        <div className="p-1 min-w-[120px]">
          <div className="font-bold text-sm mb-1">{bus.bus_id}</div>
          <div className="text-xs text-muted-foreground mb-2">{bus.route_name}</div>
          <div className="flex justify-between text-xs mb-1">
            <span className="text-muted-foreground">Speed</span>
            <span className="font-medium">{bus.speed_kmh?.toFixed(1) || 0} km/h</span>
          </div>
          <div className="flex justify-between text-xs mb-1">
            <span className="text-muted-foreground">AI Status</span>
            <span className="font-medium capitalize text-emerald-500">{bus.ai_status}</span>
          </div>
          <div className="flex justify-between text-xs mt-2 pt-2 border-t border-border">
            <span className="text-muted-foreground">Detections</span>
            <span className="font-medium text-orange-500">{bus.pothole_count + bus.waterlogging_count}</span>
          </div>
        </div>
      </Tooltip>
    </Marker>
  );
}
