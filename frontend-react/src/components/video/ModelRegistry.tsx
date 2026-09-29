import React, { useEffect, useState, useCallback } from 'react';
import { fetchRaw } from '../../api/client';
import {
  Database, CheckCircle, AlertTriangle, XCircle, RotateCcw,
  ShieldAlert, TestTube2, Package, ChevronDown, ChevronUp, Info
} from 'lucide-react';

// ─── Types ────────────────────────────────────────────────────────────────────

interface ModelEntry {
  model_id: string;
  display_name: string;
  task: string;
  architecture: string;
  version: string;
  sha256: string;
  status: string;
  is_active: boolean;
  is_previous: boolean;
  file_exists: boolean;
  confidence_threshold: number;
  iou_threshold: number;
  imgsz: number;
  device: string;
  notes: string;
  classes?: Record<string, string>;
}

interface RegistryResponse {
  [task: string]: Record<string, ModelEntry>;
}

// ─── Status helpers ───────────────────────────────────────────────────────────

const STATUS_META: Record<string, { label: string; color: string; icon: React.ElementType }> = {
  AVAILABLE:   { label: 'AVAILABLE',   color: 'text-blue-500   border-blue-500/30   bg-blue-500/10',   icon: Package },
  DEPRECATED:  { label: 'DEPRECATED',  color: 'text-yellow-500 border-yellow-500/30 bg-yellow-500/10', icon: AlertTriangle },
  TEST_MODE:   { label: 'TEST MODE',   color: 'text-orange-500 border-orange-500/30 bg-orange-500/10', icon: TestTube2 },
  UNAVAILABLE: { label: 'UNAVAILABLE', color: 'text-red-500    border-red-500/30    bg-red-500/10',    icon: XCircle },
  ERROR:       { label: 'ERROR',       color: 'text-red-600    border-red-600/30    bg-red-600/10',    icon: XCircle },
};

