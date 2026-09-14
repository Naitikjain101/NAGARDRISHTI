/**
 * Urban Watch — Phase 19.5 AI Detection Overlay
 *
 * Renders per-frame AI detections on a canvas positioned over the video element.
 *
 * Data contract:
 *   frames[i].vehicle_tracks           → vehicle bboxes (always present)
 *   frames[i].pothole_detections       → pothole bboxes (restored in Phase 19.5)
 *   frames[i].active_pothole_event_ids → parallel to pothole_detections (1:1)
 *   frames[i].waterlogging_detections  → waterlogging polygons + area_ratio (restored)
 *   frames[i].active_waterlogging_event_ids → parallel to waterlogging_detections (1:1)
 *
 * The overlay:
 *   1. Binary-searches frames by video.currentTime
 *   2. Clears canvas on every RAF tick
 *   3. Draws only detections that belong to CONFIRMED events
 *   4. Correctly transforms pixel coords from source-video space → canvas space
 */
import { useEffect, useRef } from 'react';

interface DetectionOverlayProps {
  videoRef: React.RefObject<HTMLVideoElement>;
  frames: any[];
  potholeEvents?: any[];
  waterloggingEvents?: any[];
  showVehicles?: boolean;
  showPotholes?: boolean;
  showWaterlogging?: boolean;
  showDebug?: boolean;
}

const CLASS_COLORS: Record<string, string> = {
  'car': '#6366f1',
  'motorcycle': '#06b6d4',
  'bus': '#f59e0b',
  'truck': '#ef4444',
  'bicycle': '#10b981',
  'person': '#8b5cf6',
};
const DEFAULT_COLOR = '#94a3b8';

// ─── Waterlogging Draw ────────────────────────────────────────────────────────

const drawWaterlogging = (
  ctx: CanvasRenderingContext2D,
  item: any,
  origW: number,
  origH: number,
  scale: number,
  offsetX: number,
  offsetY: number
) => {
  const [x1, y1, x2, y2] = item.bbox;
  const sx = x1 * scale + offsetX;
  const sy = y1 * scale + offsetY;
  const sw = (x2 - x1) * scale;
  const sh = (y2 - y1) * scale;

  const color = '#3b82f6'; // blue-500
  const conf = item.confidence ?? 0.8;

  ctx.save();

  // ── Draw segmentation polygon if present ──────────────────────────────────
  if (item.polygon && item.polygon.length > 2) {
    ctx.beginPath();
    for (let i = 0; i < item.polygon.length; i++) {
      const px = item.polygon[i][0] * scale + offsetX;
      const py = item.polygon[i][1] * scale + offsetY;
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    }
    ctx.closePath();

    // Filled mask — semi-transparent blue
    ctx.globalAlpha = 0.35;
    ctx.fillStyle = color;
    ctx.fill();

    // Mask outline
    ctx.globalAlpha = 0.9;
    ctx.lineWidth = 1.5;
    ctx.strokeStyle = color;
    ctx.stroke();
  } else {
    // Fallback: bbox outline when no polygon
    ctx.globalAlpha = 0.85;
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.strokeRect(sx, sy, sw, sh);
  }

  // ── Frame coverage calculation ─────────────────────────────────────────────
  // area_ratio from the backend is Shoelace(polygon) / bbox_area.
  // True frame coverage = (area_ratio × bbox_area) / frame_area
  // where bbox_area and frame_area are in source-pixel space.
  let frameCoveragePercent: number | null = null;
  if (item.area_ratio != null && item.area_ratio > 0 && origW > 0 && origH > 0) {
    const bboxArea = (x2 - x1) * (y2 - y1);
    const frameArea = origW * origH;
    const polygonAreaPixels = item.area_ratio * bboxArea;
    frameCoveragePercent = Math.min(100, (polygonAreaPixels / frameArea) * 100);
  }

  // ── Label ──────────────────────────────────────────────────────────────────
  ctx.globalAlpha = 1;

  const coverageStr = frameCoveragePercent != null
    ? `${frameCoveragePercent.toFixed(0)}% Frame Cov`
    : '';
  const confStr = `Conf ${(conf * 100).toFixed(0)}%`;
  const line1 = `WATER · TEST`;
  const line2 = coverageStr ? `${coverageStr} · ${confStr}` : confStr;

  ctx.font = 'bold 11px Inter, system-ui, sans-serif';
  const w1 = ctx.measureText(line1).width;
  ctx.font = '10px Inter, system-ui, sans-serif';
  const w2 = ctx.measureText(line2).width;
  const labelW = Math.max(w1, w2) + 14;
  const labelH = 36;
  const labelY = sy > labelH + 6 ? sy - labelH - 3 : sy + 3;
  const labelX = sx - 1;

  // Label background
  ctx.globalAlpha = 0.88;
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.roundRect(labelX, labelY, labelW, labelH, 4);
  ctx.fill();

  // Label text
  ctx.globalAlpha = 1;
  ctx.fillStyle = '#ffffff';
  ctx.font = 'bold 11px Inter, system-ui, sans-serif';
  ctx.fillText(line1, labelX + 6, labelY + 14);
  ctx.font = '10px Inter, system-ui, sans-serif';
  ctx.fillText(line2, labelX + 6, labelY + 28);

  ctx.restore();
};

