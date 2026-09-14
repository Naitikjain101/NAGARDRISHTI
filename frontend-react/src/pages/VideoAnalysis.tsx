import { useState, useRef, useEffect } from 'react';
import { Upload, RefreshCw, AlertTriangle, RotateCcw, Cpu, FileVideo, Activity } from 'lucide-react';
import { VideoPlayer } from '@/components/video/VideoPlayer';
import { videoApi, type JobStatus, type ProcessingStartResponse, type ProcessingStatusResponse, type VideoUploadResponse } from '@/api/video';
import { useMutation, useQuery } from '@tanstack/react-query';
import { AddJourneyModal } from '@/components/fleet/AddJourneyModal';


// Session storage keys for refresh recovery
const STORAGE_KEY_VIDEO_ID = 'uw_active_video_id';
const STORAGE_KEY_JOB_ID   = 'uw_active_job_id';

/** Terminal statuses — polling must stop on these */
const TERMINAL_STATUSES: JobStatus[] = ['completed', 'failed', 'cancelled'];

export function VideoAnalysis() {
  const [selectedFile, setSelectedFile]       = useState<File | null>(null);
  const [videoId, setVideoId]                 = useState<string | null>(() => sessionStorage.getItem(STORAGE_KEY_VIDEO_ID));
  const [jobId, setJobId]                     = useState<string | null>(() => sessionStorage.getItem(STORAGE_KEY_JOB_ID));
  const [isProcessing, setIsProcessing]       = useState(false);
  const [processingComplete, setProcessingComplete] = useState(false);
  const [processingError, setProcessingError] = useState<string | null>(null);
  const [pollError, setPollError]             = useState<string | null>(null);
  const [isAddModalOpen, setIsAddModalOpen]   = useState(false);
  const fileInputRef                          = useRef<HTMLInputElement>(null);

  // On mount: if we have a videoId in session, check whether the job is already done/running
  useEffect(() => {
    if (videoId && jobId) {
      videoApi.getProcessingStatus(videoId).then((res) => {
        if (!TERMINAL_STATUSES.includes(res.status)) {
          setIsProcessing(true);
        } else {
          setProcessingComplete(res.status === 'completed');
          if (res.status === 'failed' || res.status === 'cancelled') {
            setProcessingError(res.error ?? 'Processing failed');
          }
        }
      }).catch(console.error);
    }
  }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  // Persist IDs to session storage whenever they change
  useEffect(() => {
    if (videoId) sessionStorage.setItem(STORAGE_KEY_VIDEO_ID, videoId);
    else sessionStorage.removeItem(STORAGE_KEY_VIDEO_ID);
  }, [videoId]);

  useEffect(() => {
    if (jobId) sessionStorage.setItem(STORAGE_KEY_JOB_ID, jobId);
    else sessionStorage.removeItem(STORAGE_KEY_JOB_ID);
  }, [jobId]);

  // ── Upload mutation ──────────────────────────────────────────────────────
  const uploadMutation = useMutation({
    mutationFn: videoApi.uploadVideo,
    onSuccess: (data: VideoUploadResponse) => {
      setVideoId(data.video_id);
    },
    onError: (err: Error) => {
      setProcessingError(`Upload failed: ${err.message}`);
    },
  });

  // ── Process trigger mutation ─────────────────────────────────────────────
  const processMutation = useMutation({
    mutationFn: videoApi.startUnifiedProcessing,
    onSuccess: (data: ProcessingStartResponse) => {
      setJobId(data.job_id);
      setIsProcessing(true);
      setProcessingError(null);
      setPollError(null);
    },
    onError: (err: Error) => {
      setProcessingError(`Failed to start processing: ${err.message}`);
    },
  });

  // ── Status polling ───────────────────────────────────────────────────────
  // Poll by video_id. Stops immediately on terminal status.
  const { data: statusData } = useQuery({
    queryKey: ['videoStatus', videoId],
    queryFn: async (): Promise<ProcessingStatusResponse> => {
      setPollError(null);
      return videoApi.getProcessingStatus(videoId!);
    },
    enabled: !!videoId && isProcessing,
    refetchInterval: (query) => {
      const status = query.state.data?.status as JobStatus | undefined;
      if (!status) return 1500;
      if (TERMINAL_STATUSES.includes(status)) {
        return false;
      }
      return 1500;
    },
    retry: 3,
    retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 8000),
    throwOnError: false,
  });



  // Handle terminal status transition in useEffect to avoid React Query state mutation issues
  useEffect(() => {
    if (statusData?.status) {
      if (statusData.status === 'completed') {
        setIsProcessing(false);
        setProcessingComplete(true);
      } else if (statusData.status === 'failed' || statusData.status === 'cancelled') {
        setIsProcessing(false);
        setProcessingError(statusData.error ?? 'Processing failed with no error message');
      }
    }
  }, [statusData?.status, statusData?.error]);

  // ── Results fetch ────────────────────────────────────────────────────────
  const { data: resultsData } = useQuery({
    queryKey: ['videoResults', videoId],
    queryFn: () => videoApi.getResults(videoId!),
    enabled: !!videoId && processingComplete,
    retry: 2,
  });

  // ── Event handlers ───────────────────────────────────────────────────────
  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      setProcessingError(null);
      uploadMutation.mutate(file);
    }
  };

  const startProcessing = () => {
    if (videoId) {
      setProcessingError(null);
      processMutation.mutate(videoId);
    }
  };

  const resetAll = () => {
    setVideoId(null);
    setJobId(null);
    setSelectedFile(null);
    setIsProcessing(false);
    setProcessingComplete(false);
    setProcessingError(null);
    setPollError(null);
  };

  // ── Progress calculation ─────────────────────────────────────────────────
  const progressPercent = statusData?.total_frames
    ? Math.min(100, Math.round(((statusData.progress_frames || 0) / statusData.total_frames) * 100))
    : 0;

  const displayStatus: JobStatus | 'idle' | 'uploading' = (
    uploadMutation.isPending ? 'uploading' :
    !videoId ? 'idle' :
    isProcessing ? (statusData?.status ?? 'queued') :
    processingComplete ? 'completed' :
    processingError ? 'failed' :
    'idle'
  );

  // Video stream URL — routes through Vite proxy, never hardcoded
  const videoStreamUrl = videoId ? videoApi.getStreamUrl(videoId) : null;

  const confirmedPotholes = resultsData?.pothole_events?.filter((e: any) => e.status === 'confirmed' || e.status === 'CONFIRMED')?.length ?? 0;
  const confirmedWaterlogging = resultsData?.waterlogging_events?.filter((e: any) => e.status === 'confirmed' || e.status === 'CONFIRMED')?.length ?? 0;

  return (
    <div className="flex flex-col h-full space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold">Video AI Pipeline</h1>
          <p className="text-muted-foreground">Upload drone or CCTV footage for automated forensic analysis.</p>
        </div>
        {(videoId || selectedFile) && (
          <button
            onClick={resetAll}
            className="flex items-center gap-2 px-3 py-1.5 bg-secondary text-secondary-foreground rounded-md text-sm hover:bg-secondary/80 transition-colors"
          >
            <RefreshCw className="h-4 w-4" /> Start Over
          </button>
        )}
      </div>

      {/* Upload Drop Zone */}
      {!videoId && !selectedFile && (
        <div
          className="flex-1 border-2 border-dashed border-border rounded-lg flex flex-col items-center justify-center bg-card hover:bg-secondary/20 transition-colors cursor-pointer group"
          onClick={() => fileInputRef.current?.click()}
        >
          <div className="p-4 rounded-full bg-secondary text-primary group-hover:scale-110 transition-transform mb-4">
            <Upload className="h-8 w-8" />
          </div>
          <h3 className="text-xl font-bold mb-2">Upload Video Evidence</h3>
          <p className="text-muted-foreground text-sm max-w-sm text-center">
            Drag and drop your MP4/AVI/MOV file here, or click to browse. Max size: 500MB.
          </p>
          <input
            type="file"
            ref={fileInputRef}
            className="hidden"
            accept="video/mp4,video/avi,video/quicktime,video/x-msvideo,video/webm"
            onChange={handleFileChange}
          />
        </div>
      )}

      {/* Uploading spinner */}
      {selectedFile && uploadMutation.isPending && (
        <div className="flex-1 border border-border rounded-lg flex flex-col items-center justify-center bg-card gap-4">
          <div className="w-12 h-12 rounded-full border-4 border-primary border-t-transparent animate-spin" />
          <h3 className="text-lg font-bold">Uploading to Server...</h3>
          <p className="text-muted-foreground">{selectedFile.name}</p>
        </div>
      )}

      {/* Upload error (no video yet) */}
      {!videoId && processingError && (
        <div className="flex-1 border border-destructive/50 rounded-lg flex flex-col items-center justify-center bg-card gap-4">
          <AlertTriangle className="h-12 w-12 text-destructive" />
          <h3 className="text-lg font-bold text-destructive">Upload Failed</h3>
          <p className="text-muted-foreground text-sm text-center max-w-sm">{processingError}</p>
          <button
            onClick={() => { setProcessingError(null); setSelectedFile(null); }}
            className="flex items-center gap-2 px-4 py-2 bg-secondary rounded-md text-sm"
          >
            <RotateCcw className="h-4 w-4" /> Try Again
          </button>
        </div>
      )}

      {/* Main content — video + controls */}
      {videoId && (
        <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Video Player */}
          <div className="lg:col-span-2 flex flex-col gap-4 relative">
            <div className="flex-1 rounded-lg border border-border overflow-hidden bg-black relative">
              {videoStreamUrl && (
                <VideoPlayer
                  src={videoStreamUrl}
                  results={resultsData || null}
                />
              )}
            </div>

            {/* Progress overlay — only while processing */}
            {isProcessing && (
              <div className="absolute inset-x-0 bottom-4 mx-4 bg-card/95 backdrop-blur border border-border rounded-lg p-4 shadow-2xl z-20">
                <div className="flex justify-between items-end mb-2">
                  <div>
                    <h4 className="font-bold flex items-center gap-2">
                      <Cpu className="h-4 w-4 text-primary animate-pulse" /> 
                      {progressPercent === 100 ? 'Finalizing AI Results...' : 'AI Processing Running'}
                    </h4>
                    <p className="text-xs text-muted-foreground">
                      Status: <span className="font-mono">{progressPercent === 100 ? 'finalizing' : (statusData?.status ?? 'queued')}</span>
                      {statusData?.processing_fps && progressPercent < 100 ? ` · ${statusData.processing_fps.toFixed(1)} fps` : ''}
                    </p>
                    {/* Transient poll error */}
                    {pollError && (
                      <p className="text-xs text-amber-500 mt-1">{pollError}</p>
                    )}
                  </div>
                  <div className="text-right">
                    <span className="text-xs font-mono">
                      {statusData?.progress_frames ?? 0} / {statusData?.total_frames ?? '?'} frames
                    </span>
                    <p className="text-2xl font-bold text-primary">{progressPercent}%</p>
                  </div>
                </div>
                <div className="w-full h-2 bg-secondary rounded-full overflow-hidden">
                  <div
                    className="h-full bg-primary transition-all duration-300"
                    style={{ width: `${progressPercent}%` }}
                  />
                </div>
              </div>
            )}
          </div>

          {/* Right sidebar */}
          <div className="flex flex-col gap-4">
            {/* Video Metadata */}
            <div className="bg-card border border-border rounded-lg p-6">
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <FileVideo className="h-5 w-5" /> Job Info
              </h3>
              <div className="space-y-3 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Video ID</span>
                  <span className="font-mono text-xs bg-secondary px-1.5 rounded">{videoId.slice(0, 8)}…</span>
                </div>
                {jobId && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Job ID</span>
                    <span className="font-mono text-xs bg-secondary px-1.5 rounded">{jobId.slice(0, 8)}…</span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Status</span>
                  <span className={`font-mono text-xs px-2 py-0.5 rounded ${
                    displayStatus === 'completed' ? 'bg-emerald-500/20 text-emerald-400' :
                    displayStatus === 'failed' ? 'bg-red-500/20 text-red-400' :
                    displayStatus === 'running' ? 'bg-blue-500/20 text-blue-400' :
                    'bg-secondary text-muted-foreground'
                  }`}>
                    {displayStatus}
                  </span>
                </div>
                {statusData?.total_frames ? (
                  <>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Total Frames</span>
                      <span className="font-mono text-xs">{statusData.total_frames.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Processed</span>
                      <span className="font-mono text-xs">{(statusData.progress_frames ?? 0).toLocaleString()}</span>
                    </div>
                  </>
                ) : null}
              </div>

              {/* Start AI button */}
              {!isProcessing && !processingComplete && !processingError && (
                <button
                  id="start-ai-analysis-btn"
                  onClick={startProcessing}
                  disabled={processMutation.isPending}
                  className="w-full mt-6 flex items-center justify-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
                >
                  <Cpu className="h-4 w-4" />
                  {processMutation.isPending ? 'Starting…' : 'Start AI Analysis'}
                </button>
              )}
            </div>

            {/* Processing Error card */}
            {processingError && !isProcessing && (
              <div className="bg-card border border-destructive/50 rounded-lg p-4">
                <h3 className="font-semibold text-destructive flex items-center gap-2 mb-2">
                  <AlertTriangle className="h-4 w-4" /> Processing Failed
                </h3>
                <p className="text-xs text-muted-foreground break-words">{processingError}</p>
                <button
                  onClick={() => { setProcessingError(null); setIsProcessing(false); }}
                  className="mt-3 text-xs underline text-muted-foreground hover:text-foreground"
                >
                  Retry
                </button>
              </div>
            )}

            {/* Results card — only after completion */}
            {processingComplete && (
              <div className="bg-card border border-border rounded-lg flex flex-col flex-1 overflow-hidden">
                <div className="p-4 border-b border-border bg-emerald-500/10">
                  <h3 className="font-semibold text-emerald-500 flex items-center gap-2">
                    <Activity className="h-5 w-5" /> Analysis Complete
                  </h3>
                </div>
                <div className="p-4 flex-1 space-y-4">
                  <div className="grid grid-cols-2 gap-2">
                    <div className="bg-secondary/50 p-3 rounded-md border border-border text-center">
                      <p className="text-xs text-muted-foreground">Total Events</p>
                      <p className="text-xl font-bold">
                        {confirmedPotholes + confirmedWaterlogging}
                      </p>
                    </div>
                    <div className="bg-secondary/50 p-3 rounded-md border border-border text-center">
                      <p className="text-xs text-muted-foreground">Inference FPS</p>
                      <p className="text-xl font-bold">
                        {resultsData?.timing?.total_frame?.fps_mean?.toFixed?.(1) ?? statusData?.processing_fps?.toFixed(1) ?? '—'}
                      </p>
                    </div>
                    <div className="bg-secondary/50 p-3 rounded-md border border-border text-center">
                      <p className="text-xs text-muted-foreground">Potholes</p>
                      <p className="text-xl font-bold text-orange-500">{confirmedPotholes}</p>
                    </div>
                    <div className="bg-secondary/50 p-3 rounded-md border border-border text-center">
                      <p className="text-xs text-muted-foreground">Waterlogging</p>
                      <p className="text-xl font-bold text-blue-500">{confirmedWaterlogging}</p>
                    </div>
                  </div>

                  <button
                    onClick={() => setIsAddModalOpen(true)}
                    className="w-full mt-4 flex items-center justify-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md font-medium hover:bg-primary/90 transition-colors"
                  >
                    ADD TO LIVE MONITORING
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Reusable Journey Modal */}
      {videoId && (
        <AddJourneyModal 
          isOpen={isAddModalOpen} 
          onClose={() => setIsAddModalOpen(false)}
          preUploadedVideoId={videoId}
          preUploadedFilename={selectedFile?.name || statusData?.video_id || 'video'}
          preProcessedDuration={statusData?.total_frames && statusData?.processing_fps ? (statusData.total_frames / statusData.processing_fps) : 0}
        />
      )}
    </div>
  );
}
