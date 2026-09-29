export interface LocationSearchResult {
  place_id: number;
  display_name: string;
  lat: number;
  lon: number;
}

export interface RouteResult {
  distance_km: number;
  duration_min: number;
  geometry: [number, number][]; // Array of [lat, lng]
}

const GEOCODE_CACHE = new Map<string, LocationSearchResult[]>();

export const LocationService = {
  /**
   * Search for a location using Nominatim (OpenStreetMap).
   * Free, no API key required. Rate limited to 1 req/sec.
   */
  async search(query: string): Promise<LocationSearchResult[]> {
    if (!query || query.length < 3) return [];
    
    // Check cache first
    const cacheKey = query.trim().toLowerCase();
    if (GEOCODE_CACHE.has(cacheKey)) {
      return GEOCODE_CACHE.get(cacheKey)!;
    }

    try {
      const res = await fetch(
        `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}&limit=5`,
        {
          headers: {
            'Accept-Language': 'en',
            // It's polite to provide a user agent for Nominatim
            'User-Agent': 'UrbanWatch/1.0 (HackathonDemo)'
          }
        }
      );
      
      if (!res.ok) throw new Error('Geocoding failed');
      
      const data = await res.json();
      
      const results: LocationSearchResult[] = data.map((item: any) => ({
        place_id: item.place_id,
        display_name: item.display_name,
        lat: parseFloat(item.lat),
        lon: parseFloat(item.lon)
      }));

      // Cache the result
      GEOCODE_CACHE.set(cacheKey, results);
      return results;
    } catch (err) {
      console.error('Nominatim search error:', err);
      return [];
    }
  },

  /**
   * Reverse geocode coordinates using Nominatim.
   * Fallback to coordinates if API fails.
   */
  async reverseGeocode(lat: number, lon: number): Promise<LocationSearchResult> {
    try {
      const res = await fetch(
        `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}`,
        {
          headers: {
            'Accept-Language': 'en',
            'User-Agent': 'UrbanWatch/1.0 (HackathonDemo)'
          }
        }
      );
      if (!res.ok) throw new Error('Reverse geocoding failed');
      const data = await res.json();
      return {
        place_id: data.place_id || Date.now(),
        display_name: data.display_name || `Selected location (${lat.toFixed(4)}, ${lon.toFixed(4)})`,
        lat: lat,
        lon: lon
      };
    } catch (err) {
      console.error('Reverse geocode error:', err);
      // Fallback
      return {
        place_id: Date.now(),
        display_name: `Selected location (${lat.toFixed(4)}, ${lon.toFixed(4)})`,
        lat: lat,
        lon: lon
      };
    }
  },

  /**
   * Generate a road route using OSRM.
   * Free public API. Returns decoded polyline geometries.
   */
  async getRoute(start: {lat: number, lon: number}, end: {lat: number, lon: number}): Promise<RouteResult | null> {
    try {
      // OSRM format: lon,lat
      const res = await fetch(
        `https://router.project-osrm.org/route/v1/driving/${start.lon},${start.lat};${end.lon},${end.lat}?overview=full&geometries=geojson`
      );

      if (!res.ok) throw new Error('Routing failed');

      const data = await res.json();
      
      if (data.code !== 'Ok' || !data.routes || data.routes.length === 0) {
        return null;
      }

      const route = data.routes[0];
      
      // GeoJSON returns coordinates in [lon, lat] format
      // We must swap them to [lat, lng] for Leaflet and our Backend DB
      const coordinates: [number, number][] = route.geometry.coordinates.map(
        (coord: [number, number]) => [coord[1], coord[0]]
      );

      return {
        distance_km: route.distance / 1000,
        duration_min: route.duration / 60,
        geometry: coordinates
      };
    } catch (err) {
      console.error('OSRM route error:', err);
      return null;
    }
  }
};
