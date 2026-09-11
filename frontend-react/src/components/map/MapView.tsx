
import { MapContainer, TileLayer, ZoomControl } from 'react-leaflet';
import type { Incident } from '@/api/incidents';
import { IncidentMarker } from './IncidentMarker';
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
  incidents: Incident[];
  onIncidentClick: (incident: Incident) => void;
}

export function MapView({ incidents, onIncidentClick }: MapViewProps) {
  // Center of Delhi/Gurugram as default
  const defaultCenter: [number, number] = [28.4595, 77.0266];
  
  return (
    <div className="relative w-full h-full z-0">
      <MapContainer 
        center={defaultCenter} 
        zoom={12} 
        className="w-full h-full bg-background"
        zoomControl={false} // We add it manually to position it
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          subdomains="abcd"
          maxZoom={20}
        />
        
        <ZoomControl position="bottomleft" />
        
        {incidents.map((incident) => (
          <IncidentMarker 
            key={incident.id} 
            incident={incident} 
            onClick={onIncidentClick} 
          />
        ))}
      </MapContainer>
      
      <MapLegend />
    </div>
  );
}
