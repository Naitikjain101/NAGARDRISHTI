/**
 * Urban Watch — Canvas Overlay
 *
 * Draws AI detection boxes synchronized to video.currentTime.
 * NEVER pauses the video.
 * NEVER waits for AI before playing.
 * Uses requestAnimationFrame for smooth rendering.
 *
 * Algorithm:
 *   1. On each animation frame, read video.currentTime
 *   2. Binary-search the sorted frames array for latest timestamp ≤ currentTime
 *   3. Draw tracks from that frame
 *   4. If AI hasn't processed this section yet, draw nothing
 */

'use strict';

class DetectionOverlay {
  constructor(videoEl, canvasEl) {
    this.video = videoEl;
    this.canvas = canvasEl;
    this.ctx = canvasEl.getContext('2d');

    // Sorted array of frame results from AI
    this._frames = [];
    this._lastFrameIndex = -1;
    this._rafId = null;
    this._running = false;

    // Debug flag - set to true via console to see stats (window.DEBUG_OVERLAY)
    this.debugMode = false;

    // Color map for classes
    this._classColors = {
      'car':        '#6366f1',
      'motorcycle': '#06b6d4',
      'bus':        '#f59e0b',
      'truck':      '#ef4444',
      'bicycle':    '#10b981',
      'person':     '#8b5cf6',
    };
    this._defaultColor = '#94a3b8';

    // Bind resize
    this._resizeObserver = new ResizeObserver(() => this._resize());
    this._resizeObserver.observe(videoEl.parentElement);
  }

  /**
   * Set detection results from AI.
   * frames must be sorted by timestamp (ascending).
   */
  setFrames(frames) {
    this._frames = frames || [];
  }

  start() {
    if (this._running) return;
    this._running = true;
    this._resize();
    this._loop();
  }

  stop() {
    this._running = false;
    if (this._rafId) cancelAnimationFrame(this._rafId);
    this._rafId = null;
  }

  clear() {
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
  }

  _loop() {
    if (!this._running) return;
    this._render();
    this._rafId = requestAnimationFrame(() => this._loop());
  }

  _render() {
    const { video, canvas, ctx } = this;

    // Sync canvas size to actual rendered video size
    const rect = video.getBoundingClientRect();
    if (canvas.width !== rect.width || canvas.height !== rect.height) {
      canvas.width  = rect.width;
      canvas.height = rect.height;
    }

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (!this._frames.length || video.paused && video.currentTime === 0) return;

    const currentTime = video.currentTime;

    // Binary search: find latest frame with timestamp ≤ currentTime
    const frame = this._findFrame(currentTime);
    if (!frame) return;

    // Original video dimensions
    const origW = video.videoWidth;
    const origH = video.videoHeight;
    const cw = canvas.width;
    const ch = canvas.height;

    if (!origW || !origH) return;

    // Compute scale and offsets for object-fit: contain
    const scale = Math.min(cw / origW, ch / origH);
    const dispW = origW * scale;
    const dispH = origH * scale;
    const offsetX = (cw - dispW) / 2;
    const offsetY = (ch - dispH) / 2;

    // Draw vehicle tracks
    const vehicles = frame.vehicle_tracks && frame.vehicle_tracks.length > 0
      ? frame.vehicle_tracks
      : frame.detections || [];

    for (const item of vehicles) {
      this._drawBox(ctx, item, scale, offsetX, offsetY);
    }
    
    // Draw potholes
    const potholes = frame.pothole_detections || [];
    const activeEvents = frame.active_pothole_event_ids || [];
    
    for (let i = 0; i < potholes.length; i++) {
      const pothole = potholes[i];
      const eventId = activeEvents[i]; // aligned by index in some cases, or just use the event tracker
      this._drawPothole(ctx, pothole, eventId, scale, offsetX, offsetY);
    }

    // Draw waterlogging
    const waterlogs = frame.waterlogging_detections || [];
    for (const wl of waterlogs) {
      this._drawWaterlogging(ctx, wl, scale, offsetX, offsetY);
    }

    // Optional debug display
    if (window.DEBUG_OVERLAY || this.debugMode) {
      ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
      ctx.fillRect(10, 10, 250, 90);
      ctx.fillStyle = '#0f0';
      ctx.font = '12px monospace';
      ctx.fillText(`SOURCE: ${origW}x${origH}`, 20, 30);
      ctx.fillText(`DISPLAY: ${Math.round(dispW)}x${Math.round(dispH)}`, 20, 45);
      ctx.fillText(`OFFSET: ${offsetX.toFixed(1)}, ${offsetY.toFixed(1)}`, 20, 60);
      ctx.fillText(`SCALE: ${scale.toFixed(3)}, ${scale.toFixed(3)}`, 20, 75);
    }
  }
  
  _drawWaterlogging(ctx, item, scale, offsetX, offsetY) {
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
    const ratioStr = item.area_ratio ? ` (Area: ${(item.area_ratio * 100).toFixed(0)}%)` : '';
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
  }

  _drawPothole(ctx, item, eventId, scale, offsetX, offsetY) {
    const [x1, y1, x2, y2] = item.bbox;
    const sx = x1 * scale + offsetX;
    const sy = y1 * scale + offsetY;
    const sw = (x2 - x1) * scale;
    const sh = (y2 - y1) * scale;

    let color = '#f97316'; // MEDIUM default
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
  }

  _drawBox(ctx, item, scale, offsetX, offsetY) {
    const [x1, y1, x2, y2] = item.bbox;
    const sx = x1 * scale + offsetX;
    const sy = y1 * scale + offsetY;
    const sw = (x2 - x1) * scale;
    const sh = (y2 - y1) * scale;

    const color = this._classColors[item.class_name] || this._defaultColor;
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
  }

  _findFrame(currentTime) {
    if (!this._frames.length) return null;

    // Binary search for latest frame with timestamp ≤ currentTime
    let lo = 0, hi = this._frames.length - 1, result = null;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (this._frames[mid].timestamp <= currentTime) {
        result = this._frames[mid];
        lo = mid + 1;
      } else {
        hi = mid - 1;
      }
    }
    return result;
  }

  _resize() {
    if (!this.video.parentElement) return;
    const rect = this.video.getBoundingClientRect();
    this.canvas.width  = rect.width;
    this.canvas.height = rect.height;
  }
}

