import { X, MapPin, Activity, Cpu, Camera, Clock, ExternalLink, Video } from 'lucide-react';
import type { Incident } from '@/api/incidents';
import { formatDistanceToNow } from 'date-fns';
import { StatusBadge } from './../ui/StatusBadge';

interface IncidentDrawerProps {
  incident: Incident | null;
  onClose: () => void;
}

export function IncidentDrawer({ incident, onClose }: IncidentDrawerProps) {
  if (!incident) return null;

  return (
    <>
      <div 
        className="fixed inset-0 bg-background/50 backdrop-blur-sm z-40"
        onClick={onClose}
      />
      
      <div className="fixed top-0 right-0 h-full w-full max-w-lg bg-card border-l border-border shadow-2xl z-50 overflow-y-auto transform transition-transform duration-300 ease-in-out">
        {/* HEADER */}
        <div className="p-6 border-b border-border flex justify-between items-start sticky top-0 bg-card/95 backdrop-blur-md z-10">
          <div>
            <h2 className="text-xl font-bold capitalize flex items-center gap-2">
              {incident.type.replace('_', ' ')}
            </h2>
            <div className="flex gap-2 mt-2">
              <StatusBadge status={incident.severity} type="severity" />
              <StatusBadge status={incident.status} type="state" />
              <span className="text-xs text-muted-foreground font-mono bg-secondary px-2 rounded-md py-0.5 flex items-center">
                ID: {incident.id.slice(0, 8)}
              </span>
            </div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-secondary rounded-full transition-colors">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="p-6 space-y-8">
          
          {/* EVIDENCE PREVIEW */}
          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-2">
              <Video className="h-4 w-4" /> Evidence Snapshot
            </h3>
            <div className="aspect-video bg-black rounded-lg border border-border flex flex-col items-center justify-center relative overflow-hidden">
              <Camera className="h-8 w-8 text-muted-foreground mb-2" />
              <p className="text-muted-foreground text-sm z-10">Live frame fetch pending backend sync</p>
              <div className="absolute inset-0 bg-gradient-to-tr from-secondary/20 to-transparent"></div>
            </div>
          </div>

          {/* AI DETECTION & SOURCE */}
          <div className="grid grid-cols-2 gap-4">
             <div className="space-y-3">
              <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-2">
                <Cpu className="h-4 w-4" /> Detection
              </h3>
              <div className="bg-secondary/30 p-3 rounded-md border border-border/50 space-y-2 text-sm">
                <div className="flex justify-between"><span className="text-muted-foreground">Model</span><span className="font-medium">YOLOv8-Seg</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Confidence</span><span className="font-medium">{Math.round(incident.confidence * 100)}%</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Frame</span><span className="font-mono">{incident.frame}</span></div>
              </div>
            </div>
            
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-2">
                <Activity className="h-4 w-4" /> Source
              </h3>
              <div className="bg-secondary/30 p-3 rounded-md border border-border/50 space-y-2 text-sm">
                <div className="flex justify-between"><span className="text-muted-foreground">Stream</span><span className="font-medium truncate max-w-[100px]">{incident.video_id}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Type</span><span className="font-medium">Fixed CCTV</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Telemetry</span><span className="font-medium text-emerald-500">Live</span></div>
              </div>
            </div>
          </div>

          {/* LOCATION */}
          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-2">
              <MapPin className="h-4 w-4" /> Location
            </h3>
            <div className="bg-secondary/30 p-4 rounded-md border border-border/50">
              {incident.gps_available ? (
                <div className="flex items-start justify-between">
                  <div>
                     <p className="font-mono text-sm">{incident.latitude?.toFixed(6)}, {incident.longitude?.toFixed(6)}</p>
                     <p className="text-xs text-muted-foreground mt-1">Delhi Urban Grid</p>
                  </div>
                  <button className="text-xs flex items-center gap-1 text-primary hover:underline">
                    View on Map <ExternalLink className="h-3 w-3" />
                  </button>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">No GPS telemetry attached to this frame.</p>
              )}
            </div>
          </div>

          {/* TIMELINE */}
          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-2">
              <Clock className="h-4 w-4" /> Timeline
            </h3>
            <div className="relative border-l border-border ml-3 pl-4 space-y-6">
               <div className="relative">
                 <div className="absolute w-3 h-3 bg-emerald-500 rounded-full -left-[22px] top-1" />
                 <p className="text-sm font-medium">Detected by AI</p>
                 <p className="text-xs text-muted-foreground">{new Date(incident.created_at).toLocaleString()}</p>
                 <p className="text-xs text-muted-foreground">{formatDistanceToNow(new Date(incident.created_at), { addSuffix: true })}</p>
               </div>
               
               <div className="relative opacity-50">
                 <div className="absolute w-3 h-3 bg-secondary border border-border rounded-full -left-[22px] top-1" />
                 <p className="text-sm font-medium">Human Validation</p>
                 <p className="text-xs text-muted-foreground">Pending</p>
               </div>
               
               <div className="relative opacity-50">
                 <div className="absolute w-3 h-3 bg-secondary border border-border rounded-full -left-[22px] top-1" />
                 <p className="text-sm font-medium">Maintenance Dispatched</p>
                 <p className="text-xs text-muted-foreground">Pending</p>
               </div>
            </div>
          </div>

          {/* ACTIONS */}
          <div className="pt-4 border-t border-border flex flex-wrap gap-2">
            <button className="flex-1 bg-primary text-primary-foreground py-2 rounded-md font-medium hover:bg-primary/90 transition-colors text-sm">
              Investigate
            </button>
            <button className="flex-1 bg-secondary text-secondary-foreground py-2 rounded-md font-medium hover:bg-secondary/80 transition-colors text-sm">
              Assign Task
            </button>
            <button className="w-full bg-background border border-border text-muted-foreground py-2 rounded-md font-medium hover:bg-secondary transition-colors text-sm mt-2">
              Dismiss False Positive
            </button>
          </div>

        </div>
      </div>
    </>
  );
}
