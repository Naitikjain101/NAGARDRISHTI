import { useEffect, useRef } from 'react';

interface DetectionOverlayProps {
  videoRef: React.RefObject<HTMLVideoElement>;
  frames: any[];
  potholeEvents?: any[];
  waterloggingEvents?: any[];
  showVehicles?: boolean;
  showPotholes?: boolean;
  showWaterlogging?: boolean;
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

const drawWaterlogging = (ctx: CanvasRenderingContext2D, item: any, scale: number, offsetX: number, offsetY: number) => {
  const [x1, y1, x2, y2] = item.bbox;
  const sx = x1 * scale + offsetX;
  const sy = y1 * scale + offsetY;
  const sw = (x2 - x1) * scale;
  const sh = (y2 - y1) * scale;

  const color = '#3498db'; // Distinct blue for water
  const alpha = Math.max(0.4, Math.min(1, item.confidence || 0.8));

  // Draw Polygon if it exists
  if (item.polygon && item.polygon.length > 2) {
    ctx.beginPath();
    for (let i = 0; i < item.polygon.length; i++) {
      const px = item.polygon[i][0] * scale + offsetX;
      const py = item.polygon[i][1] * scale + offsetY;
      if (i === 0) {
        ctx.moveTo(px, py);
      } else {
        ctx.lineTo(px, py);
      }
    }
    ctx.closePath();

    // Fill the area
    ctx.globalAlpha = alpha * 0.4;
    ctx.fillStyle = color;
    ctx.fill();

    // Outline the area
    ctx.globalAlpha = alpha;
    ctx.lineWidth = 1.5;
    ctx.strokeStyle = color;
    ctx.stroke();
  } else {
    // Fallback to bounding box if no polygon
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.globalAlpha = alpha;
    ctx.strokeRect(sx, sy, sw, sh);
  }

  // Label with Area Ratio if available
  ctx.globalAlpha = 1;
  const ratioStr = item.area_ratio ? ` (Density: ${(item.area_ratio * 100).toFixed(0)}%)` : '';
  const label = `WATER ${Math.round(item.confidence * 100)}%${ratioStr}`;

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
};

const drawPothole = (ctx: CanvasRenderingContext2D, item: any, eventId: any, scale: number, offsetX: number, offsetY: number) => {
  const [x1, y1, x2, y2] = item.bbox;
  const sx = x1 * scale + offsetX;
  const sy = y1 * scale + offsetY;
  const sw = (x2 - x1) * scale;
  const sh = (y2 - y1) * scale;

  const color = '#f97316'; // MEDIUM default
  const alpha = Math.max(0.4, Math.min(1, item.confidence || 0.8));

  // Shadow glow
  ctx.shadowColor = color;
  ctx.shadowBlur = 8;

  // Bounding box
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.globalAlpha = alpha;
  ctx.strokeRect(sx, sy, sw, sh);

  // Label
  const eventIdStr = eventId !== undefined ? `E${eventId}` : '';
  const confText = item.confidence !== undefined ? ` ${(item.confidence * 100).toFixed(0)}%` : '';
  const label = `pothole ${eventIdStr}${confText}`;

  ctx.font = '600 11px Inter, system-ui, sans-serif';
  const textW = ctx.measureText(label).width;
  const labelH = 20;
  const labelY = sy > labelH + 4 ? sy - labelH - 2 : sy + 2;

  // Label background
  ctx.fillStyle = color;
  ctx.globalAlpha = 0.85;
  ctx.beginPath();
  ctx.roundRect(sx - 1, labelY, textW + 12, labelH, 4);
  ctx.fill();

  // Label text
  ctx.globalAlpha = 1;
  ctx.fillStyle = '#ffffff';
  ctx.fillText(label, sx + 5, labelY + 14);
  ctx.shadowBlur = 0;
};

const drawBox = (ctx: CanvasRenderingContext2D, item: any, scale: number, offsetX: number, offsetY: number) => {
  const [x1, y1, x2, y2] = item.bbox;
  const sx = x1 * scale + offsetX;
  const sy = y1 * scale + offsetY;
  const sw = (x2 - x1) * scale;
  const sh = (y2 - y1) * scale;

  const color = CLASS_COLORS[item.class_name] || DEFAULT_COLOR;
  const alpha = Math.max(0.4, Math.min(1, item.confidence || 0.8));

  // Shadow glow
  ctx.shadowColor = color;
  ctx.shadowBlur = 8;

  // Bounding box
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.globalAlpha = alpha;
  ctx.strokeRect(sx, sy, sw, sh);

  // Corner accents
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

  // Label
  const trackId = item.track_id !== undefined ? `#${item.track_id}` : '';
  const confText = item.confidence !== undefined ? ` ${(item.confidence * 100).toFixed(0)}%` : '';
  const label = `${item.class_name}${trackId ? ' ' + trackId : ''}${confText}`;

  ctx.font = '600 11px Inter, system-ui, sans-serif';
  const textW = ctx.measureText(label).width;
  const labelH = 20;
  const labelY = sy > labelH + 4 ? sy - labelH - 2 : sy + 2;

  // Label background
  ctx.fillStyle = color;
  ctx.globalAlpha = 0.85;
  ctx.beginPath();
  ctx.roundRect(sx - 1, labelY, textW + 12, labelH, 4);
  ctx.fill();

  // Label text
  ctx.globalAlpha = 1;
  ctx.fillStyle = '#ffffff';
  ctx.fillText(label, sx + 5, labelY + 14);
};

export function DetectionOverlay({ 
  videoRef, 
  frames, 
  potholeEvents = [],
  waterloggingEvents = [],
  showVehicles = true, 
  showPotholes = true, 
  showWaterlogging = true 
}: DetectionOverlayProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafId = useRef<number | null>(null);

  // Create sets of confirmed event IDs for fast lookup
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
      // Sync canvas size to actual rendered video size
      const rect = video.getBoundingClientRect();
      if (canvas.width !== rect.width || canvas.height !== rect.height) {
        canvas.width = rect.width;
        canvas.height = rect.height;
      }

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      if (!frames.length || (video.paused && video.currentTime === 0)) {
        rafId.current = requestAnimationFrame(render);
        return;
      }

      const currentTime = video.currentTime;

      // Binary search for latest frame with timestamp <= currentTime
      let lo = 0, hi = frames.length - 1, frame = null;
      while (lo <= hi) {
        const mid = (lo + hi) >> 1;
        if (frames[mid].timestamp <= currentTime) {
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

      // Compute scale and offsets for object-fit: contain
      const scale = Math.min(cw / origW, ch / origH);
      const dispW = origW * scale;
      const dispH = origH * scale;
      const offsetX = (cw - dispW) / 2;
      const offsetY = (ch - dispH) / 2;

      // Draw vehicle tracks
      if (showVehicles) {
        const vehicles = frame.vehicle_tracks && frame.vehicle_tracks.length > 0
          ? frame.vehicle_tracks
          : frame.detections || [];

        for (const item of vehicles) {
          drawBox(ctx, item, scale, offsetX, offsetY);
        }
      }

      // Draw potholes
      if (showPotholes) {
        const potholes = frame.pothole_detections || [];
        const activeEvents = frame.active_pothole_event_ids || [];

        for (let i = 0; i < potholes.length; i++) {
          const pothole = potholes[i];
          const eventId = activeEvents[i];
          
          // Only draw if it belongs to a confirmed event
          if (eventId !== undefined && confirmedPotholeIds.current.has(eventId)) {
            drawPothole(ctx, pothole, eventId, scale, offsetX, offsetY);
          }
        }
      }

      // Draw waterlogging
      if (showWaterlogging) {
        const waterlogs = frame.waterlogging_detections || [];
        const activeEvents = frame.active_waterlogging_event_ids || [];

        for (let i = 0; i < waterlogs.length; i++) {
          const wl = waterlogs[i];
          const eventId = activeEvents[i];

          // Only draw if it belongs to a confirmed event
          if (eventId !== undefined && confirmedWaterloggingIds.current.has(eventId)) {
            drawWaterlogging(ctx, wl, scale, offsetX, offsetY);
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
