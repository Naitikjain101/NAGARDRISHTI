/**
 * Urban Watch — API Client
 *
 * Handles all communication with the FastAPI backend.
 * Never invents data — returns null/undefined if data isn't available.
 */

'use strict';

const API = {
  BASE: 'http://localhost:8000',  // Explicitly point to the FastAPI backend

  async getDevice() {
    const res = await fetch(`${API.BASE}/api/ai/device`);
    if (!res.ok) throw new Error(`Device fetch failed: ${res.status}`);
    return res.json();
  },

  async uploadVideo(file) {
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(`${API.BASE}/api/video/upload`, {
      method: 'POST',
      body: form,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'Upload failed');
    }
    return res.json();
  },

  async processVideo(videoId) {
    const res = await fetch(`${API.BASE}/api/ai/unified/process/${videoId}`, {
      method: 'POST',
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'Processing request failed');
    }
    return res.json();
  },

  async getStatus(videoId) {
    const res = await fetch(`${API.BASE}/api/ai/unified/status/${videoId}`);
    if (!res.ok) throw new Error(`Status fetch failed: ${res.status}`);
    return res.json();
  },

  async getResults(videoId) {
    const res = await fetch(`${API.BASE}/api/ai/unified/results/${videoId}`);
    if (res.status === 202) return null;  // Still processing
    if (res.status === 404) return null;  // Not ready
    if (!res.ok) throw new Error(`Results fetch failed: ${res.status}`);
    return res.json();
  },

  streamUrl(videoId, filename) {
    const suffix = (filename || '').split('.').pop() || 'mp4';
    return `${API.BASE}/api/video/${videoId}/stream`;
  },
};

// Polling manager — polls status until complete, then fetches results
class ProcessingPoller {
  constructor(videoId, onProgress, onComplete, onError) {
    this.videoId = videoId;
    this.onProgress = onProgress;
    this.onComplete = onComplete;
    this.onError = onError;
    this._timer = null;
    this._stopped = false;
  }

  start(intervalMs = 1000) {
    this._stopped = false;
    this._poll(intervalMs);
  }

  stop() {
    this._stopped = true;
    if (this._timer) clearTimeout(this._timer);
  }

  async _poll(intervalMs) {
    if (this._stopped) return;
    try {
      const status = await API.getStatus(this.videoId);
      this.onProgress(status);

      if (status.status === 'complete') {
        const results = await API.getResults(this.videoId);
        if (results) {
          this.onComplete(results);
          return;
        }
      } else if (status.status === 'failed') {
        this.onError(status.error || 'Processing failed');
        return;
      }

      this._timer = setTimeout(() => this._poll(intervalMs), intervalMs);
    } catch (err) {
      if (!this._stopped) {
        this._timer = setTimeout(() => this._poll(intervalMs), intervalMs * 2);
      }
    }
  }
}