// ─── Pothole Draw ─────────────────────────────────────────────────────────────

const drawPothole = (
  ctx: CanvasRenderingContext2D,
  item: any,
  eventId: number | undefined,
  scale: number,
  offsetX: number,
  offsetY: number
) => {
  const [x1, y1, x2, y2] = item.bbox;
  const sx = x1 * scale + offsetX;
  const sy = y1 * scale + offsetY;
  const sw = (x2 - x1) * scale;
  const sh = (y2 - y1) * scale;

  const color = '#f97316'; // orange-500
  const conf = item.confidence ?? 0.8;

  ctx.save();

  // Glow shadow
  ctx.shadowColor = color;
  ctx.shadowBlur = 10;

  // Bounding box
  ctx.globalAlpha = 0.9;
  ctx.strokeStyle = color;
  ctx.lineWidth = 2.5;
  ctx.strokeRect(sx, sy, sw, sh);

  // Corner accents
  ctx.shadowBlur = 0;
  ctx.globalAlpha = 1;
  ctx.lineWidth = 3;
  const cs = Math.min(12, sw * 0.2, sh * 0.2);
  // TL
  ctx.beginPath(); ctx.moveTo(sx, sy + cs); ctx.lineTo(sx, sy); ctx.lineTo(sx + cs, sy); ctx.stroke();
  // TR
  ctx.beginPath(); ctx.moveTo(sx + sw - cs, sy); ctx.lineTo(sx + sw, sy); ctx.lineTo(sx + sw, sy + cs); ctx.stroke();
  // BL
  ctx.beginPath(); ctx.moveTo(sx, sy + sh - cs); ctx.lineTo(sx, sy + sh); ctx.lineTo(sx + cs, sy + sh); ctx.stroke();
  // BR
  ctx.beginPath(); ctx.moveTo(sx + sw - cs, sy + sh); ctx.lineTo(sx + sw, sy + sh); ctx.lineTo(sx + sw, sy + sh - cs); ctx.stroke();

  // Label
  const confStr = `${(conf * 100).toFixed(0)}%`;
  const eidStr = eventId !== undefined ? ` · E${eventId}` : '';
  const label = `POTHOLE ${confStr}${eidStr}`;

  ctx.font = 'bold 11px Inter, system-ui, sans-serif';
  const textW = ctx.measureText(label).width;
  const labelH = 20;
  const labelY = sy > labelH + 4 ? sy - labelH - 2 : sy + 2;

  ctx.fillStyle = color;
  ctx.globalAlpha = 0.88;
  ctx.beginPath();
  ctx.roundRect(sx - 1, labelY, textW + 12, labelH, 4);
  ctx.fill();

  ctx.globalAlpha = 1;
  ctx.fillStyle = '#ffffff';
  ctx.fillText(label, sx + 5, labelY + 14);

  ctx.restore();
};

