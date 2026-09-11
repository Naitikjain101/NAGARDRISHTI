/**
 * Urban Watch — Main Application Controller
 *
 * Orchestrates:
 * 1. Device status fetch
 * 2. Video upload and playback (independent of AI)
 * 3. AI processing trigger
 * 4. Overlay and dashboard updates
 *
 * CRITICAL: HTML5 video plays immediately after upload.
 * AI processing runs in the background.
 * The two pipelines NEVER block each other.
 */

'use strict';

(function () {
  // ── State ──
  let currentVideoId  = null;
  let currentFilename = null;
  let overlay         = null;
  let poller          = null;
  let timeUpdateRaf   = null;

  // ── Elements ──
  const uploadZone   = document.getElementById('upload-zone');
  const fileInput    = document.getElementById('file-input');
  const browseBtn    = document.getElementById('browse-btn');
  const videoContainer = document.getElementById('video-container');
  const videoEl      = document.getElementById('main-video');
  const canvas       = document.getElementById('overlay-canvas');
  const metaBar      = document.getElementById('video-meta-bar');
  const actionBar    = document.getElementById('action-bar');
  const processBtn   = document.getElementById('process-btn');
  const progressWrap = document.getElementById('progress-wrap');
  const progressBar  = document.getElementById('progress-bar');
  const progressLabel= document.getElementById('progress-label');
  const processingBadge = document.getElementById('processing-badge');
  const doneBadge    = document.getElementById('done-badge');

  // ── Init ──
  async function init() {
    setupUploadZone();
    setupVideoEvents();
    setupProcessButton();
    await fetchDeviceInfo();
  }

  // ── Device Info ──
  async function fetchDeviceInfo() {
    try {
      const data = await API.getDevice();
      Dashboard.updateDevice(data);
    } catch (err) {
      console.warn('Device info unavailable:', err.message);
      document.getElementById('device-label').textContent = 'Device: Not available';
    }
  }

  // ── Upload Zone ──
  function setupUploadZone() {
    browseBtn.addEventListener('click', (e) => { e.stopPropagation(); fileInput.click(); });
    uploadZone.addEventListener('click', () => fileInput.click());
    uploadZone.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') fileInput.click(); });
    fileInput.addEventListener('change', (e) => handleFiles(e.target.files));

    uploadZone.addEventListener('dragover', (e) => { e.preventDefault(); uploadZone.classList.add('dragover'); });
    uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));
    uploadZone.addEventListener('drop', (e) => {
      e.preventDefault();
      uploadZone.classList.remove('dragover');
      handleFiles(e.dataTransfer.files);
    });
  }

  async function handleFiles(files) {
    if (!files || !files.length) return;
    const file = files[0];

    if (!file.type.startsWith('video/') && !['mp4','avi','mov','mkv','webm'].some(
      ext => file.name.toLowerCase().endsWith(ext)
    )) {
      showToast('Please select a video file', 'error');
      return;
    }

    await uploadFile(file);
  }

  async function uploadFile(file) {
    showToast('Uploading…');

    try {
      const result = await API.uploadVideo(file);
      currentVideoId  = result.video_id;
      currentFilename = result.filename;

      // Show video player immediately — playback is INDEPENDENT of AI
      showVideoPlayer(result);
      updateMetaBar(result.metadata);
      actionBar.style.display = 'flex';

      showToast('Video ready — click "Process with AI" to start detection', 'success');
    } catch (err) {
      showToast(`Upload failed: ${err.message}`, 'error');
      console.error('Upload error:', err);
    }
  }

  function showVideoPlayer(uploadResult) {
    uploadZone.style.display = 'none';
    videoContainer.style.display = 'block';
    metaBar.style.display = 'flex';

    // Set video source — playback starts immediately, no AI dependency
    videoEl.src = API.streamUrl(currentVideoId, currentFilename);
    videoEl.load();

    // Initialize overlay
    if (overlay) overlay.stop();
    overlay = new DetectionOverlay(videoEl, canvas);
    overlay.start();
  }

  function updateMetaBar(metadata) {
    if (!metadata) return;
    const { width, height, fps, duration_seconds, codec } = metadata;
    document.getElementById('meta-resolution').textContent = `${width}×${height}`;
    document.getElementById('meta-fps').textContent = fps != null ? `${fps.toFixed(1)} fps` : '—';
    document.getElementById('meta-duration').textContent  = duration_seconds != null
      ? formatDuration(duration_seconds) : '—';
    document.getElementById('meta-codec').textContent = codec || 'Unknown';
  }

  // ── Video Events ──
  function setupVideoEvents() {
    videoEl.addEventListener('timeupdate', () => {
      Dashboard.updateForTime(videoEl.currentTime);
    });

    videoEl.addEventListener('error', () => {
      showToast('Video playback error. The file may be corrupted.', 'error');
    });
  }

  // ── AI Processing ──
  function setupProcessButton() {
    processBtn.addEventListener('click', startProcessing);
  }

  async function startProcessing() {
    if (!currentVideoId) return;

    processBtn.disabled = true;
    processingBadge.style.display = 'flex';
    doneBadge.style.display = 'none';
    progressWrap.style.display = 'block';
    progressBar.style.width = '0%';
    progressLabel.textContent = 'Starting…';

    try {
      await API.processVideo(currentVideoId);
    } catch (err) {
      showToast(`Failed to start processing: ${err.message}`, 'error');
      processBtn.disabled = false;
      processingBadge.style.display = 'none';
      progressWrap.style.display = 'none';
      return;
    }

    // Stop previous poller
    if (poller) poller.stop();

    poller = new ProcessingPoller(
      currentVideoId,
      onProcessingProgress,
      onProcessingComplete,
      onProcessingError,
    );
    poller.start(1500);

    showToast('AI processing started — video plays independently');
  }

  function onProcessingProgress(status) {
    const done  = status.progress_frames || 0;
    const total = status.total_frames || 0;
    const pct   = total > 0 ? Math.round((done / total) * 100) : 0;

    progressBar.style.width = `${pct}%`;
    progressLabel.textContent = total > 0
      ? `${done.toLocaleString()} / ${total.toLocaleString()} frames (${pct}%)`
      : 'Processing…';
  }

  function onProcessingComplete(results) {
    // Update dashboard with real data
    Dashboard.setResults(results);

    // Feed frames to overlay
    if (overlay && results.frames) {
      overlay.setFrames(results.frames);
    }

    // UI updates
    processingBadge.style.display = 'none';
    doneBadge.style.display = 'flex';
    progressBar.style.width = '100%';
    progressLabel.textContent = `Complete — ${(results.frames || []).length.toLocaleString()} frames processed`;

    // Re-enable button for re-processing
    processBtn.disabled = false;
    processBtn.textContent = '↺ Re-process';

    showToast('AI processing complete!', 'success');
    console.log('Processing results:', results);
  }

  function onProcessingError(error) {
    processingBadge.style.display = 'none';
    progressWrap.style.display = 'none';
    processBtn.disabled = false;
    showToast(`AI processing failed: ${error}`, 'error');
    console.error('Processing error:', error);
  }

  // ── Toast ──
  function showToast(message, type = '') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast ${type} visible`;
    setTimeout(() => { toast.className = `toast ${type}`; }, 3500);
  }

  // ── Helpers ──
  function formatDuration(seconds) {
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}m ${s}s`;
  }

  // ── Start ──
  document.addEventListener('DOMContentLoaded', init);

})();
