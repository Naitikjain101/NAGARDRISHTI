export interface RoutePoint {
  id?: string;
  mission_id?: string;
  timestamp_seconds: number;
  latitude: number;
  longitude: number;
  created_at?: string;
}

export interface InterpolatedPosition {
  lat: number;
  lng: number;
  progress: number; // 0.0 to 1.0
  currentSequence: number;
  previousPoint: RoutePoint | null;
  nextPoint: RoutePoint | null;
  heading: number | null; // angle in degrees
}

/**
 * Calculate heading (bearing) between two lat/lng coordinates.
 * Returns angle in degrees (0 = North, 90 = East)
 */
function calculateHeading(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const toDeg = (rad: number) => (rad * 180) / Math.PI;

  const dLon = toRad(lon2 - lon1);
  const y = Math.sin(dLon) * Math.cos(toRad(lat2));
  const x =
    Math.cos(toRad(lat1)) * Math.sin(toRad(lat2)) -
    Math.sin(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.cos(dLon);

  let bearing = toDeg(Math.atan2(y, x));
  bearing = (bearing + 360) % 360;
  return bearing;
}

/**
 * Interpolates the bus position given a video timestamp and an ordered array of route points.
 */
export function getPositionAtTime(points: RoutePoint[], currentTime: number, totalVideoDuration: number): InterpolatedPosition | null {
  if (!points || points.length === 0) {
    return null;
  }

  const duration = totalVideoDuration > 0 ? totalVideoDuration : points[points.length - 1].timestamp_seconds;
  const progress = duration > 0 ? Math.min(1, Math.max(0, currentTime / duration)) : 0;

  // Single point edge case
  if (points.length === 1) {
    return {
      lat: points[0].latitude,
      lng: points[0].longitude,
      progress,
      currentSequence: 0,
      previousPoint: points[0],
      nextPoint: null,
      heading: null,
    };
  }

  // Before first point
  if (currentTime <= points[0].timestamp_seconds) {
    return {
      lat: points[0].latitude,
      lng: points[0].longitude,
      progress: 0,
      currentSequence: 0,
      previousPoint: points[0],
      nextPoint: points[1],
      heading: calculateHeading(points[0].latitude, points[0].longitude, points[1].latitude, points[1].longitude),
    };
  }

  // After last point
  const lastPoint = points[points.length - 1];
  if (currentTime >= lastPoint.timestamp_seconds) {
    const prevPoint = points[points.length - 2];
    return {
      lat: lastPoint.latitude,
      lng: lastPoint.longitude,
      progress: 1,
      currentSequence: points.length - 1,
      previousPoint: lastPoint,
      nextPoint: null,
      heading: calculateHeading(prevPoint.latitude, prevPoint.longitude, lastPoint.latitude, lastPoint.longitude),
    };
  }

  // Binary search for the correct segment
  let low = 0;
  let high = points.length - 1;

  while (low <= high) {
    const mid = Math.floor((low + high) / 2);

    if (points[mid].timestamp_seconds === currentTime) {
      const nextPoint = mid + 1 < points.length ? points[mid + 1] : points[mid];
      return {
        lat: points[mid].latitude,
        lng: points[mid].longitude,
        progress,
        currentSequence: mid,
        previousPoint: points[mid],
        nextPoint,
        heading: calculateHeading(points[mid].latitude, points[mid].longitude, nextPoint.latitude, nextPoint.longitude),
      };
    }

    if (points[mid].timestamp_seconds < currentTime) {
      if (mid + 1 < points.length && points[mid + 1].timestamp_seconds > currentTime) {
        // Found the exact segment: points[mid] to points[mid+1]
        const p1 = points[mid];
        const p2 = points[mid + 1];
        
        const timeDiff = p2.timestamp_seconds - p1.timestamp_seconds;
        // Avoid division by zero if timestamps are identical
        const alpha = timeDiff === 0 ? 0 : (currentTime - p1.timestamp_seconds) / timeDiff;

        const interpLat = p1.latitude + (p2.latitude - p1.latitude) * alpha;
        const interpLng = p1.longitude + (p2.longitude - p1.longitude) * alpha;
        
        return {
          lat: interpLat,
          lng: interpLng,
          progress,
          currentSequence: mid,
          previousPoint: p1,
          nextPoint: p2,
          heading: calculateHeading(p1.latitude, p1.longitude, p2.latitude, p2.longitude),
        };
      }
      low = mid + 1;
    } else {
      high = mid - 1;
    }
  }

  // Fallback (should theoretically not be reached due to bounds checks)
  return null;
}
