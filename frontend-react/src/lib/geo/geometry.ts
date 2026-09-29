import type { MapIncident } from '@/hooks/useMapIntelligence';

export type ShapeType = 'circle' | 'ellipse' | 'polygon';

export interface IncidentGeometry {
  shapeType: ShapeType;
  center: [number, number]; // lat, lng
  radiusMeters?: number; // for circle
  radiiMeters?: [number, number]; // for ellipse
  polygonPoints?: [number, number][]; // for complex hazard/waterlogging
  color: string;
  fillOpacity: number;
}

const SEVERITY_COLORS = {
  LOW: '#eab308',      // yellow-500
  MEDIUM: '#f97316',   // orange-500
  HIGH: '#ef4444',     // red-500
  CRITICAL: '#b91c1c'  // red-700
};

/**
 * Calculates a bounding box width/height in real-world meters given a detection bbox.
 * This is an approximation since we lack exact camera calibration.
 */
function estimateExtentFromBBox(incident: MapIncident): { width: number; height: number } {
  // If we don't have a real bbox in the UI model yet, we fake it based on type & severity
  // A real system would use `incident.bbox` (e.g. [x, y, w, h]).
  let baseRadius = 2.0; 
  if ((incident.type || incident.incident_type) === 'pothole') {
    baseRadius = incident.severity === 'CRITICAL' ? 3.0 : 1.5;
  } else if ((incident.type || incident.incident_type) === 'waterlogging') {
    baseRadius = incident.severity === 'CRITICAL' ? 8.0 : 4.0;
  }
  
  return { width: baseRadius * 2, height: baseRadius * 2 };
}

export function getIncidentGeometry(incident: MapIncident): IncidentGeometry {
  const t = incident.type || incident.incident_type;
  const severity = incident.severity || 'LOW';
  
  // Conf = 0.0 to 1.0. Lower confidence = more transparent
  const conf = incident.confidence ?? 0.8;
  const fillOpacity = Math.max(0.2, Math.min(0.8, conf));
  
  const color = SEVERITY_COLORS[severity as keyof typeof SEVERITY_COLORS] || SEVERITY_COLORS.LOW;

  const extent = estimateExtentFromBBox(incident);

  // Potholes -> Small Circle
  if (t === 'pothole') {
    return {
      shapeType: 'circle',
      center: [incident.latitude, incident.longitude],
      radiusMeters: extent.width / 2,
      color,
      fillOpacity
    };
  }
  
  // Waterlogging -> Ellipse (pool along the road)
  // We approximate an ellipse in leaflet by scaling a circle or using a polygon, 
  // but for simplicity we return 'ellipse' and render it using a custom SVG or just a circle if leafet doesn't support ellipse natively easily.
  // Actually, Leaflet has a plugin for Ellipse, but standard Leaflet only has Circle and Polygon.
  // Let's use a standard Polygon approximating an ellipse or just a wider Circle/Rectangle.
  // For 'waterlogging', we'll return an ellipse indicator and let the component handle it (e.g., using a bounding polygon).
  if (t === 'waterlogging') {
    // Generate a quick diamond/ellipse polygon around the center
    const lat = incident.latitude;
    const lng = incident.longitude;
    // rough conversion: 1 deg lat ~ 111km -> 1m ~ 0.000009 deg
    const wDeg = (extent.width / 111000) * 2; // Waterlogging is wide
    const hDeg = (extent.height / 111000) / 2; // Not very deep along the path

    return {
      shapeType: 'polygon',
      center: [lat, lng],
      polygonPoints: [
        [lat + hDeg, lng],
        [lat, lng + wDeg],
        [lat - hDeg, lng],
        [lat, lng - wDeg]
      ],
      color,
      fillOpacity
    };
  }

  // Default / Hazard -> Circle
  return {
    shapeType: 'circle',
    center: [incident.latitude, incident.longitude],
    radiusMeters: extent.width / 2,
    color,
    fillOpacity
  };
}
