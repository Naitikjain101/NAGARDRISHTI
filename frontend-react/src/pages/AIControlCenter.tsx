
import { useQuery } from '@tanstack/react-query';
import { aiApi } from '@/api/ai';
import { Cpu, Server, Activity, Database, HardDrive, Clock } from 'lucide-react';
import { StatusBadge } from '@/components/ui/StatusBadge';

export function AIControlCenter() {
  const { data: device } = useQuery({
    queryKey: ['aiDevice'],
    queryFn: aiApi.getDevice,
  });

  const { data: systemStatus } = useQuery({
    queryKey: ['systemStatus'],
    queryFn: aiApi.getSystemStatus,
    refetchInterval: 5000,
  });

  const models = [
    { id: 'waterlogging', name: 'WATERLOGGING V1', task: 'Segmentation', version: 'YOLOv8-seg', status: 'ACTIVE', conf: '45%' },
    { id: 'pothole', name: 'POTHOLE MODEL', task: 'Detection', version: 'YOLO26m', status: 'ACTIVE', conf: '40%' },
    { id: 'vehicle', name: 'VEHICLE DETECTOR', task: 'Detection & Tracking', version: 'YOLOv8', status: 'ACTIVE', conf: '50%' },
    { id: 'helmet', name: 'HELMET MODEL', task: 'Classification', version: 'YOLOv8-cls', status: 'ACTIVE', conf: '60%' },
  ];

  return (
    <div className="space-y-8 max-w-6xl">
      <div>
        <h1 className="text-2xl font-bold">AI Control Center</h1>
        <p className="text-muted-foreground">Monitor and manage the active computer vision inference engines.</p>
      </div>

      {/* SYSTEM HEALTH */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold border-b border-border pb-2 flex items-center gap-2">
          <Activity className="h-5 w-5 text-primary" /> System Health
        </h2>
        
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="bg-card border border-border rounded-lg p-4 flex flex-col items-center text-center space-y-2">
             <Server className="h-6 w-6 text-muted-foreground" />
             <p className="text-sm font-medium">FastAPI</p>
             <StatusBadge status={systemStatus?.status === 'ok' ? 'ONLINE' : 'ERROR'} type="connectivity" />
          </div>
          <div className="bg-card border border-border rounded-lg p-4 flex flex-col items-center text-center space-y-2">
             <Database className="h-6 w-6 text-muted-foreground" />
             <p className="text-sm font-medium">Supabase DB</p>
             <StatusBadge status={systemStatus?.status === 'ok' ? 'ONLINE' : 'ERROR'} type="connectivity" />
          </div>
          <div className="bg-card border border-border rounded-lg p-4 flex flex-col items-center text-center space-y-2">
             <Cpu className="h-6 w-6 text-muted-foreground" />
             <p className="text-sm font-medium">AI Engine</p>
             <StatusBadge status={systemStatus?.status === 'ok' ? 'ONLINE' : 'ERROR'} type="connectivity" />
          </div>
          <div className="bg-card border border-border rounded-lg p-4 flex flex-col items-center text-center space-y-2">
             <Activity className="h-6 w-6 text-muted-foreground" />
             <p className="text-sm font-medium">Hardware Accel</p>
             <StatusBadge status={device?.has_mps ? 'MPS_ACTIVE' : device?.has_cuda ? 'CUDA_ACTIVE' : 'CPU_ONLY'} type={device?.has_mps || device?.has_cuda ? 'connectivity' : 'state'} />
          </div>
          <div className="bg-card border border-border rounded-lg p-4 flex flex-col items-center text-center space-y-2">
             <HardDrive className="h-6 w-6 text-muted-foreground" />
             <p className="text-sm font-medium">Storage</p>
             <StatusBadge status="ONLINE" type="connectivity" />
          </div>
        </div>
      </section>

      {/* ACTIVE MODELS */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold border-b border-border pb-2 flex items-center gap-2">
          <Cpu className="h-5 w-5 text-primary" /> Active Models
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {models.map(model => (
            <div key={model.id} className="bg-card border border-border rounded-lg p-5">
              <div className="flex justify-between items-start mb-4">
                <div className="p-2 bg-secondary rounded-lg">
                  <Cpu className="h-5 w-5 text-primary" />
                </div>
                <StatusBadge status={model.status} type="state" />
              </div>
              <h3 className="font-bold text-sm tracking-wide">{model.name}</h3>
              <p className="text-muted-foreground text-xs mb-4">{model.task}</p>
              
              <div className="space-y-2 text-xs">
                <div className="flex justify-between"><span className="text-muted-foreground">Version</span><span className="font-mono">{model.version}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Device</span><span className="font-mono uppercase">{device?.device || 'cpu'}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Min Conf</span><span className="font-mono">{model.conf}</span></div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* RECENT JOBS */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold border-b border-border pb-2 flex items-center gap-2">
          <Clock className="h-5 w-5 text-primary" /> Recent AI Jobs
        </h2>
        <div className="bg-card border border-border rounded-lg overflow-hidden">
          <table className="w-full text-sm text-left">
            <thead className="text-xs uppercase bg-secondary/50 text-muted-foreground border-b border-border">
              <tr>
                <th className="px-4 py-3">Video ID</th>
                <th className="px-4 py-3">Model Pipeline</th>
                <th className="px-4 py-3">Started</th>
                <th className="px-4 py-3">Frames</th>
                <th className="px-4 py-3">Events</th>
                <th className="px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
               <tr>
                 <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                   Job history syncing... 
                 </td>
               </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
