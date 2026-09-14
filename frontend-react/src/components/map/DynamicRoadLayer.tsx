import { useMemo } from 'react';
import { Polyline } from 'react-leaflet';
import { type RoutePoint } from '@/utils/routeInterpolation';

export interface SegmentIntelligence {
  observed: boolean;
  pothole: boolean;
  waterlogging: boolean;
  trafficDensity?: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
}

export type ActiveMapLayer = 'observed' | 'traffic' | 'potholes' | 'waterlogging';

interface DynamicRoadLayerProps {
  routePoints: RoutePoint[];
  segmentIntelligence: Record<number, SegmentIntelligence>;
  activeLayer: ActiveMapLayer;
}

export function DynamicRoadLayer({ routePoints, segmentIntelligence, activeLayer }: DynamicRoadLayerProps) {
  // Memoize the chunking algorithm to minimize react-leaflet rendering overhead
  const polylineChunks = useMemo(() => {
    if (!routePoints || routePoints.length < 2) return [];

    // We build a list of segments rather than chunks, because overlapping lines (red+blue) need to be drawn per segment
    // But for performance, we still group adjacent segments that share the exact same rendering state.
    
    // Define a rendering state string for easy comparison
    type RenderState = {
      color: string;
      weight: number;
      opacity: number;
      isTrafficOverlay?: boolean;
      trafficOpacity?: number;
      trafficColor?: string;
      isBoth?: boolean; // Pothole + Waterlogging
    };

    const getRenderState = (intel: SegmentIntelligence | undefined): RenderState => {
      if (!intel || !intel.observed) {
        return { color: '#475569', weight: 3, opacity: 0.3 }; // GRAY (Not observed)
      }

      if (activeLayer === 'traffic') {
        const trafficOpacityMap = { LOW: 0.3, MEDIUM: 0.6, HIGH: 0.8, CRITICAL: 1.0 };
        const trafficColorMap = { LOW: '#22c55e', MEDIUM: '#eab308', HIGH: '#f97316', CRITICAL: '#dc2626' };
        const intensity = intel.trafficDensity ? trafficOpacityMap[intel.trafficDensity] : 0.3;
        const color = intel.trafficDensity ? trafficColorMap[intel.trafficDensity] : '#22c55e';
        
        // Base observed gray road underneath, glowing traffic line on top
        return { color: '#475569', weight: 4, opacity: 0.4, isTrafficOverlay: true, trafficOpacity: intensity, trafficColor: color };
      }

      if (activeLayer === 'potholes') {
        if (intel.pothole) return { color: '#ef4444', weight: 6, opacity: 0.9 }; // RED
        return { color: '#22c55e', weight: 4, opacity: 0.6 }; // GREEN (Observed, no pothole filter focus)
      }

      if (activeLayer === 'waterlogging') {
        if (intel.waterlogging) return { color: '#3b82f6', weight: 6, opacity: 0.9 }; // BLUE
        return { color: '#22c55e', weight: 4, opacity: 0.6 }; // GREEN (Observed, no waterlogging filter focus)
      }

      // Default activeLayer === 'observed' (Road Health / Map Intelligence)
      if (intel.pothole && intel.waterlogging) {
        return { color: '#ef4444', weight: 6, opacity: 0.9, isBoth: true }; // RED + BLUE (handled in render)
      }
      if (intel.pothole) return { color: '#ef4444', weight: 6, opacity: 0.9 }; // RED
      if (intel.waterlogging) return { color: '#3b82f6', weight: 6, opacity: 0.9 }; // BLUE
      
      // OBSERVED — NO CONFIGURED ROAD CONDITION DETECTED
      return { color: '#22c55e', weight: 4, opacity: 0.8 }; // GREEN
    };

    const serializeState = (s: RenderState) => `${s.color}-${s.weight}-${s.opacity}-${s.isTrafficOverlay}-${s.trafficOpacity}-${s.trafficColor}-${s.isBoth}`;

    const chunks: { positions: [number, number][]; state: RenderState }[] = [];
    
    let currentChunkPositions: [number, number][] = [];
    let currentStateStr: string | null = null;
    let currentState: RenderState | null = null;

    for (let i = 0; i < routePoints.length - 1; i++) {
      const p1 = routePoints[i];
      const p2 = routePoints[i + 1];

      const segmentIntel = segmentIntelligence[i];
      const renderState = getRenderState(segmentIntel);
      const stateStr = serializeState(renderState);

      if (stateStr !== currentStateStr) {
        if (currentChunkPositions.length > 0 && currentState) {
          chunks.push({ positions: currentChunkPositions, state: currentState });
        }
        currentChunkPositions = [[p1.latitude, p1.longitude], [p2.latitude, p2.longitude]];
        currentStateStr = stateStr;
        currentState = renderState;
      } else {
        currentChunkPositions.push([p2.latitude, p2.longitude]);
      }
    }

    if (currentChunkPositions.length > 0 && currentState) {
      chunks.push({ positions: currentChunkPositions, state: currentState });
    }

    return chunks;
  }, [routePoints, segmentIntelligence, activeLayer]);

  return (
    <>
      {polylineChunks.map((chunk, index) => (
        <div key={`chunk-wrapper-${index}`}>
          {/* Base Layer */}
          <Polyline
            positions={chunk.positions}
            pathOptions={{ 
              color: chunk.state.color, 
              weight: chunk.state.weight,
              opacity: chunk.state.opacity,
            }}
          />
          
          {/* Waterlogging Dashed Overlay (When Both) */}
          {chunk.state.isBoth && (
            <Polyline
              positions={chunk.positions}
              pathOptions={{ 
                color: '#3b82f6', 
                weight: chunk.state.weight - 1, // Slightly thinner so red border is visible, or dashed
                opacity: 1.0,
                dashArray: '10, 15', // Dashed blue on solid red
              }}
            />
          )}

          {/* Traffic Density Glowing Overlay */}
          {chunk.state.isTrafficOverlay && (
            <Polyline
              positions={chunk.positions}
              pathOptions={{ 
                color: chunk.state.trafficColor, 
                weight: 8,
                opacity: chunk.state.trafficOpacity,
              }}
            />
          )}
        </div>
      ))}
    </>
  );
}

