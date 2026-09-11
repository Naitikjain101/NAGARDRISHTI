import { EmptyState } from '@/components/ui/EmptyState';
import { Camera, Maximize2 } from 'lucide-react';

export function LiveMonitoring() {
  return (
    <div className="space-y-6 flex flex-col h-full">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold">Live Monitoring</h1>
          <p className="text-muted-foreground">Real-time CCTV grid view across the urban network.</p>
        </div>
        <button className="flex items-center gap-2 px-4 py-2 bg-secondary text-secondary-foreground rounded-md hover:bg-secondary/80 transition-colors">
          <Maximize2 className="h-4 w-4" />
          <span>Full Screen Grid</span>
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 flex-1">
        {[1, 2, 3, 4, 5, 6].map((feed) => (
          <div key={feed} className="bg-card border border-border rounded-lg overflow-hidden flex flex-col h-[250px]">
            <div className="p-2 border-b border-border bg-secondary/30 flex justify-between items-center">
              <span className="text-xs font-medium font-mono text-muted-foreground">CAM_{feed.toString().padStart(3, '0')}</span>
              <div className="flex items-center gap-1">
                <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse"></div>
                <span className="text-[10px] uppercase font-bold text-red-500 tracking-wider">Offline</span>
              </div>
            </div>
            <div className="flex-1">
              <EmptyState 
                icon={Camera}
                title="Feed Unavailable"
                description="RTSP stream not connected"
                className="border-none bg-transparent"
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
