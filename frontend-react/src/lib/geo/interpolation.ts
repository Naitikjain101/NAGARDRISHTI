export interface RoutePoint {
  timestamp: number;
  lat: number;
  lng: number;
}

export interface BusPosition {
  lat: number;
  lng: number;
  heading: number; // Degrees from True North
  speedKmh: number;
  segmentIndex: number;
}

const EARTH_RADIUS_KM = 6371;

/**
 * Calculates the Haversine distance between two points in km.
 */
export function haversineDistance(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
            Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
            Math.sin(dLon/2) * Math.sin(dLon/2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
  return EARTH_RADIUS_KM * c;
}

/**
 * Calculates the initial bearing from point 1 to point 2 in degrees (0-360).
 */
export function calculateBearing(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const rLat1 = lat1 * Math.PI / 180;
  const rLat2 = lat2 * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  
  const y = Math.sin(dLon) * Math.cos(rLat2);
  const x = Math.cos(rLat1) * Math.sin(rLat2) -
            Math.sin(rLat1) * Math.cos(rLat2) * Math.cos(dLon);
            
  let brng = Math.atan2(y, x) * 180 / Math.PI;
  return (brng + 360) % 360;
}

/**
 * Linearly interpolates a position between two points given a fraction (0-1).
 */
function interpolateCoord(val1: number, val2: number, fraction: number): number {
  return val1 + (val2 - val1) * fraction;
}

/**
 * Computes the precise bus position on the route at a given video timestamp.
 * Interpolates coordinates, calculates heading, and computes instantaneous speed.
 */
export function getBusPositionAtTime(routePoints: RoutePoint[], videoTimestamp: number): BusPosition | null {
  if (!routePoints || routePoints.length === 0) return null;
  
  // Before start
  if (videoTimestamp <= routePoints[0].timestamp) {
    const next = routePoints.length > 1 ? routePoints[1] : routePoints[0];
    const heading = calculateBearing(routePoints[0].lat, routePoints[0].lng, next.lat, next.lng);
    return {
      lat: routePoints[0].lat,
      lng: routePoints[0].lng,
      heading,
      speedKmh: 0,
      segmentIndex: 0
    };
  }
  
  // After end
  const lastIdx = routePoints.length - 1;
  if (videoTimestamp >= routePoints[lastIdx].timestamp) {
    const prev = lastIdx > 0 ? routePoints[lastIdx - 1] : routePoints[lastIdx];
    const heading = calculateBearing(prev.lat, prev.lng, routePoints[lastIdx].lat, routePoints[lastIdx].lng);
    return {
      lat: routePoints[lastIdx].lat,
      lng: routePoints[lastIdx].lng,
      heading,
      speedKmh: 0,
      segmentIndex: lastIdx
    };
  }
  
  // Find the exact segment
  let i = 0;
  while (i < routePoints.length - 1 && routePoints[i + 1].timestamp < videoTimestamp) {
    i++;
  }
  
  const p1 = routePoints[i];
  const p2 = routePoints[i + 1];
  
  const timeDelta = p2.timestamp - p1.timestamp;
  if (timeDelta <= 0) return null; // Avoid division by zero on malformed data
  
  const fraction = (videoTimestamp - p1.timestamp) / timeDelta;
  
  const currentLat = interpolateCoord(p1.lat, p2.lat, fraction);
  const currentLng = interpolateCoord(p1.lng, p2.lng, fraction);
  
  const heading = calculateBearing(p1.lat, p1.lng, p2.lat, p2.lng);
  
  // Speed calculation for this segment
  const distKm = haversineDistance(p1.lat, p1.lng, p2.lat, p2.lng);
  const speedKmh = (distKm / (timeDelta / 3600)); // km/h
  
  return {
    lat: currentLat,
    lng: currentLng,
    heading,
    speedKmh,
    segmentIndex: i
  };
}
