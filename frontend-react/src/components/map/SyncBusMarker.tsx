import React, { useEffect, useRef } from 'react';
import { Marker, useMap } from 'react-leaflet';
import L from 'leaflet';
import { type RoutePoint, getPositionAtTime, type InterpolatedPosition } from '@/utils/routeInterpolation';

// ── Bus-Shaped SVG Icon ──────────────────────────────────────────────────────
// A clean municipal bus silhouette rendered as a DivIcon so it needs no extra CDN.
const BUS_SVG = `
<svg xmlns="http://www.w3.org/2000/svg" width="40" height="48" viewBox="0 0 40 48">
  <!-- Drop shadow -->
  <ellipse cx="20" cy="45" rx="10" ry="3" fill="rgba(0,0,0,0.25)"/>
  
  <!-- Bus body -->
  <rect x="4" y="6" width="32" height="30" rx="5" ry="5" fill="#1d4ed8" stroke="white" stroke-width="1.5"/>
  
  <!-- Windscreen (top) -->
  <rect x="7" y="8" width="26" height="9" rx="3" ry="3" fill="#bfdbfe"/>
  
  <!-- Side windows -->
  <rect x="7" y="20" width="8" height="7" rx="2" ry="2" fill="#bfdbfe"/>
  <rect x="17" y="20" width="8" height="7" rx="2" ry="2" fill="#bfdbfe"/>
  <rect x="27" y="20" width="6" height="7" rx="2" ry="2" fill="#bfdbfe"/>
  
  <!-- Door indicator -->
  <rect x="7" y="30" width="6" height="5" rx="1" fill="#93c5fd"/>

  <!-- Wheels -->
  <circle cx="11" cy="37" r="3.5" fill="#1e293b" stroke="white" stroke-width="1"/>
  <circle cx="29" cy="37" r="3.5" fill="#1e293b" stroke="white" stroke-width="1"/>
  
  <!-- NagarDrishti badge -->
  <rect x="12" y="30" width="16" height="5" rx="1.5" fill="white" opacity="0.9"/>
  <text x="20" y="34.2" font-family="monospace" font-size="3.5" font-weight="900" fill="#1d4ed8" text-anchor="middle">NDRISHTI</text>
</svg>`;

const busIcon = L.divIcon({
  html: BUS_SVG,
  className: 'bus-marker-icon',
  iconSize: [40, 48],
  iconAnchor: [20, 44],   // anchor at base of bus
  popupAnchor: [0, -48],
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
