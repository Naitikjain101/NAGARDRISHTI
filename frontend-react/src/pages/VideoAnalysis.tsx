import { useState, useRef, useEffect } from 'react';
import { Upload, RefreshCw, AlertTriangle, RotateCcw, Cpu, FileVideo, CheckCircle2, Play } from 'lucide-react';
import { VideoPlayer } from '@/components/video/VideoPlayer';
import { videoApi, type JobStatus, type ProcessingStartResponse, type ProcessingStatusResponse, type VideoUploadResponse } from '@/api/video';
import { useMutation, useQuery } from '@tanstack/react-query';
import { AddJourneyModal } from '@/components/fleet/AddJourneyModal';
import { PageHeader } from '@/components/ui/PageHeader';
import { Button } from '@/components/ui/Button';
import { TrafficDensityPanel } from '@/components/video/TrafficDensityPanel';
import { DetectionSummary } from '@/components/video/DetectionSummary';

// Session storage keys for refresh recovery
const STORAGE_KEY_VIDEO_ID = 'uw_active_video_id';
const STORAGE_KEY_JOB_ID   = 'uw_active_job_id';

const TERMINAL_STATUSES: JobStatus[] = ['completed', 'failed', 'cancelled'];

export function VideoAnalysis() {
  const [selectedFile, setSelectedFile]       = useState<File | null>(null);
  const [videoId, setVideoId]                 = useState<string | null>(() => sessionStorage.getItem(STORAGE_KEY_VIDEO_ID));
  const [jobId, setJobId]                     = useState<string | null>(() => sessionStorage.getItem(STORAGE_KEY_JOB_ID));
  
  const [isProcessing, setIsProcessing]       = useState(false);
  const [processingComplete, setProcessingComplete] = useState(false);
  const [processingError, setProcessingError] = useState<string | null>(null);
  
  const [isAddModalOpen, setIsAddModalOpen]   = useState(false);
  const fileInputRef                          = useRef<HTMLInputElement>(null);

  // Cross-component state
  const [currentVideoTime, setCurrentVideoTime] = useState(0);
  const [seekTime, setSeekTime] = useState<number | null>(null);

  // On mount check if running
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
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Persist IDs
  useEffect(() => {
    if (videoId) sessionStorage.setItem(STORAGE_KEY_VIDEO_ID, videoId);
    else sessionStorage.removeItem(STORAGE_KEY_VIDEO_ID);
  }, [videoId]);

  useEffect(() => {
    if (jobId) sessionStorage.setItem(STORAGE_KEY_JOB_ID, jobId);
    else sessionStorage.removeItem(STORAGE_KEY_JOB_ID);
  }, [jobId]);

  // Mutations
  const uploadMutation = useMutation({
    mutationFn: videoApi.uploadVideo,
    onSuccess: (data: VideoUploadResponse) => setVideoId(data.video_id),
    onError: (err: Error) => setProcessingError(`Upload failed: ${err.message}`),
  });

  const processMutation = useMutation({
    mutationFn: videoApi.startUnifiedProcessing,
    onSuccess: (data: ProcessingStartResponse) => {
      setJobId(data.job_id);
      setIsProcessing(true);
      setProcessingError(null);
    },
    onError: (err: Error) => setProcessingError(`Failed to start processing: ${err.message}`),
  });

  // Polling
  const { data: statusData } = useQuery({
    queryKey: ['videoStatus', videoId],
    queryFn: async (): Promise<ProcessingStatusResponse> => {
      return videoApi.getProcessingStatus(videoId!);
    },
    enabled: !!videoId && isProcessing,
    refetchInterval: (query) => {
      const status = query.state.data?.status as JobStatus | undefined;
      if (!status) return 1500;
      if (TERMINAL_STATUSES.includes(status)) return false;
      return 1500;
    },
    retry: 3,
    retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 8000),
    throwOnError: false,
  });

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

  const { data: resultsData } = useQuery({
    queryKey: ['videoResults', videoId],
    queryFn: () => videoApi.getResults(videoId!),
    enabled: !!videoId && processingComplete,
    retry: 2,
  });

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
    setCurrentVideoTime(0);
    setSeekTime(null);
  };

  const handleSeek = (time: number) => {
    setSeekTime(time);
    // Clear seek time shortly after so it can be re-triggered
    setTimeout(() => setSeekTime(null), 100);
  };

  const progressPercent = statusData?.total_frames
    ? Math.min(100, Math.round(((statusData.progress_frames || 0) / statusData.total_frames) * 100))
    : 0;

  const videoStreamUrl = videoId ? videoApi.getStreamUrl(videoId) : null;

  return (
    <div className="page-content pb-8 h-full flex flex-col">
      <PageHeader
        title="Video Analysis"
        icon={FileVideo}
        description="Upload survey footage to analyze infrastructure and traffic density using AI."
        actions={
          (videoId || selectedFile) && (
            <Button variant="outline" icon={RefreshCw} onClick={resetAll}>
              Start Over
            </Button>
          )
        }
      />

      <div className="flex-1 overflow-y-auto">
        {/* Upload State */}
        {!videoId && !selectedFile && (
          <div
            className="w-full max-w-4xl mx-auto mt-8 border-2 border-dashed border-border rounded-xl p-12 flex flex-col items-center justify-center bg-card hover:bg-secondary/20 transition-colors cursor-pointer group shadow-sm"
            onClick={() => fileInputRef.current?.click()}
          >
            <div className="p-4 rounded-full bg-secondary text-primary group-hover:scale-110 transition-transform mb-6">
              <Upload className="h-10 w-10" />
            </div>
            <h3 className="text-2xl font-bold mb-3">Upload Video Evidence</h3>
            <p className="text-muted-foreground text-center max-w-md">
              Drag and drop your MP4, AVI, or MOV file here, or click to browse. Ensure the video is clear for accurate AI detection.
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

        {/* Uploading State */}
        {selectedFile && uploadMutation.isPending && (
          <div className="w-full max-w-4xl mx-auto mt-8 border border-border rounded-xl p-12 flex flex-col items-center justify-center bg-card shadow-sm gap-6">
            <div className="w-16 h-16 rounded-full border-4 border-primary border-t-transparent animate-spin" />
            <div className="text-center">
              <h3 className="text-xl font-bold mb-1">Uploading to Platform...</h3>
              <p className="text-muted-foreground font-mono text-sm">{selectedFile.name}</p>
            </div>
          </div>
        )}

        {/* Upload Error */}
        {!videoId && processingError && (
          <div className="w-full max-w-4xl mx-auto mt-8 border border-destructive/50 rounded-xl p-12 flex flex-col items-center justify-center bg-destructive/5 shadow-sm gap-4 text-center">
            <div className="p-4 rounded-full bg-destructive/10 text-destructive mb-2">
              <AlertTriangle className="h-10 w-10" />
            </div>
            <h3 className="text-xl font-bold text-destructive">Upload Failed</h3>
            <p className="text-muted-foreground max-w-md">{processingError}</p>
            <Button variant="outline" icon={RotateCcw} onClick={() => { setProcessingError(null); setSelectedFile(null); }} className="mt-4">
              Try Again
            </Button>
          </div>
        )}

        {/* Ready to process / Processing / Completed Workspace */}
        {videoId && (
          <div className="grid grid-cols-1 xl:grid-cols-12 gap-6 h-full min-h-[600px]">
            {/* Left Column - Video & Metadata */}
            <div className="xl:col-span-8 flex flex-col gap-6">
              
              {/* Video Player Area */}
              <div className="relative bg-black rounded-lg border border-border overflow-hidden shadow-sm flex-shrink-0">
                {videoStreamUrl && (
                  <VideoPlayer
                    src={videoStreamUrl}
                    results={resultsData || null}
                    onTimeUpdate={setCurrentVideoTime}
                    seekTime={seekTime}
                  />
                )}
                
                {/* Processing Overlay mask */}
                {(isProcessing || (!processingComplete && !processingError)) && (
                  <div className="absolute inset-0 bg-black/80 flex flex-col items-center justify-center p-8 text-white z-20 backdrop-blur-sm">
                    {!isProcessing && !processingComplete && !processingError ? (
                      <div className="text-center max-w-sm">
                        <Cpu className="h-12 w-12 text-primary mx-auto mb-4" />
                        <h3 className="text-xl font-bold mb-2">Video Ready for Analysis</h3>
                        <p className="text-sm text-gray-400 mb-6">Run the Unified Video Processor to extract infrastructure hazards and traffic density.</p>
                        <Button onClick={startProcessing} loading={processMutation.isPending} className="w-full" size="lg">
                          Start AI Analysis
                        </Button>
                      </div>
                    ) : isProcessing ? (
                      <div className="w-full max-w-md bg-card/10 border border-white/20 p-6 rounded-xl">
                        <div className="flex justify-between items-end mb-4">
                          <div>
                            <h4 className="font-bold flex items-center gap-2 text-lg">
                              <Cpu className="h-5 w-5 text-primary animate-pulse" /> 
                              {progressPercent === 100 ? 'Finalizing...' : 'Processing Frame Detections'}
                            </h4>
                            <p className="text-sm text-gray-400 mt-1">
                              Status: {statusData?.status ?? 'queued'}
                              {statusData?.processing_fps ? ` · ${statusData.processing_fps.toFixed(1)} fps` : ''}
                            </p>
                          </div>
                          <div className="text-right">
                            <span className="text-sm font-mono text-gray-400">
                              {statusData?.progress_frames ?? 0} / {statusData?.total_frames ?? '?'}
                            </span>
                            <p className="text-3xl font-bold text-primary leading-none mt-1">{progressPercent}%</p>
                          </div>
                        </div>
                        <div className="w-full h-3 bg-white/10 rounded-full overflow-hidden">
                          <div className="h-full bg-primary transition-all duration-300" style={{ width: `${progressPercent}%` }} />
                        </div>
                      </div>
                    ) : null}
                  </div>
                )}
                
                {/* Processing Error Overlay */}
                {processingError && !isProcessing && (
                  <div className="absolute inset-0 bg-black/90 flex flex-col items-center justify-center p-8 text-white z-20 backdrop-blur-sm">
                    <AlertTriangle className="h-12 w-12 text-red-500 mx-auto mb-4" />
                    <h3 className="text-xl font-bold text-red-500 mb-2">Analysis Failed</h3>
                    <p className="text-sm text-gray-400 mb-6 max-w-md text-center">{processingError}</p>
                    <Button variant="outline" onClick={() => { setProcessingError(null); setIsProcessing(false); }}>
                      Acknowledge
                    </Button>
                  </div>
                )}
              </div>

              {/* Lower Section: Traffic + Journey Info (Only when complete) */}
              {processingComplete && resultsData && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 flex-1">
                  <TrafficDensityPanel results={resultsData} currentTime={currentVideoTime} />
                  
                  {/* Journey Card */}
                  <div className="bg-card border border-border rounded-lg shadow-sm flex flex-col">
                    <div className="px-4 py-3 border-b border-border flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <FileVideo className="h-4 w-4 text-primary" />
                        <h3 className="font-semibold text-sm">Journey Configuration</h3>
                      </div>
                      <span className="text-xs font-semibold bg-green-100 text-green-700 px-2 py-0.5 rounded flex items-center gap-1">
                        <CheckCircle2 className="h-3 w-3" /> Processed
                      </span>
                    </div>
                    <div className="p-5 flex-1 flex flex-col justify-between">
                      <div className="space-y-4">
                        <div>
                          <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Source Video</p>
                          <p className="text-sm font-medium">{selectedFile?.name || statusData?.video_id || 'video.mp4'}</p>
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                          <div>
                            <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Duration</p>
                            <p className="text-sm font-medium">
                              {resultsData.video?.duration_seconds ? `${Math.round(resultsData.video.duration_seconds)}s` : 'Unknown'}
                            </p>
                          </div>
                          <div>
                            <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Resolution</p>
                            <p className="text-sm font-medium font-mono">
                              {resultsData.video?.width || '?'}x{resultsData.video?.height || '?'}
                            </p>
                          </div>
                        </div>
                      </div>
                      
                      <div className="mt-6 pt-5 border-t border-border">
                        <p className="text-sm text-muted-foreground mb-4">
                          Add this processed journey to the active fleet for Live Monitoring and incident dispatch.
                        </p>
                        <Button className="w-full" onClick={() => setIsAddModalOpen(true)} icon={Play}>
                          Add to Live Monitoring
                        </Button>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Right Column - Detection Summary */}
            <div className="xl:col-span-4 flex flex-col gap-6">
              <DetectionSummary results={processingComplete ? resultsData : null} onSeek={handleSeek} />
            </div>
          </div>
        )}
      </div>

      {videoId && (
        <AddJourneyModal 
          isOpen={isAddModalOpen} 
          onClose={() => setIsAddModalOpen(false)}
          preUploadedVideoId={videoId}
          preUploadedFilename={selectedFile?.name || statusData?.video_id || 'video'}
          preProcessedDuration={
            resultsData?.video?.duration_seconds || 
            resultsData?.metadata?.video_duration || 
            (statusData?.total_frames && statusData?.processing_fps ? (statusData.total_frames / statusData.processing_fps) : 0)
          }
        />
      )}
    </div>
  );
}
