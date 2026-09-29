import { useEffect } from 'react';
import { MapContainer, TileLayer, ZoomControl, useMap } from 'react-leaflet';
import type { MapIncident, MapBus } from '@/hooks/useMapIntelligence';
import { IncidentMarker } from './IncidentMarker';
import { BusMarker } from './BusMarker';
import { RouteLayer } from './RouteLayer';
import type { ActiveMapLayer } from './DynamicRoadLayer';

// Fix for missing default icon paths in leaflet
import L from 'leaflet';
import iconUrl from 'leaflet/dist/images/marker-icon.png';
import iconRetinaUrl from 'leaflet/dist/images/marker-icon-2x.png';
import shadowUrl from 'leaflet/dist/images/marker-shadow.png';

L.Icon.Default.mergeOptions({
  iconRetinaUrl,
  iconUrl,
  shadowUrl,
});

interface MapViewProps {
  incidents: MapIncident[];
  buses?: MapBus[];
  onIncidentClick: (incident: MapIncident) => void;
  activeLayer?: ActiveMapLayer;
}

export function MapView({ incidents, buses = [], onIncidentClick, selectedIncident, activeLayer = 'observed' }: MapViewProps & { selectedIncident?: MapIncident | null }) {
  // Center of Jaipur as default since demo missions are in Jaipur
  const defaultCenter: [number, number] = [26.9124, 75.7873];
  
  // Controller to fly map to selected incident
  function MapController() {
    const map = useMap();
    useEffect(() => {
      if (selectedIncident?.latitude && selectedIncident?.longitude) {
        map.flyTo([selectedIncident.latitude, selectedIncident.longitude], 17, { duration: 1.5 });
      }
    }, [selectedIncident, map]);
    return null;
  }

  const safeIncidents = Array.isArray(incidents) ? incidents : [];
  const safeBuses = Array.isArray(buses) ? buses : [];

  // Collect all unique mission IDs from active buses and incidents to draw their routes
  const missionIdsToDraw = new Set<string>();
  safeBuses.forEach(b => { if (b.mission_id) missionIdsToDraw.add(b.mission_id); });
  safeIncidents.forEach(i => {
    const mId = i.metadata?.mission_id || (i as any).source_mission_id;
    if (mId) missionIdsToDraw.add(mId);
  });

  return (
    <div className="relative w-full h-full z-0">
      <MapContainer 
        center={defaultCenter} 
        zoom={12} 
        className="w-full h-full bg-background"
        zoomControl={false} // We add it manually to position it
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          maxZoom={19}
        />
        
        <ZoomControl position="bottomright" />
        <MapController />
        
        {safeIncidents
          .filter(inc => {
             const type = inc.incident_type || inc.type;
             if (activeLayer === 'waterlogging' && type === 'waterlogging') return false;
             return true;
          })
          .map((incident) => (
          <IncidentMarker 
            key={incident.id} 
            incident={incident} 
            onClick={onIncidentClick} 
          />
        ))}

        {Array.from(missionIdsToDraw).map((mId) => {
          const activeBus = safeBuses.find(b => b.mission_id === mId);
          return (
            <RouteLayer 
              key={`route-${mId}`} 
              missionId={mId}
              currentTimestamp={activeBus?.current_timestamp}
              incidents={safeIncidents}
              activeLayer={activeLayer}
              onChunkClick={(latlng) => {
                if (safeIncidents.length > 0) {
                   let nearest = safeIncidents[0];
                   let minDist = Infinity;
                   for (const inc of safeIncidents) {
                     if (!inc.latitude || !inc.longitude) continue;
                     const dist = Math.pow(inc.latitude - latlng.lat, 2) + Math.pow(inc.longitude - latlng.lng, 2);
                     if (dist < minDist) {
                        minDist = dist;
                        nearest = inc;
                     }
                   }
                   if (minDist !== Infinity) {
                     onIncidentClick(nearest);
                   }
                }
              }}
            />
          );
        })}
        {safeBuses.map((bus) => (
          <BusMarker key={`bus-${bus.mission_id}-${bus.bus_id}`} bus={bus} />
        ))}
      </MapContainer>
    </div>
  );
}
