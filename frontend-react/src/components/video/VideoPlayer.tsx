import { useRef, useState } from 'react';
import { Layers } from 'lucide-react';
import { DetectionOverlay } from './DetectionOverlay';

interface VideoPlayerProps {
  src: string;
  results: any; // The full JSON results from UnifiedVideoProcessor
}

export function VideoPlayer({ src, results }: VideoPlayerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const [showVehicles, setShowVehicles] = useState(true);
  const [showPotholes, setShowPotholes] = useState(true);
  const [showWaterlogging, setShowWaterlogging] = useState(true);

  return (
    <div
      ref={containerRef}
      className="relative w-full h-[600px] bg-black rounded-lg overflow-hidden border border-border flex items-center justify-center group"
    >
      <video
        ref={videoRef}
        src={src}
        className="w-full h-full object-contain"
        controls
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
        <label className="flex items-center gap-2 text-xs cursor-pointer hover:text-blue-400 transition-colors">
          <input type="checkbox" checked={showWaterlogging} onChange={e => setShowWaterlogging(e.target.checked)} className="accent-blue-500 w-3 h-3" /> Waterlogging
        </label>
      </div>

      {results && results.frames && (
        <DetectionOverlay
          videoRef={videoRef}
          frames={results.frames}
          potholeEvents={results.pothole_events}
          waterloggingEvents={results.waterlogging_events}
          showVehicles={showVehicles}
          showPotholes={showPotholes}
          showWaterlogging={showWaterlogging}
        />
      )}
    </div>
  );
}
