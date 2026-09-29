import { useEffect, useRef } from 'react';

interface LabDetectionOverlayProps {
  videoRef: React.RefObject<HTMLVideoElement>;
  frames: any[];
  confidenceThreshold: number;
}

const drawPothole = (ctx: CanvasRenderingContext2D, item: any, eventId: any, scale: number, offsetX: number, offsetY: number) => {
  const [x1, y1, x2, y2] = item.bbox;
  const sx = x1 * scale + offsetX;
  const sy = y1 * scale + offsetY;
  const sw = (x2 - x1) * scale;
  const sh = (y2 - y1) * scale;

  // Generate a distinct color if there's a track ID, otherwise generic orange
  let color = '#f97316'; 
  if (eventId !== undefined && eventId !== null) {
    const colors = ['#ef4444', '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4'];
    color = colors[eventId % colors.length];
  }

  const alpha = 0.8;

  // Shadow glow
  ctx.shadowColor = color;
  ctx.shadowBlur = 6;

  // Bounding box
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.globalAlpha = alpha;
  ctx.strokeRect(sx, sy, sw, sh);

  // Label
  const eventIdStr = eventId !== undefined && eventId !== null ? `T#${eventId} ` : '';
  const confText = item.confidence !== undefined ? `${(item.confidence * 100).toFixed(0)}%` : '';
  const label = `${eventIdStr}${confText}`;

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

export function LabDetectionOverlay({ 
  videoRef, 
  frames, 
  confidenceThreshold 
}: LabDetectionOverlayProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafId = useRef<number | null>(null);

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

      if (!frames || !frames.length || (video.paused && video.currentTime === 0)) {
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

      // Draw potholes
      const potholes = frame.pothole_detections || [];
      const activeEvents = frame.active_pothole_event_ids || [];

      for (let i = 0; i < potholes.length; i++) {
        const pothole = potholes[i];
        if (pothole.confidence >= confidenceThreshold) {
          const eventId = activeEvents[i];
          drawPothole(ctx, pothole, eventId, scale, offsetX, offsetY);
        }
      }

      rafId.current = requestAnimationFrame(render);
    };

    render();

    return () => {
      if (rafId.current) cancelAnimationFrame(rafId.current);
    };
  }, [frames, confidenceThreshold, videoRef]);

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 pointer-events-none z-20"
      style={{ width: '100%', height: '100%' }}
    />
  );
}
