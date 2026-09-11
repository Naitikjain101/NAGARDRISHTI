import { Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import type { Incident } from '@/api/incidents';
import { AlertTriangle } from 'lucide-react';

interface IncidentMarkerProps {
  incident: Incident;
  onClick: (incident: Incident) => void;
}

export function IncidentMarker({ incident, onClick }: IncidentMarkerProps) {
  if (!incident.latitude || !incident.longitude) return null;

  let colorClass = 'bg-emerald-500 shadow-emerald-500/50'; // Default vehicle
  if (incident.severity === 'CRITICAL') {
    colorClass = 'bg-red-500 shadow-red-500/50';
  } else if (incident.type === 'pothole') {
    colorClass = 'bg-orange-500 shadow-orange-500/50';
  } else if (incident.type === 'waterlogging') {
    colorClass = 'bg-blue-500 shadow-blue-500/50';
  }

  // Create custom DivIcon for Tailwind styling
  const icon = L.divIcon({
    className: 'bg-transparent border-none',
    html: `<div class="relative flex items-center justify-center w-6 h-6">
            <div class="absolute w-full h-full rounded-full animate-ping opacity-75 ${colorClass.split(' ')[0]}"></div>
            <div class="relative w-4 h-4 rounded-full border-2 border-white shadow-lg ${colorClass}"></div>
           </div>`,
    iconSize: [24, 24],
    iconAnchor: [12, 12]
  });

  return (
    <Marker 
      position={[incident.latitude, incident.longitude]} 
      icon={icon}
      eventHandlers={{
        click: () => onClick(incident)
      }}
    >
      <Popup className="custom-popup">
        <div className="p-1">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="h-4 w-4 text-orange-500" />
            <h4 className="font-semibold capitalize">{incident.type.replace('_', ' ')}</h4>
          </div>
          <p className="text-sm mb-1">Severity: <span className="font-medium">{incident.severity}</span></p>
          <p className="text-xs text-muted-foreground">Confidence: {Math.round(incident.confidence * 100)}%</p>
        </div>
      </Popup>
    </Marker>
  );
}