function StatusBadge({ status, isActive }: { status: string; isActive: boolean }) {
  if (isActive) {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-bold px-2 py-0.5 rounded-full border text-green-600 border-green-500/30 bg-green-500/10">
        <CheckCircle className="h-3 w-3" /> ACTIVE
      </span>
    );
  }
  const meta = STATUS_META[status] ?? STATUS_META.AVAILABLE;
  const Icon = meta.icon;
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-bold px-2 py-0.5 rounded-full border ${meta.color}`}>
      <Icon className="h-3 w-3" /> {meta.label}
    </span>
  );
}

// ─── Confirm Modal ────────────────────────────────────────────────────────────

interface ConfirmModalProps {
  open: boolean;
  title: string;
  currentName: string;
  newName: string;
  onCancel: () => void;
  onConfirm: () => void;
  loading: boolean;
}

function ConfirmModal({ open, title, currentName, newName, onCancel, onConfirm, loading }: ConfirmModalProps) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-card border rounded-xl shadow-2xl p-6 w-full max-w-md mx-4 animate-in fade-in zoom-in-95">
        <div className="flex items-center gap-2 mb-4">
          <ShieldAlert className="h-5 w-5 text-orange-500" />
          <h3 className="font-bold text-lg">{title}</h3>
        </div>
        <div className="space-y-3 mb-6">
          <div className="rounded-lg border p-3 bg-muted/30">
            <div className="text-xs text-muted-foreground mb-1">Current Model</div>
            <div className="font-medium text-sm">{currentName}</div>
          </div>
          <div className="flex justify-center">
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          </div>
          <div className="rounded-lg border border-primary/40 p-3 bg-primary/5">
            <div className="text-xs text-primary mb-1">New Model</div>
            <div className="font-medium text-sm text-primary">{newName}</div>
          </div>
        </div>
        <div className="text-xs text-muted-foreground mb-4 bg-muted/40 rounded p-2">
          ⚠️ Only new video processing will use the new model. Historical results, incidents,
          journeys, and evidence are permanently tied to the model that processed them
          and will NOT be changed.
        </div>
        <div className="flex gap-3">
          <button
            onClick={onCancel}
            disabled={loading}
            className="flex-1 py-2 text-sm font-medium border rounded-lg hover:bg-muted/50 transition-colors disabled:opacity-50"
          >
            CANCEL
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className="flex-1 py-2 text-sm font-bold bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors disabled:opacity-50"
          >
            {loading ? 'Switching…' : 'CONFIRM SWITCH'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Model Card ───────────────────────────────────────────────────────────────

function ModelCard({
  modelId,
  model,
  task,
  onSwitch,
  onRollback,
  switching,
}: {
  modelId: string;
  model: ModelEntry;
  task: string;
  onSwitch: (task: string, modelId: string, model: ModelEntry, isConfidenceEdit?: boolean) => void;
  onRollback: (task: string) => void;
  switching: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const sha256Display = model.sha256
    ? `${model.sha256.slice(0, 16)}…${model.sha256.slice(-8)}`
    : 'N/A';

  const isUnavailable = model.status === 'UNAVAILABLE' || !model.file_exists;
  const isTestMode = model.status === 'TEST_MODE';
  const isDeprecated = model.status === 'DEPRECATED';

  return (
    <div
      className={`relative rounded-xl border transition-all duration-200 overflow-hidden
        ${model.is_active
          ? 'border-green-500/40 shadow-[0_0_0_1px_rgb(34,197,94,0.2)] bg-green-500/5'
          : isUnavailable
            ? 'border-red-500/20 bg-red-500/5 opacity-70'
            : 'border-border bg-card hover:border-border/80'
        }`}
    >
      {/* TEST MODE banner */}
      {isTestMode && (
        <div className="flex items-center gap-2 bg-orange-500/10 border-b border-orange-500/20 px-4 py-2 text-xs font-bold text-orange-600">
          <TestTube2 className="h-3 w-3" />
          TEST MODE — NOT PRODUCTION VALIDATED
        </div>
      )}

      {/* DEPRECATED banner */}
      {isDeprecated && (
        <div className="flex items-center gap-2 bg-yellow-500/10 border-b border-yellow-500/20 px-4 py-2 text-xs font-bold text-yellow-600">
          <AlertTriangle className="h-3 w-3" />
          DEPRECATED — Do not use for new production deployments
        </div>
      )}

      {/* FILE NOT FOUND banner */}
      {isUnavailable && (
        <div className="flex items-center gap-2 bg-red-500/10 border-b border-red-500/20 px-4 py-2 text-xs font-bold text-red-600">
          <XCircle className="h-3 w-3" />
          FILE NOT FOUND ON DISK — Model is unavailable
        </div>
      )}

      <div className="p-4">
        {/* Header row */}
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="min-w-0 flex-1">
            <h4 className="font-bold text-sm leading-tight truncate">{model.display_name}</h4>
            <div className="text-xs text-muted-foreground font-mono mt-0.5">{modelId}</div>
          </div>
          <StatusBadge status={model.status} isActive={model.is_active} />
        </div>

        {/* Core fields */}
        <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs mb-3">
          <div>
            <span className="text-muted-foreground">Architecture</span>
            <div className="font-medium text-foreground">{model.architecture}</div>
          </div>
          <div>
            <span className="text-muted-foreground">Version</span>
            <div className="font-medium text-foreground">{model.version || '—'}</div>
          </div>
          <div>
            <span className="text-muted-foreground">Input Size</span>
            <div className="font-medium text-foreground">{model.imgsz}px</div>
          </div>
          <div>
            <span className="text-muted-foreground">Confidence</span>
            <div className="font-medium text-foreground">{model.confidence_threshold.toFixed(2)}</div>
          </div>
          <div className="col-span-2">
            <span className="text-muted-foreground">SHA256</span>
            <div
              className="font-mono text-[10px] text-foreground truncate cursor-help"
              title={model.sha256 || 'Not computed'}
            >
              {sha256Display}
            </div>
          </div>
        </div>

        {/* Expand / collapse notes */}
        {model.notes && (
          <button
            onClick={() => setExpanded(e => !e)}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors mb-3"
          >
            <Info className="h-3 w-3" />
            {expanded ? 'Hide' : 'Show'} notes
            {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          </button>
        )}
        {expanded && model.notes && (
          <p className="text-xs text-muted-foreground bg-muted/40 rounded p-2 mb-3 leading-relaxed">
            {model.notes}
          </p>
        )}

        {/* Action buttons */}
        <div className="flex gap-2">
          {!model.is_active && !isUnavailable && (
            <button
              disabled={switching}
              onClick={() => onSwitch(task, modelId, model)}
              className="flex-1 py-2 text-xs font-bold rounded-lg bg-primary/10 text-primary border border-primary/30 hover:bg-primary/20 transition-colors disabled:opacity-50"
            >
              USE THIS MODEL
            </button>
          )}

          {model.is_active && (
            <div className="flex-1 py-2 text-xs font-bold rounded-lg bg-green-500/10 text-green-600 border border-green-500/30 text-center">
              ✓ CURRENTLY ACTIVE
            </div>
          )}

          {model.is_previous && !model.is_active && (
            <button
              disabled={switching}
              onClick={() => onRollback(task)}
              title="Rollback to this model"
              className="px-3 py-2 text-xs font-medium rounded-lg border hover:bg-muted/50 transition-colors flex items-center gap-1 disabled:opacity-50"
            >
              <RotateCcw className="h-3 w-3" />
              ROLLBACK
            </button>
          )}
        </div>

        {/* Active model config panel */}
        {model.is_active && (
          <div className="mt-4 pt-4 border-t space-y-3">
            <div className="flex justify-between items-center text-xs font-medium">
              <span className="text-muted-foreground">Confidence Threshold</span>
              <span>{model.confidence_threshold.toFixed(2)}</span>
            </div>
            
            <input 
              type="range" 
              min="0.10" 
              max="0.95" 
              step="0.01"
              value={model.confidence_threshold}
              onChange={(e) => onSwitch(task, modelId, { ...model, confidence_threshold: parseFloat(e.target.value) }, true)}
              className="w-full h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
            />
            
            <div className="text-[10px] text-muted-foreground bg-muted/20 p-2 rounded leading-tight">
              Only affects new video processing. Does not alter historical results.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Task Section ─────────────────────────────────────────────────────────────

const TASK_META: Record<string, { label: string; description: string; color: string }> = {
  POTHOLE:     { label: 'Pothole Detection', description: 'Bounding-box detection of road potholes', color: 'text-red-500' },
  WATERLOGGING:{ label: 'Waterlogging / Road-Water Segmentation', description: 'Segmentation of road surface waterlogging', color: 'text-blue-500' },
  OBJECT:      { label: 'Vehicle / Person Detection', description: 'COCO object detector — vehicles, persons. Traffic density is derived from this.', color: 'text-purple-500' },
  HELMET:      { label: 'Helmet / No-Helmet Detection', description: 'Rider safety compliance detection', color: 'text-yellow-500' },
};

// ─── Main Component ───────────────────────────────────────────────────────────

export function ModelRegistry() {
  const [registry, setRegistry] = useState<RegistryResponse>({});
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);
  const [switching, setSwitching] = useState(false);

  // Confirm modal state
  const [modal, setModal] = useState<{
    open: boolean;
    task: string;
    modelId: string;
    model: ModelEntry | null;
    currentName: string;
    isConfidenceEdit: boolean;
  }>({ open: false, task: '', modelId: '', model: null, currentName: '', isConfidenceEdit: false });

  const fetchRegistry = useCallback(async () => {
    try {
      setError(null);
      const res = await fetchRaw('/api/ai/models');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setRegistry(data);
    } catch (e) {
      setError('Failed to load model registry. Is the backend running?');
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchRegistry(); }, [fetchRegistry]);

  // Initiate model switch — open confirm modal
  const handleSwitchRequest = (task: string, modelId: string, model: ModelEntry, isConfidenceEdit = false) => {
    if (isConfidenceEdit) {
      // Local optimistic update for the slider (don't show modal immediately for sliding)
      setRegistry(prev => {
        const next = { ...prev };
        if (next[task] && next[task][modelId]) {
          next[task][modelId] = model;
        }
        return next;
      });
      return;
    }
    
    const taskModels = registry[task] || {};
    const activeEntry = Object.values(taskModels).find(m => m.is_active);
    const currentName = activeEntry?.display_name ?? 'Unknown';
    setModal({ open: true, task, modelId, model, currentName, isConfidenceEdit: false });
  };

  const handleSaveConfidence = async (task: string, modelId: string, conf: number) => {
    setSwitching(true);
    try {
      const res = await fetchRaw('/api/ai/models/confidence', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task, model_id: modelId, confidence_threshold: conf }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Update failed');
      }
      await fetchRegistry();
    } catch (e: any) {
      alert(`Failed to update confidence: ${e.message}`);
    } finally {
      setSwitching(false);
    }
  };

  // Confirm model switch
  const handleSwitchConfirm = async () => {
    if (!modal.model) return;
    setSwitching(true);
    try {
      const res = await fetchRaw('/api/ai/models/active', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task: modal.task, model_id: modal.modelId }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Switch failed');
      }
      setModal(m => ({ ...m, open: false }));
      await fetchRegistry();
    } catch (e: any) {
      alert(`Failed to switch model: ${e.message}`);
    } finally {
      setSwitching(false);
    }
  };

  // Rollback
  const handleRollback = async (task: string) => {
    const confirmed = window.confirm(
      `Rollback ${task} model to its previous selection?\n\nThis only affects new video processing — historical results are preserved.`
    );
    if (!confirmed) return;
    setSwitching(true);
    try {
      const res = await fetchRaw(`/api/ai/models/rollback/${task}`, {
        method: 'POST',
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Rollback failed');
      }
      await fetchRegistry();
    } catch (e: any) {
      alert(`Rollback failed: ${e.message}`);
    } finally {
      setSwitching(false);
    }
  };

  if (loading) {
    return (
      <div className="p-8 space-y-3">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-16 rounded-xl bg-muted/40 animate-pulse" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="flex items-center gap-3 p-4 rounded-xl border border-red-500/30 bg-red-500/10 text-red-600">
          <XCircle className="h-5 w-5 flex-shrink-0" />
          <div>
            <div className="font-bold text-sm">Registry Unavailable</div>
            <div className="text-xs mt-0.5">{error}</div>
          </div>
          <button
            onClick={fetchRegistry}
            className="ml-auto px-3 py-1 text-xs border border-red-500/30 rounded-lg hover:bg-red-500/20 transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <>
      {/* Confirm modal */}
      <ConfirmModal
        open={modal.open}
        title={`SWITCH ${modal.task} MODEL?`}
        currentName={modal.currentName}
        newName={modal.model?.display_name ?? ''}
        onCancel={() => setModal(m => ({ ...m, open: false }))}
        onConfirm={handleSwitchConfirm}
        loading={switching}
      />

      <div className="space-y-8">
        {/* Registry immutability notice */}
        <div className="flex items-start gap-3 p-4 rounded-xl border border-blue-500/20 bg-blue-500/5 text-sm">
          <Database className="h-4 w-4 text-blue-500 flex-shrink-0 mt-0.5" />
          <div className="text-muted-foreground text-xs leading-relaxed">
            <strong className="text-foreground">Historical Result Immutability:</strong> Switching
            the active model only affects <em>new</em> video processing runs. All existing results,
            incidents, journeys, and evidence are permanently tied to the model that originally
            processed them and will never be changed.
          </div>
        </div>

        {/* Task sections */}
        {Object.entries(registry).map(([task, taskModels]) => {
          const meta = TASK_META[task];
          const modelEntries = Object.entries(taskModels);

          return (
            <div key={task} className="space-y-4">
              {/* Task header */}
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className={`text-xs font-bold px-2 py-0.5 rounded border ${
                    task === 'POTHOLE'      ? 'text-red-500 border-red-500/30 bg-red-500/10' :
                    task === 'WATERLOGGING' ? 'text-blue-500 border-blue-500/30 bg-blue-500/10' :
                    task === 'OBJECT'       ? 'text-purple-500 border-purple-500/30 bg-purple-500/10' :
                    'text-yellow-500 border-yellow-500/30 bg-yellow-500/10'
                  }`}>
                    {task}
                  </div>
                  <div>
                    <div className="font-bold text-sm">{meta?.label ?? task}</div>
                    {meta?.description && (
                      <div className="text-xs text-muted-foreground">{meta.description}</div>
                    )}
                  </div>
                </div>
                {/* Active model save button */}
                {Object.values(taskModels).find(m => m.is_active) && (
                  <div className="flex gap-2">
                    <button
                      disabled={switching}
                      onClick={() => fetchRegistry()}
                      className="px-3 py-1.5 text-xs font-medium rounded border hover:bg-muted/50 transition-colors"
                    >
                      Reset UI
                    </button>
                    <button
                      disabled={switching}
                      onClick={() => {
                        const activeM = Object.values(taskModels).find(m => m.is_active)!;
                        handleSaveConfidence(task, activeM.model_id, activeM.confidence_threshold);
                      }}
                      className="px-3 py-1.5 text-xs font-bold rounded bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
                    >
                      {switching ? 'Saving...' : 'Save Config'}
                    </button>
                  </div>
                )}
              </div>

              {/* Model cards grid */}
              <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
                {modelEntries.map(([modelId, model]) => (
                  <ModelCard
                    key={modelId}
                    modelId={modelId}
                    model={model}
                    task={task}
                    onSwitch={handleSwitchRequest}
                    onRollback={handleRollback}
                    switching={switching}
                  />
                ))}
              </div>
            </div>
          );
        })}

        {/* Compatibility matrix */}
        <div className="border rounded-xl overflow-hidden">
          <div className="bg-muted/30 border-b px-4 py-3 flex items-center gap-2">
            <Database className="h-4 w-4 text-muted-foreground" />
            <h3 className="font-bold text-sm">Model-Frontend Compatibility Matrix</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b bg-muted/20">
                  <th className="px-4 py-2 text-left font-medium text-muted-foreground">Task</th>
                  <th className="px-4 py-2 text-center font-medium text-muted-foreground">Video Analysis</th>
                  <th className="px-4 py-2 text-center font-medium text-muted-foreground">Map</th>
                  <th className="px-4 py-2 text-center font-medium text-muted-foreground">Journey Replay</th>
                  <th className="px-4 py-2 text-center font-medium text-muted-foreground">Fleet Replay</th>
                  <th className="px-4 py-2 text-center font-medium text-muted-foreground">Evidence</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {[
                  ['Pothole',      '✓','✓','✓','✓','✓'],
                  ['Waterlogging', '✓','✓','✓','✓','✓'],
                  ['Vehicles',     '✓','✓','✓','✓','✓'],
                  ['Persons',      '✓','✓','✓','✓','✓'],
                  ['Helmet',       '—','—','—','—','—'],
                ].map(([label, ...checks]) => (
                  <tr key={label} className="hover:bg-muted/20">
                    <td className="px-4 py-2 font-medium">{label}</td>
                    {checks.map((c, i) => (
                      <td key={i} className={`px-4 py-2 text-center font-bold ${c === '✓' ? 'text-green-500' : 'text-muted-foreground'}`}>
                        {c}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="px-4 py-2 text-xs text-muted-foreground bg-muted/10 border-t">
            ✓ = verified via canonical event pipeline &nbsp;|&nbsp; — = model file unavailable (best_roadx.pt absent)
          </div>
        </div>
      </div>
    </>
  );
}