// ─── Vehicle Draw ─────────────────────────────────────────────────────────────

const drawBox = (
  ctx: CanvasRenderingContext2D,
  item: any,
  scale: number,
  offsetX: number,
  offsetY: number,
  showDebug: boolean = false
) => {
  const [x1, y1, x2, y2] = item.bbox;
  const sx = x1 * scale + offsetX;
  const sy = y1 * scale + offsetY;
  const sw = (x2 - x1) * scale;
  const sh = (y2 - y1) * scale;

  const color = CLASS_COLORS[(item.class_name || '').toLowerCase()] || DEFAULT_COLOR;
  const conf = item.confidence ?? 0.8;

  ctx.save();
  ctx.shadowColor = color;
  ctx.shadowBlur = 8;
  ctx.globalAlpha = Math.max(0.4, Math.min(1, conf));
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.strokeRect(sx, sy, sw, sh);

  ctx.globalAlpha = 1;
  ctx.shadowBlur = 0;
  const cs = Math.min(12, sw * 0.2, sh * 0.2);
  ctx.lineWidth = 3;
  // TL
  ctx.beginPath(); ctx.moveTo(sx, sy + cs); ctx.lineTo(sx, sy); ctx.lineTo(sx + cs, sy); ctx.stroke();
  // TR
  ctx.beginPath(); ctx.moveTo(sx + sw - cs, sy); ctx.lineTo(sx + sw, sy); ctx.lineTo(sx + sw, sy + cs); ctx.stroke();
  // BL
  ctx.beginPath(); ctx.moveTo(sx, sy + sh - cs); ctx.lineTo(sx, sy + sh); ctx.lineTo(sx + cs, sy + sh); ctx.stroke();
  // BR
  ctx.beginPath(); ctx.moveTo(sx + sw - cs, sy + sh); ctx.lineTo(sx + sw, sy + sh); ctx.lineTo(sx + sw, sy + sh - cs); ctx.stroke();

  const trackId = item.track_id !== undefined ? ` #${item.track_id}` : '';
  const confStr = ` ${(conf * 100).toFixed(0)}%`;
  let label = `${item.class_name}${trackId}${confStr}`;

  if (showDebug && item.raw_class && item.raw_class !== item.class_name) {
    label = `RAW: ${item.raw_class} / STABLE: ${item.class_name}${trackId}`;
  }

  ctx.font = '600 11px Inter, system-ui, sans-serif';
  const textW = ctx.measureText(label).width;
  const labelH = 20;
  const labelY = sy > labelH + 4 ? sy - labelH - 2 : sy + 2;

  ctx.fillStyle = color;
  ctx.globalAlpha = 0.85;
  ctx.beginPath();
  ctx.roundRect(sx - 1, labelY, textW + 12, labelH, 4);
  ctx.fill();

  ctx.globalAlpha = 1;
  ctx.fillStyle = '#ffffff';
  ctx.fillText(label, sx + 5, labelY + 14);
  ctx.restore();
};

// ─── Main Component ───────────────────────────────────────────────────────────

