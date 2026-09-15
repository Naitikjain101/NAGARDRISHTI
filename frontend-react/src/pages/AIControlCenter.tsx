import { useQuery } from '@tanstack/react-query';
import { aiApi } from '@/api/ai';
import { Cpu, Server, Activity, Database, HardDrive, TestTube2, AlertTriangle, XCircle, CheckCircle } from 'lucide-react';
import { StatusBadge } from '@/components/ui/StatusBadge';

const STATUS_META: Record<string, { label: string; color: string; icon: any }> = {
  AVAILABLE:   { label: 'AVAILABLE',   color: 'text-blue-500   border-blue-500/30   bg-blue-500/10',   icon: CheckCircle },
  DEPRECATED:  { label: 'DEPRECATED',  color: 'text-yellow-500 border-yellow-500/30 bg-yellow-500/10', icon: AlertTriangle },
  TEST_MODE:   { label: 'TEST MODE',   color: 'text-orange-500 border-orange-500/30 bg-orange-500/10', icon: TestTube2 },
  UNAVAILABLE: { label: 'UNAVAILABLE', color: 'text-red-500    border-red-500/30    bg-red-500/10',    icon: XCircle },
};

function ModelStatusBadge({ status }: { status: string }) {
  const meta = STATUS_META[status] ?? STATUS_META.AVAILABLE;
  const Icon = meta.icon;
  return (
    <span className={`inline-flex items-center gap-1 text-[10px] font-bold px-1.5 py-0.5 rounded-full border ${meta.color}`}>
      <Icon className="h-3 w-3" /> {meta.label}
    </span>
  );
}

export function AIControlCenter() {
  const { data: device } = useQuery({
    queryKey: ['aiDevice'],
    queryFn: aiApi.getDevice,
  });

  const { data: systemStatus } = useQuery({
    queryKey: ['systemStatus'],
    queryFn: aiApi.getSystemStatus,
    refetchInterval: 10000,
  });

  const { data: registry } = useQuery({
    queryKey: ['aiModels'],
    queryFn: async () => {
      const res = await fetch('/api/ai/models');
      if (!res.ok) throw new Error('Failed to fetch models');
      return res.json();
    },
  });

  // Extract only active models across all tasks
  const activeModels: any[] = [];
  if (registry) {
    Object.values(registry).forEach((taskModels: any) => {
      Object.values(taskModels).forEach((model: any) => {
        if (model.is_active) activeModels.push(model);
      });
    });
  }

  return (
    <div className="space-y-8 max-w-6xl">
      <div className="mb-6">
        <h2 className="text-xl font-bold text-foreground">AI Configuration Profile</h2>
        <p className="text-sm text-muted-foreground mt-1">Read-only overview of currently active system inference configurations.</p>
      </div>

      {/* SYSTEM HEALTH */}
      <section className="space-y-4">
        <h3 className="text-sm font-semibold border-b border-border pb-2 flex items-center gap-2">
          <Activity className="h-4 w-4 text-primary" /> System Health
        </h3>
        
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="bg-card border border-border rounded-lg p-4 flex flex-col items-center text-center space-y-2 shadow-sm">
             <Server className="h-5 w-5 text-muted-foreground" />
             <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground">FastAPI</p>
             <StatusBadge status={systemStatus?.status === 'ok' ? 'ONLINE' : 'ERROR'} type="connectivity" />
          </div>
          <div className="bg-card border border-border rounded-lg p-4 flex flex-col items-center text-center space-y-2 shadow-sm">
             <Database className="h-5 w-5 text-muted-foreground" />
             <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Supabase DB</p>
             <StatusBadge status={systemStatus?.status === 'ok' ? 'ONLINE' : 'ERROR'} type="connectivity" />
          </div>
          <div className="bg-card border border-border rounded-lg p-4 flex flex-col items-center text-center space-y-2 shadow-sm">
             <Cpu className="h-5 w-5 text-muted-foreground" />
             <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground">AI Engine</p>
             <StatusBadge status={systemStatus?.status === 'ok' ? 'ONLINE' : 'ERROR'} type="connectivity" />
          </div>
          <div className="bg-card border border-border rounded-lg p-4 flex flex-col items-center text-center space-y-2 shadow-sm">
             <Activity className="h-5 w-5 text-muted-foreground" />
             <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Hardware Accel</p>
             <StatusBadge status={device?.has_mps ? 'MPS_ACTIVE' : device?.has_cuda ? 'CUDA_ACTIVE' : 'CPU_ONLY'} type={device?.has_mps || device?.has_cuda ? 'connectivity' : 'state'} />
          </div>
          <div className="bg-card border border-border rounded-lg p-4 flex flex-col items-center text-center space-y-2 shadow-sm">
             <HardDrive className="h-5 w-5 text-muted-foreground" />
             <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Storage</p>
             <StatusBadge status="ONLINE" type="connectivity" />
          </div>
        </div>
      </section>

      {/* ACTIVE MODELS */}
      <section className="space-y-4">
        <h3 className="text-sm font-semibold border-b border-border pb-2 flex items-center gap-2">
          <Cpu className="h-4 w-4 text-primary" /> Active Model Deployments
        </h3>
        
        {activeModels.length === 0 ? (
          <div className="bg-card border border-border rounded-lg p-8 flex flex-col items-center justify-center text-center shadow-sm">
             <Cpu className="h-8 w-8 text-muted-foreground mb-3 opacity-50" />
             <p className="font-medium text-foreground">Loading model registry...</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3 gap-4">
            {activeModels.map((model, idx) => (
              <div key={idx} className="bg-card border border-border rounded-lg p-4 shadow-sm flex flex-col">
                <div className="flex justify-between items-start mb-3">
                  <div className="flex items-center gap-2">
                    <div className="p-1.5 bg-primary/10 rounded-md">
                      <Cpu className="h-4 w-4 text-primary" />
                    </div>
                    <div>
                      <h4 className="font-bold text-sm leading-tight text-foreground">{model.display_name}</h4>
                      <p className="text-[10px] uppercase tracking-widest font-bold text-muted-foreground mt-0.5">{model.task}</p>
                    </div>
                  </div>
                </div>
                
                <div className="space-y-2 text-xs flex-1 bg-secondary/20 p-3 rounded border border-border/50">
                  <div className="flex justify-between items-center">
                    <span className="text-muted-foreground font-medium">Architecture</span>
                    <span className="font-mono text-foreground">{model.architecture}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-muted-foreground font-medium">Confidence Threshold</span>
                    <span className="font-mono text-foreground font-bold">{model.confidence_threshold.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-muted-foreground font-medium">Image Size</span>
                    <span className="font-mono text-foreground">{model.imgsz}px</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-muted-foreground font-medium">Status</span>
                    <ModelStatusBadge status={model.status} />
                  </div>
                </div>
                
                {!model.file_exists && (
                  <div className="mt-3 text-[10px] text-red-600 bg-red-500/10 p-2 rounded flex items-start gap-2">
                    <AlertTriangle className="h-3 w-3 shrink-0" />
                    Warning: Model file is missing from disk. Inference will fail for this task.
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </section>
      
      <div className="text-xs text-muted-foreground bg-secondary/30 p-3 rounded-lg border border-border flex items-start gap-2">
         <TestTube2 className="h-4 w-4 shrink-0 text-primary" />
         To modify these configurations or change the active model, please navigate to the Model Lab tab.
      </div>
    </div>
  );
}
