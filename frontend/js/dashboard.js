/**
 * Urban Watch — Dashboard Updater
 *
 * Updates status panels from real API data.
 * Never invents values — shows "Not available" if data isn't present.
 */

'use strict';

const Dashboard = {
  _results: null,

  /**
   * Update device panel from GET /api/ai/device response.
   */
  updateDevice(deviceData) {
    if (!deviceData) return;

    const deviceStr = deviceData.device || 'Not available';
    document.getElementById('info-device').textContent = deviceStr;
    document.getElementById('info-mps').textContent   = deviceData.mps_available ? '✓ Available' : '✗ Not available';
    document.getElementById('info-cuda').textContent  = deviceData.cuda_available ? '✓ Available' : '✗ Not available';
    document.getElementById('info-torch').textContent = deviceData.torch_version || '—';

    const pill   = document.getElementById('device-pill');
    const dot    = document.getElementById('device-dot');
    const label  = document.getElementById('device-label');

    label.textContent = deviceStr.toUpperCase();
    dot.classList.add('active');

    if (deviceStr.includes('mps'))  pill.style.borderColor = 'rgba(6,182,212,0.4)';
    if (deviceStr.includes('cuda')) pill.style.borderColor = 'rgba(99,102,241,0.4)';
  },

  /**
   * Update model panel from processing config.
   */
  updateModelInfo(processingConfig) {
    if (!processingConfig) return;
    document.getElementById('info-model').textContent    = processingConfig.model_name || '—';
    document.getElementById('info-imgsz').textContent   = processingConfig.imgsz ? `${processingConfig.imgsz}px` : '—';
    document.getElementById('info-conf').textContent    = processingConfig.confidence_threshold != null
      ? processingConfig.confidence_threshold.toFixed(2)
      : '—';
    document.getElementById('info-interval').textContent = processingConfig.frame_interval != null
      ? `Every ${processingConfig.frame_interval} frame(s)`
      : '—';
  },

  /**
   * Update performance panel from timing data.
   */
  updatePerformance(timing) {
    if (!timing || !timing.total_frame) return;
    const t = timing.total_frame;
    document.getElementById('perf-fps').textContent     = t.fps != null   ? t.fps.toFixed(1)       : '—';
    document.getElementById('perf-frames').textContent  = t.count != null ? t.count.toString()     : '—';

    if (timing.tracking && timing.tracking.mean_ms != null) {
      document.getElementById('perf-inference').textContent = timing.tracking.mean_ms.toFixed(1);
    }

    if (timing.tracking_quality) {
      document.getElementById('perf-tracks').textContent =
        timing.tracking_quality.id_switches != null
          ? timing.tracking_quality.id_switches.toString()
          : '—';
    }
  },

  /**
   * Update vehicle count panel from vehicle_counts.
   */
  updateVehicleCounts(vehicleCounts) {
    if (!vehicleCounts) return;

    const total = vehicleCounts.total_unique_vehicles;
    document.getElementById('total-vehicle-badge').textContent = total != null ? total : '0';

    const byClass = vehicleCounts.by_class || {};
    const keys = ['car', 'motorcycle', 'bus', 'truck', 'bicycle', 'person'];

    for (const key of keys) {
      const el = document.getElementById(`count-${key}`);
      if (el) {
        const v = byClass[key];
        el.textContent = v != null ? v : '0';
      }
    }
  },

  /**
   * Update live detection list from current frame's tracks.
   */
  updateDetectionList(tracks) {
    const list = document.getElementById('detection-list');
    const badge = document.getElementById('detection-count-badge');

    if (!tracks || tracks.length === 0) {
      badge.textContent = '0';
      list.innerHTML = '<p class="empty-state">No detections in current frame.</p>';
      return;
    }

    badge.textContent = tracks.length;

    list.innerHTML = tracks.slice(0, 20).map(t => {
      const conf = t.confidence || 0;
      const confClass = conf >= 0.7 ? 'conf-high' : conf >= 0.4 ? 'conf-mid' : 'conf-low';
      const confText = conf > 0 ? `${(conf * 100).toFixed(0)}%` : '—';
      const trackId  = t.track_id != null ? `#${t.track_id}` : '';

      return `
        <div class="detection-item">
          <span class="detection-class">${t.class_name || 'unknown'}</span>
          ${trackId ? `<span class="detection-id">${trackId}</span>` : ''}
          <span class="detection-conf ${confClass}">${confText}</span>
        </div>
      `.trim();
    }).join('');

    if (tracks.length > 20) {
      list.innerHTML += `<p class="empty-state" style="padding:8px">+${tracks.length - 20} more</p>`;
    }
  },

  /**
   * Update traffic density panel.
   */
  updateDensity(densityWindows, currentTime) {
    const badge = document.getElementById('density-badge');
    const countEl = document.getElementById('density-vehicle-count');
    const windowsEl = document.getElementById('density-windows');

    if (!densityWindows || densityWindows.length === 0) {
      badge.textContent = '—';
      badge.className = 'density-level-badge';
      countEl.textContent = '— vehicles / 5s window';
      windowsEl.innerHTML = '';
      return;
    }

    // Find current window for live display
    const currentWindow = densityWindows.find(
      w => currentTime >= w.window_start && currentTime < w.window_end
    ) || densityWindows[densityWindows.length - 1];

    if (currentWindow) {
      const level = currentWindow.density_level || 'unknown';
      badge.textContent = level.toUpperCase();
      badge.className = `density-level-badge ${level}`;
      countEl.textContent = `${currentWindow.unique_vehicle_count} vehicles / 5s window`;
    }

    // Density timeline
    windowsEl.innerHTML = densityWindows.map(w => {
      const level = w.density_level || 'unknown';
      const start = w.window_start.toFixed(0);
      const end   = w.window_end.toFixed(0);
      return `
        <div class="density-window-item">
          <span class="window-time">${start}s – ${end}s</span>
          <span class="window-count">${w.unique_vehicle_count}</span>
          <span class="window-level ${level}">${level.toUpperCase()}</span>
        </div>
      `.trim();
    }).join('');
  },

  /**
   * Update Pothole Intelligence Panel.
   */
  updatePotholes(potholeEvents) {
    if (!potholeEvents) return;
    
    let confirmed = 0;
    let suppressed = 0;
    let outside = 0;
    let highestSeverity = 'LOW';
    
    const severityRank = { 'LOW': 1, 'MEDIUM': 2, 'HIGH': 3 };

    for (const ev of potholeEvents) {
      if (ev.status === 'confirmed' || ev.status === 'resolved') {
        confirmed++;
        if (severityRank[ev.severity_score] > severityRank[highestSeverity]) {
          highestSeverity = ev.severity_score;
        }
      } else if (ev.status === 'suppressed') {
        suppressed++;
      } else if (ev.status === 'outside_road_roi') {
        outside++;
      }
    }
    
    document.getElementById('pothole-total-badge').textContent = potholeEvents.length;
    document.getElementById('pothole-confirmed').textContent = confirmed;
    document.getElementById('pothole-suppressed').textContent = suppressed;
    document.getElementById('pothole-outside').textContent = outside;
    
    const sevEl = document.getElementById('pothole-severity');
    sevEl.textContent = confirmed > 0 ? highestSeverity : '—';
    if (highestSeverity === 'HIGH') sevEl.style.color = '#ef4444';
    else if (highestSeverity === 'MEDIUM') sevEl.style.color = '#f97316';
    else if (highestSeverity === 'LOW') sevEl.style.color = '#eab308';
  },

  /**
   * Store full results for periodic updates.
   */
  setResults(results) {
    this._results = results;
    if (!results) return;

    if (results.processing) this.updateModelInfo(results.processing);
    if (results.timing)     this.updatePerformance(results.timing);
    if (results.vehicle_counts) this.updateVehicleCounts(results.vehicle_counts);
    if (results.density_windows) this.updateDensity(results.density_windows, 0);
    if (results.pothole_events) this.updatePotholes(results.pothole_events);
  },

  /**
   * Update live panels based on current video time.
   */
  updateForTime(currentTime) {
    if (!this._results) return;

    // Find current frame
    const frames = this._results.frames || [];
    let frame = null;
    let lo = 0, hi = frames.length - 1;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (frames[mid].timestamp <= currentTime) { frame = frames[mid]; lo = mid + 1; }
      else hi = mid - 1;
    }

    if (frame) {
      const tracks = frame.tracks && frame.tracks.length > 0 ? frame.tracks : frame.detections;
      this.updateDetectionList(tracks);
    }

    this.updateDensity(this._results.density_windows, currentTime);
  },
};
