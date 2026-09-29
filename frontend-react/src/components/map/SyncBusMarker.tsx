import React, { useEffect, useRef } from 'react';
import { Marker, useMap } from 'react-leaflet';
import L from 'leaflet';
import { type RoutePoint, getPositionAtTime, type InterpolatedPosition } from '@/utils/routeInterpolation';

// ── Modern Live Location Icon ──────────────────────────────────────────────
// A clean, glowing blue dot with a pulse animation representing the live vehicle
const BUS_SVG = `
<svg xmlns="http://www.w3.org/2000/svg" width="36" height="36" viewBox="0 0 36 36">
  <circle cx="18" cy="18" r="14" fill="#3b82f6" opacity="0.3">
    <animate attributeName="r" from="8" to="18" dur="2s" repeatCount="indefinite" />
    <animate attributeName="opacity" from="0.5" to="0" dur="2s" repeatCount="indefinite" />
  </circle>
  <circle cx="18" cy="18" r="8" fill="white" filter="drop-shadow(0px 2px 4px rgba(0,0,0,0.3))"/>
  <circle cx="18" cy="18" r="5" fill="#2563eb"/>
</svg>`;

const busIcon = L.divIcon({
  html: BUS_SVG,
  className: 'bus-marker-icon',
  iconSize: [36, 36],
  iconAnchor: [18, 18],   // centered
  popupAnchor: [0, -18],
});

interface SyncBusMarkerProps {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  routePoints: RoutePoint[];
  videoDuration: number;
  onPositionUpdate?: (pos: InterpolatedPosition) => void;
  followBus: boolean;
}

export function SyncBusMarker({ videoRef, routePoints, videoDuration, onPositionUpdate, followBus }: SyncBusMarkerProps) {
  const markerRef = useRef<L.Marker>(null);
  const map = useMap();
  const requestRef = useRef<number>(0);

  useEffect(() => {
    if (!routePoints || routePoints.length === 0) return;

    let lastTime = -1;

    const animate = () => {
      const video = videoRef.current;
      const marker = markerRef.current;
      
      if (video && marker) {
        if (video.currentTime !== lastTime) {
          lastTime = video.currentTime;
          
          const pos = getPositionAtTime(routePoints, lastTime, videoDuration);
          
          if (pos) {
            marker.setLatLng([pos.lat, pos.lng]);
            onPositionUpdate?.(pos);

            if (followBus) {
              map.panTo([pos.lat, pos.lng], { animate: true, duration: 0.25, easeLinearity: 0.25 });
            }
          }
        }
      }
      requestRef.current = requestAnimationFrame(animate);
    };

    requestRef.current = requestAnimationFrame(animate);

    return () => {
      if (requestRef.current) {
        cancelAnimationFrame(requestRef.current);
      }
    };
  }, [routePoints, videoRef, videoDuration, onPositionUpdate, followBus, map]);

  const initialPos = routePoints.length > 0 ? [routePoints[0].latitude, routePoints[0].longitude] : [0, 0];

  if (!routePoints || routePoints.length === 0) return null;

  return (
    <Marker 
      ref={markerRef} 
      position={initialPos as L.LatLngExpression} 
      icon={busIcon}
      zIndexOffset={1000}
    />
  );
}