export function DetectionOverlay({ 
  videoRef, 
  frames, 
  potholeEvents = [],
  waterloggingEvents = [],
  showVehicles = true, 
  showPotholes = true, 
  showWaterlogging = true,
  showDebug = false
}: DetectionOverlayProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafId = useRef<number | null>(null);

  // Build confirmed event ID sets for O(1) lookup
  const confirmedPotholeIds = useRef<Set<number>>(new Set());
  const confirmedWaterloggingIds = useRef<Set<number>>(new Set());

  useEffect(() => {
    confirmedPotholeIds.current = new Set(
      potholeEvents
        .filter(e => e.status === 'confirmed' || e.status === 'CONFIRMED')
        .map(e => e.event_id)
    );
    confirmedWaterloggingIds.current = new Set(
      waterloggingEvents
        .filter(e => e.status === 'confirmed' || e.status === 'CONFIRMED')
        .map(e => e.event_id)
    );
  }, [potholeEvents, waterloggingEvents]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const video = videoRef.current;
    if (!canvas || !video) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const render = () => {
      // ── Sync canvas size to the video element's rendered size ──────────────
      // The video element uses object-fit: contain so the actual video pixels
      // occupy a sub-rectangle of the element's bounding box (with letterboxing).
      // The canvas must cover the entire element, and we compute offsets below.
      const rect = video.getBoundingClientRect();
      if (canvas.width !== Math.round(rect.width) || canvas.height !== Math.round(rect.height)) {
        canvas.width = Math.round(rect.width);
        canvas.height = Math.round(rect.height);
      }

      // Always clear on every tick — no stale frame contents
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      if (!frames.length || !video.readyState) {
        rafId.current = requestAnimationFrame(render);
        return;
      }

      const currentTime = video.currentTime;

      // ── Binary search: find the frame whose timestamp <= currentTime ────────
      let lo = 0, hi = frames.length - 1;
      let frame: any = null;
      while (lo <= hi) {
        const mid = (lo + hi) >> 1;
        if (frames[mid].timestamp <= currentTime + 0.001) { // +1ms tolerance
          frame = frames[mid];
          lo = mid + 1;
        } else {
          hi = mid - 1;
        }
      }

      if (!frame) {
        rafId.current = requestAnimationFrame(render);
        return;
      }

      const origW = video.videoWidth;
      const origH = video.videoHeight;
      const cw = canvas.width;
      const ch = canvas.height;

      if (!origW || !origH) {
        rafId.current = requestAnimationFrame(render);
        return;
      }

      // ── Compute scale/offset for object-fit: contain letterboxing ──────────
      // This ensures bbox coordinates (in source video pixels) are correctly
      // mapped to canvas pixels regardless of display size or aspect ratio.
      const scale = Math.min(cw / origW, ch / origH);
      const dispW = origW * scale;
      const dispH = origH * scale;
      const offsetX = (cw - dispW) / 2;
      const offsetY = (ch - dispH) / 2;

      // ── Draw: Vehicles / Persons ───────────────────────────────────────────
      if (showVehicles) {
        const vehicles = (frame.vehicle_tracks && frame.vehicle_tracks.length > 0)
          ? frame.vehicle_tracks
          : (frame.detections || []);
        for (const item of vehicles) {
          if (item.bbox) drawBox(ctx, item, scale, offsetX, offsetY, showDebug);
        }
      }

      // ── Draw: Potholes ────────────────────────────────────────────────────
      if (showPotholes) {
        const potholes = frame.pothole_detections || [];
        const activeEventIds = frame.active_pothole_event_ids || [];

        for (let i = 0; i < potholes.length; i++) {
          const det = potholes[i];
          const eventId = activeEventIds[i];

          // Only render detections that belong to a confirmed event
          if (eventId !== undefined && confirmedPotholeIds.current.has(eventId)) {
            drawPothole(ctx, det, eventId, scale, offsetX, offsetY);
          }
        }
      }

      // ── Draw: Waterlogging ────────────────────────────────────────────────
      if (showWaterlogging) {
        const waterlogs = frame.waterlogging_detections || [];
        const activeEventIds = frame.active_waterlogging_event_ids || [];

        for (let i = 0; i < waterlogs.length; i++) {
          const det = waterlogs[i];
          const eventId = activeEventIds[i];

          // Only render detections that belong to a confirmed event
          if (eventId !== undefined && confirmedWaterloggingIds.current.has(eventId)) {
            drawWaterlogging(ctx, det, origW, origH, scale, offsetX, offsetY);
          }
        }
      }

      rafId.current = requestAnimationFrame(render);
    };

    rafId.current = requestAnimationFrame(render);

    return () => {
      if (rafId.current) cancelAnimationFrame(rafId.current);
    };
  }, [frames, videoRef, showVehicles, showPotholes, showWaterlogging]);

  return (
    <canvas
      ref={canvasRef}
      className="absolute top-0 left-0 w-full h-full pointer-events-none z-10"
    />
  );
}
