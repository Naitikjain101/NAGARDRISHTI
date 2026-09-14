import React, { useEffect, useRef } from 'react';
import { Marker, useMap } from 'react-leaflet';
import L from 'leaflet';
import { type RoutePoint, getPositionAtTime, type InterpolatedPosition } from '@/utils/routeInterpolation';

// Custom colored bus marker
const busIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-blue.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
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
    // We only animate if we have valid route points
    if (!routePoints || routePoints.length === 0) return;

    let lastTime = -1;

    const animate = () => {
      const video = videoRef.current;
      const marker = markerRef.current;
      
      if (video && marker) {
        // Only update if time actually changed (prevents redundant calculation)
        if (video.currentTime !== lastTime) {
          lastTime = video.currentTime;
          
          const pos = getPositionAtTime(routePoints, lastTime, videoDuration);
          
          if (pos) {
            // Update marker immediately avoiding React state cycle (High Performance)
            marker.setLatLng([pos.lat, pos.lng]);
            
            // Optional: You could update rotation here if a leaflet rotation plugin was loaded,
            // but for simplicity and stability, we just move the position for now.
            // Example if plugin exists: marker.setRotationAngle?.(pos.heading);

            // Let parent know (parent should throttle this update if setting React state)
            onPositionUpdate?.(pos);

            // Handle map following
            if (followBus) {
              // Smoothly pan map to bus without interrupting user too aggressively
              map.panTo([pos.lat, pos.lng], { animate: true, duration: 0.25, easeLinearity: 0.25 });
            }
          }
        }
      }
      // Schedule next frame
      requestRef.current = requestAnimationFrame(animate);
    };

    requestRef.current = requestAnimationFrame(animate);

    return () => {
      if (requestRef.current) {
        cancelAnimationFrame(requestRef.current);
      }
    };
  }, [routePoints, videoRef, videoDuration, onPositionUpdate, followBus, map]);

  // Render at initial position
  const initialPos = routePoints.length > 0 ? [routePoints[0].latitude, routePoints[0].longitude] : [0, 0];

  if (!routePoints || routePoints.length === 0) return null;

  return (
    <Marker 
      ref={markerRef} 
      position={initialPos as L.LatLngExpression} 
      icon={busIcon}
      zIndexOffset={1000} // Ensure bus is above polyline
    />
  );
}
