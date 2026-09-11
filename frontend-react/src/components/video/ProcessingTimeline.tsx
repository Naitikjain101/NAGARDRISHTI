import type { ProcessingStatusResponse } from '@/api/video';

interface ProcessingTimelineProps {
  status: ProcessingStatusResponse | null;
}

export function ProcessingTimeline({ status }: ProcessingTimelineProps) {
  if (!status) return null;

  const progressPercent = status.total_frames > 0 
    ? Math.round((status.progress_frames / status.total_frames) * 100) 
    : 0;

  return (
    <div className="bg-card border border-border rounded-lg p-4 space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="font-semibold">AI Processing Status</h3>
        <span className={`px-2 py-1 rounded text-xs font-medium uppercase ${
          status.status === 'completed' ? 'bg-emerald-500/20 text-emerald-500' :
          status.status === 'running' ? 'bg-blue-500/20 text-blue-500' :
          status.status === 'failed' ? 'bg-destructive/20 text-destructive' :
          'bg-muted text-muted-foreground'
        }`}>
          {status.status}
        </span>
      </div>

      <div className="space-y-1">
        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">Progress</span>
          <span>{progressPercent}%</span>
        </div>
        <div className="w-full bg-secondary rounded-full h-2">
          <div 
            className="bg-primary h-2 rounded-full transition-all duration-300" 
            style={{ width: `${progressPercent}%` }}
          />
        </div>
        <div className="flex justify-between text-xs text-muted-foreground pt-1">
          <span>{status.progress_frames} / {status.total_frames} frames</span>
          {status.processing_fps && <span>{status.processing_fps.toFixed(1)} FPS</span>}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 pt-4 border-t border-border">
        <div>
          <p className="text-xs text-muted-foreground">Vehicles</p>
          <p className="text-xl font-semibold">{status.current_vehicles}</p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground">Potholes</p>
          <p className="text-xl font-semibold text-orange-500">{status.current_potholes}</p>
        </div>
      </div>
      
      {status.error && (
        <div className="mt-4 p-3 bg-destructive/10 border border-destructive/20 rounded-md">
          <p className="text-sm text-destructive">{status.error}</p>
        </div>
      )}
    </div>
  );
}
