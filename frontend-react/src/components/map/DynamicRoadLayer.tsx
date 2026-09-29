import React, { useMemo } from 'react';
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
  onChunkClick?: (latlng: { lat: number; lng: number }) => void;
}

export function DynamicRoadLayer({ routePoints, segmentIntelligence, activeLayer, onChunkClick }: DynamicRoadLayerProps) {
  const polylineChunks = useMemo(() => {
    if (!routePoints || routePoints.length < 2) return [];

    type RenderState = {
      color: string;
      weight: number;
      opacity: number;
      isTrafficOverlay?: boolean;
      trafficOpacity?: number;
      trafficColor?: string;
      hasBothHazards?: boolean;
    };

    const getRenderState = (intel: SegmentIntelligence | undefined): RenderState => {
      if (!intel || !intel.observed) {
        // Not yet scanned — dim dashed gray route preview
        return { color: '#64748b', weight: 3, opacity: 0.25 };
      }

      // ── TRAFFIC LAYER ──────────────────────────────────────────────
      if (activeLayer === 'traffic') {
        // Yellow → Orange → Red → Dark Red gradient
        const trafficColorMap = {
          LOW:      '#facc15', // Yellow
          MEDIUM:   '#f97316', // Orange
          HIGH:     '#ef4444', // Red
          CRITICAL: '#7f1d1d', // Dark Red
        };
        const trafficOpacityMap = { LOW: 0.6, MEDIUM: 0.75, HIGH: 0.9, CRITICAL: 1.0 };
        const color = intel.trafficDensity ? trafficColorMap[intel.trafficDensity] : '#22c55e';
        const intensity = intel.trafficDensity ? trafficOpacityMap[intel.trafficDensity] : 0.5;
        // Gray road base + colored traffic overlay
        return {
          color: '#475569',
          weight: 4,
          opacity: 0.3,
          isTrafficOverlay: true,
          trafficOpacity: intensity,
          trafficColor: color,
        };
      }

      // ── POTHOLE LAYER ──────────────────────────────────────────────
      if (activeLayer === 'potholes') {
        if (intel.pothole) return { color: '#ef4444', weight: 10, opacity: 1.0 }; // RED
        return { color: '#22c55e', weight: 6, opacity: 0.85 };                      // GREEN
      }

      // ── WATERLOGGING LAYER ─────────────────────────────────────────
      if (activeLayer === 'waterlogging') {
        if (intel.waterlogging) return { color: '#3b82f6', weight: 10, opacity: 1.0 }; // BLUE
        return { color: '#22c55e', weight: 6, opacity: 0.85 };                           // GREEN
      }

      // ── ROADS / OBSERVED (Default) ─────────────────────────────────
      if (intel.pothole && intel.waterlogging) {
        // Both hazards — solid red base with dashed blue overlay applied separately
        return { color: '#ef4444', weight: 10, opacity: 1.0, hasBothHazards: true };
      }
      if (intel.pothole)      return { color: '#ef4444', weight: 10, opacity: 1.0 }; // RED
      if (intel.waterlogging) return { color: '#3b82f6', weight: 10, opacity: 1.0 }; // BLUE

      // ── CLEAN / OBSERVED, NO ISSUES ────────────────────────────────
      return { color: '#22c55e', weight: 6, opacity: 0.95 }; // GREEN
    };

    const serializeState = (s: RenderState) =>
      `${s.color}-${s.weight}-${s.opacity}-${s.isTrafficOverlay}-${s.trafficColor}-${s.hasBothHazards}`;

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
        <React.Fragment key={`chunk-${index}`}>
          {/* Base Road Line */}
          <Polyline
            positions={chunk.positions}
            pathOptions={{
              color: chunk.state.color,
              weight: chunk.state.weight,
              opacity: chunk.state.opacity,
            }}
            eventHandlers={onChunkClick ? {
              click: (e) => onChunkClick(e.latlng)
            } : undefined}
          />

          {/* Dashed Blue Waterlogging overlay when BOTH hazards present */}
          {chunk.state.hasBothHazards && (
            <Polyline
              positions={chunk.positions}
              pathOptions={{
                color: '#60a5fa',
                weight: chunk.state.weight - 2,
                opacity: 0.9,
                dashArray: '8, 12',
              }}
              eventHandlers={onChunkClick ? {
                click: (e) => onChunkClick(e.latlng)
              } : undefined}
            />
          )}

          {/* Traffic density glowing color overlay */}
          {chunk.state.isTrafficOverlay && (
            <Polyline
              positions={chunk.positions}
              pathOptions={{
                color: chunk.state.trafficColor!,
                weight: 8,
                opacity: chunk.state.trafficOpacity!,
                lineCap: 'round',
                lineJoin: 'round',
              }}
            />
          )}
        </React.Fragment>
      ))}
    </>
  );
}
