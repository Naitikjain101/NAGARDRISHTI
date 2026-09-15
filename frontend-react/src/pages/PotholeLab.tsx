import React, { useState, useRef, useMemo, useEffect } from 'react';
import { ChevronRight, Download, Settings, BarChart2, Layers, Crosshair, Upload, Cpu } from 'lucide-react';
import { LabDetectionOverlay } from '../components/video/LabDetectionOverlay';
import { ModelRegistry } from '../components/video/ModelRegistry';

const ZERO_POTHOLE_VIDEO = "/Users/naitikjain/Documents/Nagar drishti mp4/16373790_3840_2160_30fps_compressed.mp4";
const POTHOLE_VIDEO = "/Users/naitikjain/Documents/Nagar drishti mp4/potholes.mp4";

export default function PotholeLab() {
  const [selectedVideo, setSelectedVideo] = useState<string>(POTHOLE_VIDEO);
  const [videoUrl, setVideoUrl] = useState<string>('');
  const [, setIsPlaying] = useState(false);
  const [confidenceThreshold, setConfidenceThreshold] = useState(0.40);
  const [useTracking, setUseTracking] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [activeTab, setActiveTab] = useState<'analysis' | 'registry'>('analysis');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [isLoading, setIsLoading] = useState(false);
  const [results, setResults] = useState<any>(null);

  // Model selector — fetched from registry, defaults to active pothole model
  const [potholeModels, setPotholeModels] = useState<Record<string, any>>({});
  const [selectedModelId, setSelectedModelId] = useState<string>(''); // '' = use active

  const videoRef = useRef<HTMLVideoElement>(null);

  // Load pothole model list from registry
  useEffect(() => {
    fetch('/api/ai/models/POTHOLE')
      .then(r => r.json())
      .then(data => {
        setPotholeModels(data);
        // Pre-select the active model
        const activeId = Object.entries(data).find(([, m]: any) => m.is_active)?.[0] ?? '';
        setSelectedModelId(activeId);
      })
      .catch(console.error);
  }, []);

  // Derive stats based on current confidence threshold
  const stats = useMemo(() => {
    if (!results) return null;
    
    let totalDetections = 0;
    let framesWithDetections = 0;
    let uniqueTracks = new Set();
    
    // Flat list of all valid detections for the table
    const allDetections: any[] = [];
    
    results.frames.forEach((frame: any) => {
      const validDetections = frame.pothole_detections.filter((d: any) => d.confidence >= confidenceThreshold);
      if (validDetections.length > 0) {
        framesWithDetections++;
        totalDetections += validDetections.length;
        
        validDetections.forEach((d: any, idx: number) => {
           const trackId = frame.active_pothole_event_ids?.[idx];
           if (trackId !== undefined) uniqueTracks.add(trackId);
           
           allDetections.push({
             frame: frame.frame_index,
             time: frame.timestamp,
             confidence: d.confidence,
             bbox: d.bbox,
             trackId: trackId
           });
        });
      }
    });

    return {
      totalFrames: results.metadata.frame_count,
      totalDetections,
      framesWithDetections,
      uniqueTracks: uniqueTracks.size,
      allDetections,
      fps: results.metadata.fps
    };
  }, [results, confidenceThreshold]);

  const handleAnalyze = async () => {
    setIsLoading(true);
    setResults(null);
    try {
      const jobId = `lab-${Date.now()}`;

      // Send model_id to backend — backend resolves to trusted registry path.
      // Empty string means "use active pothole model from registry".
      const res = await fetch('/api/pothole-lab/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          video_path: selectedVideo,
          model_id: selectedModelId || undefined,  // undefined → backend uses active
          confidence: 0.10, // Dense raw JSON; filtered on client by slider
          use_tracking: useTracking,
          job_id: jobId
        })
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(err.detail || 'Analysis failed');
      }

      const resultsRes = await fetch(`/api/pothole-lab/results/${jobId}`);
      const json = await resultsRes.json();
      setResults(json);

      const encodedPath = encodeURIComponent(selectedVideo);
      setVideoUrl(`/api/pothole-lab/stream?path=${encodedPath}`);

    } catch (e: any) {
      console.error(e);
      alert(`Failed to analyze video: ${e.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const seekToFrame = (frameIndex: number) => {
    if (!videoRef.current || !stats) return;
    videoRef.current.currentTime = frameIndex / stats.fps;
    videoRef.current.pause();
    setIsPlaying(false);
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      
      const res = await fetch('/api/pothole-lab/upload', {
        method: 'POST',
        body: formData
      });
      
      if (!res.ok) throw new Error('Upload failed');
      
      const data = await res.json();
      setSelectedVideo(data.video_path);
      setResults(null);
      setVideoUrl('');
      
    } catch (err) {
      console.error(err);
      alert('Failed to upload custom video');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="flex-1 bg-background text-foreground p-6">
      <div className="max-w-[1600px] mx-auto space-y-6">
        
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
              <Crosshair className="h-6 w-6 text-primary" />
              AI Model Lab
            </h1>
            <p className="text-muted-foreground mt-1">
              Pothole Analysis · Universal Model Registry · Benchmark
            </p>
          </div>
          
          <div className="flex flex-wrap items-center gap-2">
            <button 
              onClick={() => setSelectedVideo(ZERO_POTHOLE_VIDEO)}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${selectedVideo === ZERO_POTHOLE_VIDEO ? 'bg-primary text-primary-foreground' : 'bg-muted hover:bg-muted/80'}`}
            >
              Zero Pothole Test
            </button>
            <button 
              onClick={() => setSelectedVideo(POTHOLE_VIDEO)}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${selectedVideo === POTHOLE_VIDEO ? 'bg-primary text-primary-foreground' : 'bg-muted hover:bg-muted/80'}`}
            >
              Pothole Test
            </button>
            <div className="flex bg-muted p-1 rounded-lg">
              <button
                className={`px-4 py-2 text-sm font-medium rounded-md ${activeTab === 'analysis' ? 'bg-background shadow text-foreground' : 'text-muted-foreground'}`}
                onClick={() => setActiveTab('analysis')}
              >
                Analysis Lab
              </button>
              <button
                className={`px-4 py-2 text-sm font-medium rounded-md ${activeTab === 'registry' ? 'bg-background shadow text-foreground' : 'text-muted-foreground'}`}
                onClick={() => setActiveTab('registry')}
              >
                Model Registry
              </button>
            </div>

            {activeTab === 'analysis' && (
              <>
                <button 
                  onClick={() => setSelectedVideo(ZERO_POTHOLE_VIDEO)}
                  className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${selectedVideo === ZERO_POTHOLE_VIDEO ? 'bg-primary text-primary-foreground' : 'bg-muted hover:bg-muted/80'}`}
                >
                  Zero Pothole Test
                </button>
                <button 
                  onClick={() => setSelectedVideo(POTHOLE_VIDEO)}
                  className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${selectedVideo === POTHOLE_VIDEO ? 'bg-primary text-primary-foreground' : 'bg-muted hover:bg-muted/80'}`}
                >
                  Real Pothole Test
                </button>
                
                <input 
                  type="file" 
                  accept="video/mp4,video/x-m4v,video/*" 
                  className="hidden" 
                  ref={fileInputRef}
                  onChange={handleFileUpload}
                />
                <button 
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isUploading}
                  className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${selectedVideo !== ZERO_POTHOLE_VIDEO && selectedVideo !== POTHOLE_VIDEO ? 'bg-primary text-primary-foreground' : 'bg-muted hover:bg-muted/80'}`}
                >
                  <Upload className="h-4 w-4" />
                  {isUploading ? 'Uploading...' : 'Custom Video'}
                </button>

                {/* Model selector — populated from central registry */}
                {Object.keys(potholeModels).length > 0 && (
                  <div className="flex items-center gap-2 ml-2">
                    <Cpu className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                    <select
                      value={selectedModelId}
                      onChange={e => setSelectedModelId(e.target.value)}
                      className="text-sm bg-muted border rounded-md px-2 py-1.5 text-foreground cursor-pointer focus:outline-none focus:ring-1 focus:ring-primary"
                      title="Select pothole model for this lab run"
                    >
                      {Object.entries(potholeModels).map(([id, m]: any) => (
                        <option key={id} value={id} disabled={!m.file_exists}>
                          {m.display_name}{m.is_active ? ' ✓' : ''}{!m.file_exists ? ' (unavailable)' : ''}
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                <button
                  onClick={handleAnalyze}
                  disabled={isLoading || isUploading}
                  className="ml-4 px-6 py-2 bg-blue-600 text-white rounded-md text-sm font-bold shadow-sm hover:bg-blue-700 disabled:opacity-50"
                >
                  {isLoading ? 'Processing...' : 'Run Analysis'}
                </button>
              </>
            )}
          </div>
        </div>

        {activeTab === 'registry' ? (
          <ModelRegistry />
        ) : (
          results && stats && (
            <>
            {/* Acceptance Visualizer */}
            <div className="bg-card border rounded-lg p-6 flex items-center justify-between shadow-sm">
              <div>
                <h3 className="text-lg font-semibold mb-1">Evaluation Results</h3>
                <div className="text-sm text-muted-foreground flex items-center gap-4">
                  <span>Ground Truth: <strong className="text-foreground">{selectedVideo === ZERO_POTHOLE_VIDEO ? '0 Potholes' : 'Potholes Present'}</strong></span>
                  <span>Model Raw Detections: <strong className="text-foreground">{stats.totalDetections} at conf {confidenceThreshold.toFixed(2)}</strong></span>
                </div>
              </div>
              
              {selectedVideo === ZERO_POTHOLE_VIDEO ? (
                 stats.totalDetections === 0 ? (
                   <div className="px-4 py-2 bg-green-500/10 text-green-600 font-bold rounded-md border border-green-500/20">STATUS: PASS</div>
                 ) : (
                   <div className="px-4 py-2 bg-red-500/10 text-red-600 font-bold rounded-md border border-red-500/20">STATUS: FAIL — FALSE POSITIVE</div>
                 )
              ) : (
                 <div className="px-4 py-2 bg-blue-500/10 text-blue-600 font-bold rounded-md border border-blue-500/20">STATUS: EVALUATION MODE</div>
              )}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              
              {/* Left Column: Video & Timeline */}
              <div className="lg:col-span-2 space-y-4">
                <div className="relative bg-black rounded-lg overflow-hidden border aspect-video shadow-sm">
                  {videoUrl ? (
                    <>
                      <video
                        ref={videoRef}
                        src={videoUrl}
                        className="w-full h-full object-contain"
                        controls
                        onPlay={() => setIsPlaying(true)}
                        onPause={() => setIsPlaying(false)}
                      />
                      <LabDetectionOverlay 
                        videoRef={videoRef as any}
                        frames={results.frames}
                        confidenceThreshold={confidenceThreshold}
                      />
                    </>
                  ) : (
                    <div className="absolute inset-0 flex items-center justify-center text-muted-foreground">
                      Video Ready
                    </div>
                  )}
                </div>

                {/* Timeline */}
                <div className="bg-card border rounded-lg p-4">
                  <div className="flex justify-between text-xs text-muted-foreground mb-2">
                    <span>Frame 0</span>
                    <span>Frame {stats.totalFrames}</span>
                  </div>
                  <div className="h-8 bg-muted rounded-md relative cursor-pointer overflow-hidden flex"
                       onClick={(e) => {
                         const rect = e.currentTarget.getBoundingClientRect();
                         const ratio = (e.clientX - rect.left) / rect.width;
                         seekToFrame(Math.floor(ratio * stats.totalFrames));
                       }}>
                    {results.frames.map((f: any, i: number) => {
                      const valid = f.pothole_detections.filter((d: any) => d.confidence >= confidenceThreshold).length > 0;
                      return (
                        <div 
                          key={i} 
                          className={`flex-1 h-full ${valid ? 'bg-orange-500' : 'opacity-0'}`} 
                        />
                      );
                    })}
                  </div>
                </div>

                {/* Pipeline */}
                <div className="bg-card border rounded-lg p-4 overflow-x-auto">
                  <h3 className="text-sm font-semibold mb-4 text-muted-foreground">DEBUG PIPELINE VISUALIZATION</h3>
                  <div className="flex items-center gap-2 min-w-max text-sm">
                    <div className="px-3 py-2 bg-muted rounded text-center">VIDEO<br/><span className="font-bold">{stats.totalFrames} frames</span></div>
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    <div className="px-3 py-2 bg-blue-500/10 text-blue-600 rounded text-center border border-blue-500/20">YOLO26m<br/><span className="font-bold">best.pt</span></div>
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    <div className="px-3 py-2 bg-orange-500/10 text-orange-600 rounded text-center border border-orange-500/20">RAW DETECTIONS<br/><span className="font-bold">{stats.totalDetections}</span></div>
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    <div className="px-3 py-2 bg-purple-500/10 text-purple-600 rounded text-center border border-purple-500/20">BYTE TRACK<br/><span className="font-bold">{stats.uniqueTracks} tracks</span></div>
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    <div className="px-3 py-2 bg-red-500/10 text-red-600 rounded text-center border border-red-500/20 opacity-50">TEMPORAL VALIDATOR<br/><span className="text-xs">NOT IMPLEMENTED (LAB)</span></div>
                  </div>
                </div>
              </div>

              {/* Right Column: Controls & Stats */}
              <div className="space-y-6">
                
                {/* Diagnostics */}
                <div className="bg-card border rounded-lg p-5 shadow-sm space-y-6">
                  <div>
                    <h3 className="text-sm font-semibold flex items-center gap-2 mb-4">
                      <Settings className="h-4 w-4" /> Diagnostic Controls
                    </h3>
                    
                    <div className="space-y-4">
                      <div>
                        <div className="flex justify-between text-sm mb-2">
                          <span className="text-muted-foreground">Confidence Threshold</span>
                          <span className="font-mono font-bold text-primary">{confidenceThreshold.toFixed(2)}</span>
                        </div>
                        <input 
                          type="range" 
                          min="0.10" max="0.90" step="0.05"
                          value={confidenceThreshold}
                          onChange={(e) => setConfidenceThreshold(parseFloat(e.target.value))}
                          className="w-full accent-primary"
                        />
                      </div>
                      
                      <div>
                        <div className="flex justify-between text-sm mb-2">
                          <span className="text-muted-foreground">Execution Mode</span>
                        </div>
                        <div className="flex bg-muted p-1 rounded-md">
                          <button 
                            className={`flex-1 py-1.5 text-xs font-medium rounded ${!useTracking ? 'bg-background shadow-sm' : 'text-muted-foreground'}`}
                            onClick={() => setUseTracking(false)}
                          >
                            RAW DETECTION
                          </button>
                          <button 
                            className={`flex-1 py-1.5 text-xs font-medium rounded ${useTracking ? 'bg-background shadow-sm' : 'text-muted-foreground'}`}
                            onClick={() => setUseTracking(true)}
                          >
                            TRACKING
                          </button>
                        </div>
                        <p className="text-xs text-muted-foreground mt-2">
                          * Changing execution mode requires re-running analysis.
                        </p>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Statistics Panel */}
                <div className="bg-card border rounded-lg p-5 shadow-sm">
                  <h3 className="text-sm font-semibold flex items-center gap-2 mb-4">
                    <BarChart2 className="h-4 w-4" /> Live Debug Statistics
                  </h3>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div className="p-3 bg-muted/50 rounded-md">
                      <div className="text-xs text-muted-foreground mb-1">Frames Processed</div>
                      <div className="text-xl font-bold">{stats.totalFrames}</div>
                    </div>
                    <div className="p-3 bg-muted/50 rounded-md">
                      <div className="text-xs text-muted-foreground mb-1">Raw Detections</div>
                      <div className="text-xl font-bold text-orange-500">{stats.totalDetections}</div>
                    </div>
                    <div className="p-3 bg-muted/50 rounded-md">
                      <div className="text-xs text-muted-foreground mb-1">Frames with Dets</div>
                      <div className="text-xl font-bold">{stats.framesWithDetections}</div>
                    </div>
                    <div className="p-3 bg-muted/50 rounded-md">
                      <div className="text-xs text-muted-foreground mb-1">Unique Tracks</div>
                      <div className="text-xl font-bold text-purple-500">{stats.uniqueTracks}</div>
                    </div>
                  </div>
                </div>

                {/* Track Summary */}
                {useTracking && results.tracks && results.tracks.length > 0 && (
                  <div className="bg-card border rounded-lg p-5 shadow-sm max-h-[300px] overflow-y-auto">
                    <h3 className="text-sm font-semibold flex items-center gap-2 mb-4">
                      <Layers className="h-4 w-4" /> Track Summary
                    </h3>
                    <div className="space-y-3">
                      {results.tracks.map((t: any) => (
                        <div key={t.event_id} className="text-xs border-b pb-2 last:border-0 last:pb-0">
                          <div className="font-bold text-foreground mb-1">Track #{t.event_id}</div>
                          <div className="grid grid-cols-2 gap-1 text-muted-foreground">
                            <div>Frames observed: {t.total_detections}</div>
                            <div>Max confidence: {(t.max_confidence * 100).toFixed(0)}%</div>
                            <div>First frame: {t.first_frame}</div>
                            <div>Last frame: {t.last_frame}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Detection Table */}
            <div className="bg-card border rounded-lg shadow-sm overflow-hidden">
              <div className="p-4 border-b flex justify-between items-center bg-muted/30">
                <h3 className="text-sm font-semibold">Detection Log ({stats.allDetections.length})</h3>
                <button className="text-xs flex items-center gap-1 text-muted-foreground hover:text-foreground">
                  <Download className="h-3 w-3" /> Export JSON
                </button>
              </div>
              <div className="overflow-x-auto max-h-[400px]">
                <table className="w-full text-sm text-left">
                  <thead className="text-xs text-muted-foreground bg-muted/50 sticky top-0">
                    <tr>
                      <th className="px-4 py-3 font-medium">Frame</th>
                      <th className="px-4 py-3 font-medium">Time (s)</th>
                      <th className="px-4 py-3 font-medium">Confidence</th>
                      <th className="px-4 py-3 font-medium">X1</th>
                      <th className="px-4 py-3 font-medium">Y1</th>
                      <th className="px-4 py-3 font-medium">X2</th>
                      <th className="px-4 py-3 font-medium">Y2</th>
                      <th className="px-4 py-3 font-medium">Track ID</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {stats.allDetections.map((d, idx) => (
                      <tr 
                        key={idx} 
                        className="hover:bg-muted/50 cursor-pointer transition-colors"
                        onClick={() => seekToFrame(d.frame)}
                      >
                        <td className="px-4 py-2">{d.frame}</td>
                        <td className="px-4 py-2">{d.time.toFixed(2)}</td>
                        <td className="px-4 py-2 font-mono">{(d.confidence * 100).toFixed(1)}%</td>
                        <td className="px-4 py-2 text-muted-foreground">{d.bbox[0].toFixed(0)}</td>
                        <td className="px-4 py-2 text-muted-foreground">{d.bbox[1].toFixed(0)}</td>
                        <td className="px-4 py-2 text-muted-foreground">{d.bbox[2].toFixed(0)}</td>
                        <td className="px-4 py-2 text-muted-foreground">{d.bbox[3].toFixed(0)}</td>
                        <td className="px-4 py-2">
                          {d.trackId !== undefined ? (
                            <span className="px-2 py-0.5 bg-purple-500/10 text-purple-600 rounded text-xs font-medium">
                              #{d.trackId}
                            </span>
                          ) : '-'}
                        </td>
                      </tr>
                    ))}
                    {stats.allDetections.length === 0 && (
                      <tr>
                        <td colSpan={8} className="px-4 py-8 text-center text-muted-foreground">
                          No detections at confidence {confidenceThreshold.toFixed(2)}
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
            </>
          )
        )}
      </div>
    </div>
  );
}
