import { Maximize2, PlayCircle, Activity, RotateCcw } from 'lucide-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { fleetApi, type Journey } from '@/api/fleet';
import { videoApi } from '@/api/video';
import { useNavigate } from 'react-router-dom';
import { useState } from 'react';
import { PageHeader } from '@/components/ui/PageHeader';
import { Button } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { useToast } from '@/components/ui/Toast';

export function LiveMonitoring() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [isResetConfirmOpen, setIsResetConfirmOpen] = useState(false);
  const [isResetting, setIsResetting] = useState(false);

  const { data: buses } = useQuery({
    queryKey: ['fleet'],
    queryFn: fleetApi.getBuses,
    refetchInterval: 5000,
  });

  const readyJourneys: Journey[] = [];
  if (buses) {
    buses.forEach(bus => {
      if (bus.journeys) {
        bus.journeys.forEach(j => {
          if (j.status.toUpperCase() === 'READY') {
            readyJourneys.push(j);
          }
        });
      }
    });
  }

  const handleReset = async () => {
    setIsResetting(true);
    try {
      const res = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/missions/reset`, {
        method: 'POST',
      });
      if (res.ok) {
        queryClient.invalidateQueries({ queryKey: ['fleet'] });
        queryClient.invalidateQueries({ queryKey: ['map_incidents'] });
        toast.success('Session reset', 'All Live Monitoring sessions and incidents have been cleared.');
      } else {
        throw new Error('Reset failed');
      }
    } catch (e) {
      toast.error('Reset failed', 'Unable to reset the session. Please try again.');
    } finally {
      setIsResetting(false);
      setIsResetConfirmOpen(false);
    }
  };

  return (
    <div className="page-content">
      <PageHeader
        title="Live Monitoring"
        description="Replay AI-processed survey video feeds across the urban network."
        icon={Activity}
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              icon={Maximize2}
            >
              Full Screen Grid
            </Button>
            <Button
              variant="outline"
              size="sm"
              icon={RotateCcw}
              onClick={() => setIsResetConfirmOpen(true)}
              className="text-destructive border-destructive/30 hover:bg-red-50"
            >
              Reset Data
            </Button>
          </div>
        }
      />

      {/* Feed grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 flex-1">
        {readyJourneys.map((journey) => (
          <div
            key={journey.id}
            className="bg-card border border-primary/20 rounded-lg overflow-hidden flex flex-col shadow-card cursor-pointer group"
            style={{ minHeight: 240 }}
            onClick={() => navigate(`/map?mission=${journey.id}`)}
          >
            {/* Feed header */}
            <div className="px-3 py-2 border-b border-border/60 bg-secondary/40 flex items-center justify-between shrink-0">
              <div className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                <span className="text-xs font-mono font-medium text-foreground">
                  {journey.bus_id || 'VEHICLE'}
                </span>
              </div>
              <span className="text-[10px] font-semibold uppercase tracking-wider text-green-600 bg-green-50 px-2 py-0.5 rounded border border-green-200">
                AI REPLAY
              </span>
            </div>

            {/* Video preview */}
            <div className="flex-1 flex flex-col items-center justify-center bg-gray-900 relative overflow-hidden" style={{ minHeight: 180 }}>
              {journey.metadata?.video_id && (
                <video
                  src={`${videoApi.getStreamUrl(journey.metadata.video_id)}#t=2.0`}
                  className="absolute inset-0 w-full h-full object-cover opacity-70"
                  muted
                  playsInline
                />
              )}
              <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-transparent pointer-events-none" />

              <div className="relative z-10 text-center p-4 mt-auto w-full">
                <PlayCircle className="w-10 h-10 text-white/80 mx-auto mb-2 group-hover:text-white group-hover:scale-110 transition-all duration-200" />
                <p className="text-white font-semibold text-sm mb-0.5">{journey.route_name || 'Urban Survey Route'}</p>
                <p className="text-xs text-white/60 font-mono">Click to open replay</p>
              </div>
            </div>
          </div>
        ))}

        {readyJourneys.length === 0 && (
          <div className="col-span-full">
            <EmptyState
              icon={Activity}
              title="No Active Sessions"
              description="Upload and process videos in Fleet, then add them to Live Monitoring to replay AI detections here."
              className="border-2 border-dashed border-border rounded-lg min-h-[300px]"
            />
          </div>
        )}
      </div>

      {/* Confirm reset dialog */}
      <ConfirmDialog
        isOpen={isResetConfirmOpen}
        onClose={() => setIsResetConfirmOpen(false)}
        onConfirm={handleReset}
        loading={isResetting}
        title="Reset Live Monitoring?"
        description="This will remove all Live Monitoring sessions and their associated incidents from this session. This action cannot be undone."
        confirmLabel="Confirm Reset"
        variant="destructive"
      />
    </div>
  );
}
