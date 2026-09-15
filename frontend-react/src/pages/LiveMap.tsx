import { useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { MapView } from '@/components/map/MapView';
import { useMapIntelligence, type MapIncident } from '@/hooks/useMapIntelligence';
import { IncidentDrawer } from '@/components/incidents/IncidentDrawer';
import { Layers, AlertTriangle, Car, Activity, PlayCircle, Search, Wrench, CheckCircle2, Clock } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Navigate } from 'react-router-dom';
import { FleetReplay } from './FleetReplay';

export function LiveMap() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const missionId = searchParams.get('mission');
  const demoMode = searchParams.get('demo') === 'fleet';
  
  const [filterType, setFilterType] = useState<string>('all');
  const [activeTab, setActiveTab] = useState<'PRIORITY' | 'ACTIONS'>('PRIORITY');
  const [selectedIncident, setSelectedIncident] = useState<MapIncident | null>(null);
  
  // Realtime map data polling
  const { incidents: allIncidents, buses, summary, isLoading } = useMapIntelligence();

  if (missionId) {
    // Redirect legacy mission map links to the new Live Monitoring dashboard
    return <Navigate to={`/monitoring`} replace />;
  }

  if (demoMode) {
    return <FleetReplay />;
  }

  const incidents = filterType === 'all' 
    ? allIncidents 
    : filterType === 'critical'
      ? allIncidents.filter(i => i.severity === 'CRITICAL')
      : allIncidents.filter(i => (i.type || i.incident_type) === filterType);

  // Priority Queue should exclude incidents that have been resolved or rejected
  const activeIncidents = incidents.filter(i => {
    if (!i.action) return true;
    return i.action.status !== 'RESOLVED' && i.action.status !== 'REJECTED';
  });

  // Action Center metrics
  const allActions = incidents.filter(i => i.action);
  const openActions = allActions.filter(i => i.action?.status !== 'RESOLVED' && i.action?.status !== 'REJECTED');
  
  // Sort actions by priority then last_seen
  const sortedActions = [...allActions].sort((a, b) => {
    if (a.action?.status === 'RESOLVED' && b.action?.status !== 'RESOLVED') return 1;
    if (b.action?.status === 'RESOLVED' && a.action?.status !== 'RESOLVED') return -1;
    if ((b.priority_score || 0) !== (a.priority_score || 0)) {
       return (b.priority_score || 0) - (a.priority_score || 0);
    }
    const timeA = new Date(a.last_seen_at || 0).getTime();
    const timeB = new Date(b.last_seen_at || 0).getTime();
    return timeB - timeA;
  });

  // Priority Queue logic
  const priorityQueue = [...activeIncidents].sort((a, b) => {
    if ((b.priority_score || 0) !== (a.priority_score || 0)) {
       return (b.priority_score || 0) - (a.priority_score || 0);
    }
    const busCountA = a.observed_by?.length || 0;
    const busCountB = b.observed_by?.length || 0;
    if (busCountB !== busCountA) return busCountB - busCountA;
    const timeA = new Date(a.last_seen_at || 0).getTime();
    const timeB = new Date(b.last_seen_at || 0).getTime();
    return timeB - timeA;
  });

  const getPriorityColor = (level?: string) => {
    switch (level) {
      case 'CRITICAL': return 'text-red-500 bg-red-500/10 border-red-500/20';
      case 'HIGH': return 'text-orange-500 bg-orange-500/10 border-orange-500/20';
      case 'MEDIUM': return 'text-yellow-500 bg-yellow-500/10 border-yellow-500/20';
      default: return 'text-emerald-500 bg-emerald-500/10 border-emerald-500/20';
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-2rem)] space-y-4">
      {/* Header & Fleet KPI Bar */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-foreground to-muted-foreground">Command Center</h1>
          <p className="text-sm text-muted-foreground mt-1">Municipal incident prioritization and fleet telemetry</p>
        </div>
        <div className="flex items-center gap-4">
          <button 
            onClick={() => navigate('/monitoring')}
            className="flex items-center gap-2 bg-indigo-500 hover:bg-indigo-600 text-white px-4 py-2 rounded-full text-sm font-bold shadow-lg shadow-indigo-500/20 transition-all border border-indigo-400"
          >
            <PlayCircle className="w-4 h-4" /> START FLEET DEMO
          </button>
          <div className="flex items-center gap-3 bg-secondary px-4 py-2 rounded-full border border-border">
            <div className="flex items-center gap-2">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
              <span className="text-xs font-mono font-medium text-emerald-500 tracking-wider">LIVE FEED</span>
            </div>
            <div className="h-4 w-[1px] bg-border"></div>
            <span className="text-xs font-mono text-muted-foreground">{summary?.fleet.total_buses || buses.length} BUSES ACTIVE</span>
          </div>
        </div>
      </div>
      
      {/* Dynamic KPI Bar */}
      <div className="grid grid-cols-5 gap-4">
        <div className="bg-card border border-border p-4 rounded-xl flex items-center justify-between shadow-sm">
          <div>
             <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Total Buses</p>
             <p className="text-2xl font-black mt-1">{summary?.fleet.total_buses || buses.length}</p>
          </div>
          <Car className="w-8 h-8 text-blue-500 opacity-50" />
        </div>
        <div className="bg-card border border-border p-4 rounded-xl flex items-center justify-between shadow-sm">
          <div>
             <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Active Journeys</p>
             <p className="text-2xl font-black mt-1">{summary?.fleet.active_journeys || '-'}</p>
          </div>
          <Activity className="w-8 h-8 text-blue-500 opacity-50" />
        </div>
        <div className="bg-card border border-border p-4 rounded-xl flex items-center justify-between shadow-sm">
          <div>
             <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Coverage</p>
             <p className="text-2xl font-black mt-1">{summary?.coverage.observed_route_km || '0'} <span className="text-sm text-muted-foreground font-medium">km</span></p>
          </div>
          <Layers className="w-8 h-8 text-indigo-500 opacity-50" />
        </div>
        <div className="bg-card border border-border p-4 rounded-xl flex items-center justify-between shadow-sm">
          <div>
             <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Open Incidents</p>
             <p className="text-2xl font-black mt-1 text-orange-500">{summary?.incidents.open || activeIncidents.length}</p>
          </div>
          <AlertTriangle className="w-8 h-8 text-orange-500 opacity-50" />
        </div>
        <div className="bg-card border border-border p-4 rounded-xl flex items-center justify-between shadow-sm">
          <div>
             <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Confirmed Issues</p>
             <p className="text-2xl font-black mt-1 text-red-500">{summary?.incidents.confirmed || allIncidents.filter(i => i.dedup_status === 'CONFIRMED').length}</p>
          </div>
          <AlertTriangle className="w-8 h-8 text-red-500 opacity-50" />
        </div>
      </div>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-4 gap-4 h-full min-h-0">
        
        {/* Left Sidebar - Dual Tabs */}
        <div className="col-span-1 bg-card border border-border rounded-2xl flex flex-col overflow-hidden shadow-lg">
          <div className="flex border-b border-border">
            <button
              onClick={() => setActiveTab('PRIORITY')}
              className={cn(
                "flex-1 py-3 text-xs font-bold tracking-widest uppercase transition-colors flex items-center justify-center gap-2",
                activeTab === 'PRIORITY' ? "bg-muted/30 border-b-2 border-orange-500 text-foreground" : "text-muted-foreground hover:bg-secondary/50"
              )}
            >
              <AlertTriangle className="w-4 h-4" /> Queue
            </button>
            <button
              onClick={() => setActiveTab('ACTIONS')}
              className={cn(
                "flex-1 py-3 text-xs font-bold tracking-widest uppercase transition-colors flex items-center justify-center gap-2",
                activeTab === 'ACTIONS' ? "bg-muted/30 border-b-2 border-emerald-500 text-foreground" : "text-muted-foreground hover:bg-secondary/50"
              )}
            >
              <Wrench className="w-4 h-4" /> Actions
              {openActions.length > 0 && (
                <span className="bg-emerald-500 text-white text-[10px] px-1.5 py-0.5 rounded-full">{openActions.length}</span>
              )}
            </button>
          </div>

          {activeTab === 'PRIORITY' ? (
            <>
              <div className="p-4 border-b border-border bg-muted">
                <p className="text-xs text-muted-foreground">Ranked by Urban Watch Maintenance Score</p>
                {/* Quick Filter */}
                <div className="flex items-center gap-2 mt-3 overflow-x-auto pb-1">
                  {['all', 'pothole', 'waterlogging', 'critical'].map(f => (
                    <button
                      key={f}
                      onClick={() => setFilterType(f)}
                      className={cn(
                        "px-3 py-1 text-[10px] font-bold uppercase tracking-wider rounded-full border whitespace-nowrap transition-colors",
                        filterType === f 
                          ? "bg-primary text-primary-foreground border-primary" 
                          : "bg-background text-muted-foreground border-border hover:border-foreground/50"
                      )}
                    >
                      {f}
                    </button>
                  ))}
                </div>
              </div>
              
              <div className="flex-1 overflow-y-auto p-3 space-y-3">
                {priorityQueue.map((inc, idx) => (
                  <button 
                    key={inc.id}
                    onClick={() => setSelectedIncident(inc)}
                    className={cn(
                      "w-full text-left p-3 rounded-xl border transition-all animate-in slide-in-from-left-4 fade-in duration-300",
                      selectedIncident?.id === inc.id 
                        ? "bg-secondary border-primary shadow-md ring-1 ring-primary/20" 
                        : "bg-background hover:bg-secondary/50 border-border"
                    )}
                    style={{ animationDelay: `${idx * 50}ms` }}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-black text-muted-foreground">#{idx + 1}</span>
                        <span className="text-sm font-bold uppercase tracking-tight">{inc.incident_type.replace('_', ' ')}</span>
                      </div>
                      <div className={cn("px-2 py-0.5 rounded border text-[10px] font-black tracking-widest", getPriorityColor(inc.priority_level))}>
                        {inc.priority_score || 0}
                      </div>
                    </div>
                    
                    <div className="grid grid-cols-2 gap-2 text-[10px]">
                      <div>
                        <span className="text-muted-foreground uppercase font-semibold">Priority</span>
                        <p className={cn("font-bold", inc.priority_level === 'CRITICAL' ? 'text-red-500' : 'text-foreground')}>{inc.priority_level || 'LOW'}</p>
                      </div>
                      <div>
                        <span className="text-muted-foreground uppercase font-semibold">Evidence</span>
                        <p className="font-bold">{inc.observed_by?.length || 1} Buses</p>
                      </div>
                    </div>
                  </button>
                ))}
                {priorityQueue.length === 0 && (
                  <div className="flex flex-col items-center justify-center h-40 text-muted-foreground opacity-60">
                    <Search className="w-8 h-8 mb-2" />
                    <p className="text-sm">No active incidents</p>
                  </div>
                )}
              </div>
            </>
          ) : (
            <>
              <div className="p-4 border-b border-border bg-muted">
                <div className="grid grid-cols-2 gap-2 text-center">
                  <div className="bg-background border border-border rounded-lg py-2">
                    <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest mb-1">Open</p>
                    <p className="text-xl font-black text-emerald-500">{openActions.length}</p>
                  </div>
                  <div className="bg-background border border-border rounded-lg py-2">
                    <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest mb-1">In Progress</p>
                    <p className="text-xl font-black">{allActions.filter(a => a.action?.status === 'RESOLVED').length}</p>
                  </div>
                </div>
              </div>
              <div className="flex-1 overflow-y-auto p-3 space-y-3">
                {sortedActions.map((inc, idx) => (
                  <button 
                    key={inc.id}
                    onClick={() => setSelectedIncident(inc)}
                    className={cn(
                      "w-full text-left p-3 rounded-xl border transition-colors",
                      selectedIncident?.id === inc.id 
                        ? "bg-secondary border-primary shadow-md ring-1 ring-primary/20" 
                        : "bg-background hover:bg-secondary/50 border-border"
                    )}
                    style={{ animationDelay: `${idx * 50}ms` }}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex flex-col">
                        <span className="text-xs font-mono font-bold text-muted-foreground">WO-{inc.action?.id.split('-')[0].toUpperCase()}</span>
                        <span className="text-sm font-bold uppercase tracking-tight mt-1">{inc.incident_type.replace('_', ' ')}</span>
                      </div>
                      <span className={cn("text-[10px] font-bold px-2 py-0.5 rounded uppercase", 
                        inc.action?.status === 'ASSIGNED' ? 'bg-blue-500/10 text-blue-500 border border-blue-500/20' :
                        inc.action?.status === 'IN_PROGRESS' ? 'bg-orange-500/10 text-orange-500 border border-orange-500/20' :
                        inc.action?.status === 'RESOLVED' ? 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20' :
                        'bg-secondary text-muted-foreground'
                      )}>
                        {inc.action?.status.replace('_', ' ')}
                      </span>
                    </div>
                    
                    <div className="mt-2 text-[10px] text-muted-foreground space-y-1">
                      <div className="flex items-center gap-1"><Wrench className="w-3 h-3" /> {inc.action?.assigned_team}</div>
                      <div className="flex items-center gap-1"><Clock className="w-3 h-3" /> Updated {new Date(inc.action?.updated_at || inc.last_seen_at || inc.created_at || new Date().toISOString()).toLocaleDateString()}</div>
                    </div>
                  </button>
                ))}
                {sortedActions.length === 0 && (
                  <div className="flex flex-col items-center justify-center h-40 text-muted-foreground opacity-60">
                    <CheckCircle2 className="w-8 h-8 mb-2" />
                    <p className="text-sm">No maintenance actions</p>
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        {/* Center/Right - Main Map Area */}
        <div className="col-span-1 lg:col-span-3 bg-card rounded-2xl overflow-hidden relative border border-border shadow-sm">
          <div className="absolute inset-0 z-0">
            <MapView 
              incidents={incidents}
              buses={buses}
              onIncidentClick={setSelectedIncident}
              selectedIncident={selectedIncident}
            />
          </div>

          {isLoading && (
            <div className="absolute inset-0 bg-background/50 z-50 flex items-center justify-center pointer-events-none">
              <div className="px-5 py-3 bg-card border border-border rounded-full shadow-2xl font-medium text-sm flex items-center gap-3">
                <div className="w-4 h-4 rounded-full border-2 border-primary border-t-transparent animate-spin" />
                Syncing Command Center...
              </div>
            </div>
          )}

          <IncidentDrawer 
            incident={selectedIncident} 
            onClose={() => setSelectedIncident(null)} 
          />
        </div>

      </div>
    </div>
  );
}
