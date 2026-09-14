import { useEffect } from 'react';
import { MapContainer, TileLayer, ZoomControl, useMap } from 'react-leaflet';
import type { MapIncident, MapBus } from '@/hooks/useMapIntelligence';
import { IncidentMarker } from './IncidentMarker';
import { BusMarker } from './BusMarker';
import { RouteLayer } from './RouteLayer';
import { MapLegend } from './MapLegend';

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
}

export function MapView({ incidents, buses = [], onIncidentClick, selectedIncident }: MapViewProps & { selectedIncident?: MapIncident | null }) {
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
        
        {safeIncidents.map((incident) => (
          <IncidentMarker 
            key={incident.id} 
            incident={incident} 
            onClick={onIncidentClick} 
          />
        ))}

        {safeBuses.map((bus) => (
          <RouteLayer key={`route-${bus.mission_id}-${bus.bus_id}`} bus={bus} />
        ))}
        {safeBuses.map((bus) => (
          <BusMarker key={`bus-${bus.mission_id}-${bus.bus_id}`} bus={bus} />
        ))}
      </MapContainer>
      
      <MapLegend />
    </div>
  );
}
