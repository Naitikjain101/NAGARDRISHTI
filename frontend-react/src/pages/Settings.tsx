import { useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Save, Settings2, Cpu, FlaskConical, ShieldCheck } from 'lucide-react';
import { Tabs, useTabs } from '@/components/ui/Tabs';
import { PageHeader } from '@/components/ui/PageHeader';
import { Button } from '@/components/ui/Button';
import { AIControlCenter } from './AIControlCenter';
import PotholeLab from './PotholeLab';

const TABS = [
  { id: 'general',  label: 'General',          icon: Settings2 },
  { id: 'ai',       label: 'AI Control Center', icon: Cpu },
  { id: 'models',   label: 'Model Lab',         icon: FlaskConical },
  { id: 'admin',    label: 'Administration',    icon: ShieldCheck },
];

function GeneralSettings() {
  return (
    <div className="max-w-2xl space-y-8">
      <section className="space-y-4">
        <div className="border-b border-border pb-2">
          <h3 className="text-sm font-semibold text-foreground">AI Inference Engine</h3>
          <p className="text-xs text-muted-foreground mt-0.5">Configure model confidence thresholds and compute device.</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-foreground">Global Confidence Threshold (%)</label>
            <input
              type="number"
              defaultValue={60}
              className="w-full h-9 bg-card border border-input rounded px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
            <p className="text-xs text-muted-foreground">Minimum confidence score to record an incident.</p>
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-foreground">Inference Device Priority</label>
            <select className="w-full h-9 bg-card border border-input rounded px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring">
              <option value="auto">Auto (MPS/CUDA fallback)</option>
              <option value="cpu">CPU Only</option>
              <option value="mps">Apple MPS</option>
              <option value="cuda">NVIDIA CUDA</option>
            </select>
            <p className="text-xs text-muted-foreground">Hardware acceleration for YOLOv8 models.</p>
          </div>
        </div>
      </section>

      <section className="space-y-4">
        <div className="border-b border-border pb-2">
          <h3 className="text-sm font-semibold text-foreground">Database & Storage</h3>
        </div>
        <div className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-foreground">Supabase URL</label>
            <input
              type="text"
              value={import.meta.env.VITE_SUPABASE_URL || 'Configured via environment variable'}
              disabled
              className="w-full h-9 bg-secondary/50 border border-input rounded px-3 text-sm text-muted-foreground cursor-not-allowed"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-foreground">Data Retention Policy</label>
            <select className="w-full h-9 bg-card border border-input rounded px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring">
              <option value="30">30 Days</option>
              <option value="90">90 Days</option>
              <option value="365">1 Year</option>
              <option value="forever">Indefinitely</option>
            </select>
          </div>
        </div>
      </section>

      <section className="space-y-4">
        <div className="border-b border-border pb-2">
          <h3 className="text-sm font-semibold text-foreground">Alerts & Notifications</h3>
        </div>
        <div className="space-y-3">
          <label className="flex items-center gap-3 cursor-pointer">
            <input type="checkbox" defaultChecked className="w-4 h-4 accent-primary" />
            <span className="text-sm">Push notifications for CRITICAL severity incidents</span>
          </label>
          <label className="flex items-center gap-3 cursor-pointer">
            <input type="checkbox" defaultChecked className="w-4 h-4 accent-primary" />
            <span className="text-sm">Alert when AI Inference Engine goes offline</span>
          </label>
        </div>
      </section>

      <div className="flex justify-end pt-2">
        <Button icon={Save} variant="primary">
          Save Configuration
        </Button>
      </div>
    </div>
  );
}

function AdminSettings() {
  return (
    <div className="max-w-2xl space-y-6">
      <section className="space-y-4">
        <div className="border-b border-border pb-2">
          <h3 className="text-sm font-semibold text-foreground">Platform Information</h3>
        </div>
        <div className="bg-card border border-border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <tbody className="divide-y divide-border">
              {[
                ['Platform', 'NagarDrishti v1.0'],
                ['Organisation', 'Municipal Corporation'],
                ['Environment', 'Development'],
                ['Backend', 'FastAPI + Supabase'],
                ['AI Engine', 'YOLOv8 Unified Pipeline'],
              ].map(([key, val]) => (
                <tr key={key}>
                  <td className="px-4 py-3 text-muted-foreground font-medium w-40">{key}</td>
                  <td className="px-4 py-3 text-foreground font-mono text-xs">{val}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

export function Settings() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialTab = searchParams.get('tab') || 'general';
  const { activeTab, setActiveTab } = useTabs(initialTab);

  // Keep URL in sync when tab changes
  const handleTabChange = (id: string) => {
    setActiveTab(id);
    setSearchParams(id === 'general' ? {} : { tab: id });
  };

  // Sync if URL param changes externally (e.g., redirect from /ai/control)
  useEffect(() => {
    const tab = searchParams.get('tab');
    if (tab && tab !== activeTab) setActiveTab(tab);
  }, [searchParams]);

  return (
    <div className="page-content">
      <PageHeader
        title="Settings"
        description="Configure platform behaviour, AI engine, and administration."
        icon={Settings2}
      />

      <Tabs tabs={TABS} activeTab={activeTab} onChange={handleTabChange} />

      <div className="flex-1 min-h-0">
        {activeTab === 'general' && <GeneralSettings />}
        {activeTab === 'ai'      && <AIControlCenter />}
        {activeTab === 'models'  && <PotholeLab />}
        {activeTab === 'admin'   && <AdminSettings />}
      </div>
    </div>
  );
}
