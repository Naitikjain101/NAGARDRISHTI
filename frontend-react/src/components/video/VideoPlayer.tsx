import { useRef, useState, useEffect } from 'react';
import { Layers, Play, Pause, Maximize, Minimize, Volume2, VolumeX } from 'lucide-react';
import { DetectionOverlay } from './DetectionOverlay';
import { cn } from '@/lib/utils';

interface VideoPlayerProps {
  src: string;
  results: any; // The full JSON results from UnifiedVideoProcessor
  onTimeUpdate?: (time: number) => void;
  seekTime?: number | null;
}

export function VideoPlayer({ src, results, onTimeUpdate, seekTime }: VideoPlayerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isMuted, setIsMuted] = useState(true);

  // Layers
  const [showVehicles, setShowVehicles] = useState(true);
  const [showPotholes, setShowPotholes] = useState(true);
  const [showWaterlogging, setShowWaterlogging] = useState(true);
  const [showDebug, setShowDebug] = useState(false);

  // Fullscreen handling
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  const toggleFullscreen = async () => {
    if (!containerRef.current) return;
    if (!document.fullscreenElement) {
      try {
        await containerRef.current.requestFullscreen();
      } catch (e) {
        console.error("Error attempting to enable fullscreen:", e);
      }
    } else {
      if (document.exitFullscreen) {
        await document.exitFullscreen();
      }
    }
  };

  // Playback control
  const togglePlay = () => {
    if (!videoRef.current) return;
    if (videoRef.current.paused) {
      videoRef.current.play();
    } else {
      videoRef.current.pause();
    }
  };

  const handleTimeUpdate = () => {
    if (!videoRef.current) return;
    setCurrentTime(videoRef.current.currentTime);
    if (onTimeUpdate) {
      onTimeUpdate(videoRef.current.currentTime);
    }
  };

  const handleLoadedMetadata = () => {
    if (!videoRef.current) return;
    setDuration(videoRef.current.duration);
  };

  // Seek timeline manually via prop
  useEffect(() => {
    if (seekTime !== undefined && seekTime !== null && videoRef.current) {
      videoRef.current.currentTime = seekTime;
      // Also ensure it is paused so user can see it
      videoRef.current.pause();
    }
  }, [seekTime]);

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const time = parseFloat(e.target.value);
    if (videoRef.current) {
      videoRef.current.currentTime = time;
      setCurrentTime(time);
    }
  };

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  // Prepare event markers for the timeline
  const potholes = results?.pothole_events || [];
  const waterlogging = results?.waterlogging_events || [];
  const allEvents = [...potholes, ...waterlogging];

  return (
    <div
      ref={containerRef}
      className={cn(
        "relative w-full bg-black flex items-center justify-center group overflow-hidden",
        isFullscreen ? "h-screen" : "h-[450px] lg:h-[600px] rounded-lg border border-border"
      )}
    >
      <video
        ref={videoRef}
        src={src}
        className="w-full h-full object-contain"
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleLoadedMetadata}
        onClick={togglePlay}
        muted={isMuted}
        playsInline
      />

      {/* Layer Toggles Overlay */}
      <div className="absolute top-4 right-4 bg-black/60 backdrop-blur border border-white/10 rounded-md p-3 text-white z-30 opacity-0 group-hover:opacity-100 transition-opacity">
        <div className="flex items-center gap-2 mb-2 text-sm font-semibold">
          <Layers className="h-4 w-4" /> Layers
        </div>
        <label className="flex items-center gap-2 text-xs mb-1.5 cursor-pointer hover:text-primary transition-colors">
          <input type="checkbox" checked={showVehicles} onChange={e => setShowVehicles(e.target.checked)} className="accent-primary w-3 h-3" /> Vehicles
        </label>
        <label className="flex items-center gap-2 text-xs mb-1.5 cursor-pointer hover:text-orange-400 transition-colors">
          <input type="checkbox" checked={showPotholes} onChange={e => setShowPotholes(e.target.checked)} className="accent-orange-500 w-3 h-3" /> Potholes
        </label>
        <label className="flex items-center gap-2 text-xs cursor-pointer hover:text-blue-400 transition-colors mb-1.5">
          <input type="checkbox" checked={showWaterlogging} onChange={e => setShowWaterlogging(e.target.checked)} className="accent-blue-500 w-3 h-3" /> Waterlogging
        </label>
        <hr className="border-white/10 my-1.5" />
        <label className="flex items-center gap-2 text-xs cursor-pointer hover:text-gray-300 transition-colors">
          <input type="checkbox" checked={showDebug} onChange={e => setShowDebug(e.target.checked)} className="accent-gray-400 w-3 h-3" /> Debug Classes
        </label>
      </div>

      {/* Detection Overlay */}
      {results && results.frames && (
        <DetectionOverlay
          videoRef={videoRef as React.RefObject<HTMLVideoElement>}
          frames={results.frames}
          potholeEvents={results.pothole_events}
          waterloggingEvents={results.waterlogging_events}
          showVehicles={showVehicles}
          showPotholes={showPotholes}
          showWaterlogging={showWaterlogging}
          showDebug={showDebug}
        />
      )}

      {/* Custom Controls */}
      <div className={cn(
        "absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/90 via-black/60 to-transparent pt-12 pb-4 px-4 z-40 transition-opacity duration-300",
        isPlaying ? "opacity-0 group-hover:opacity-100" : "opacity-100"
      )}>
        {/* Timeline */}
        <div className="relative w-full h-1.5 bg-white/20 rounded-full mb-4 group/timeline cursor-pointer">
          <div 
            className="absolute top-0 left-0 h-full bg-primary rounded-full pointer-events-none" 
            style={{ width: `${(currentTime / (duration || 1)) * 100}%` }} 
          />
          {/* Event markers */}
          {duration > 0 && allEvents.map((evt: any, i: number) => {
            const left = (evt.first_seen_timestamp / duration) * 100;
            const isPothole = evt.incident_type === 'pothole' || evt.type === 'pothole';
            return (
              <div 
                key={i} 
                className={cn(
                  "absolute top-1/2 -translate-y-1/2 w-1.5 h-3 rounded-full pointer-events-none shadow-sm",
                  isPothole ? "bg-orange-500" : "bg-blue-500"
                )}
                style={{ left: `${Math.min(100, Math.max(0, left))}%` }}
              />
            );
          })}
          <input
            type="range"
            min={0}
            max={duration || 100}
            step={0.1}
            value={currentTime}
            onChange={handleSeek}
            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
          />
          {/* Timeline hover thumb */}
          <div 
            className="absolute top-1/2 -translate-y-1/2 w-3 h-3 bg-white rounded-full shadow pointer-events-none opacity-0 group-hover/timeline:opacity-100 transition-opacity"
            style={{ left: `calc(${(currentTime / (duration || 1)) * 100}% - 6px)` }}
          />
        </div>

        {/* Buttons & Time */}
        <div className="flex items-center justify-between text-white">
          <div className="flex items-center gap-4">
            <button onClick={togglePlay} className="hover:text-primary transition-colors focus:outline-none">
              {isPlaying ? <Pause className="h-5 w-5" fill="currentColor" /> : <Play className="h-5 w-5" fill="currentColor" />}
            </button>
            <button onClick={() => setIsMuted(!isMuted)} className="hover:text-primary transition-colors focus:outline-none">
              {isMuted ? <VolumeX className="h-5 w-5" /> : <Volume2 className="h-5 w-5" />}
            </button>
            <div className="text-xs font-mono select-none">
              {formatTime(currentTime)} / {formatTime(duration)}
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            <button onClick={toggleFullscreen} className="hover:text-primary transition-colors focus:outline-none">
              {isFullscreen ? <Minimize className="h-5 w-5" /> : <Maximize className="h-5 w-5" />}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
