import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Settings2, Cpu, FlaskConical, ShieldCheck, Database, LayoutDashboard, User, LogOut, Trash2 } from 'lucide-react';
import { Tabs, useTabs } from '@/components/ui/Tabs';
import { PageHeader } from '@/components/ui/PageHeader';
import { AIControlCenter } from './AIControlCenter';
import PotholeLab from './PotholeLab';
import { useQuery } from '@tanstack/react-query';
import { aiApi } from '@/api/ai';
import { supabase } from '@/lib/supabase';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { useToast } from '@/components/ui/Toast';
import { fetchRaw } from '../api/client';

const TABS = [
  { id: 'general',  label: 'General',          icon: Settings2 },
  { id: 'ai',       label: 'AI Control Center', icon: Cpu },
  { id: 'models',   label: 'Model Lab',         icon: FlaskConical },
  { id: 'admin',    label: 'Administration',    icon: ShieldCheck },
];

function GeneralSettings() {
  const { data: systemStatus, isLoading } = useQuery({
    queryKey: ['systemStatus'],
    queryFn: aiApi.getSystemStatus,
    refetchInterval: 10000,
  });

  return (
    <div className="max-w-3xl space-y-6">
      <section className="space-y-4">
        <div className="border-b border-border pb-2">
          <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
            <LayoutDashboard className="h-4 w-4" /> Application Information
          </h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-foreground">Application Name</label>
            <div className="w-full h-9 bg-secondary/50 border border-input rounded px-3 text-sm text-foreground flex items-center">
              NagarDrishti
            </div>
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-foreground">Environment</label>
            <div className="w-full h-9 bg-secondary/50 border border-input rounded px-3 text-sm text-foreground flex items-center capitalize">
              {import.meta.env.MODE || 'development'}
            </div>
          </div>
        </div>
      </section>

      <section className="space-y-4">
        <div className="border-b border-border pb-2">
          <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
            <Database className="h-4 w-4" /> Database & Storage
          </h3>
        </div>
        <div className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-foreground">Backend API</label>
            <div className="w-full h-9 bg-secondary/50 border border-input rounded px-3 text-sm text-muted-foreground flex items-center">
              Configured via environment — secured
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-foreground">Database Status</label>
              <div className={`w-full h-9 border rounded px-3 text-sm flex items-center font-bold ${
                isLoading ? 'bg-secondary/50 border-input text-muted-foreground' :
                systemStatus?.status === 'ok' ? 'bg-green-500/10 border-green-500/30 text-green-600' : 'bg-red-500/10 border-red-500/30 text-red-600'
              }`}>
                {isLoading ? 'Checking...' : systemStatus?.status === 'ok' ? 'CONNECTED' : 'UNAVAILABLE'}
              </div>
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-foreground">Data Refresh Behavior</label>
              <div className="w-full h-9 bg-secondary/50 border border-input rounded px-3 text-sm text-muted-foreground flex items-center italic">
                Read only — auto-polling active
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

function AdminSettings() {
  const [session, setSession] = useState<any>(null);
  const [loadingAuth, setLoadingAuth] = useState(true);
  const [resetDialogOpen, setResetDialogOpen] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const toast = useToast();

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      setLoadingAuth(false);
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
    });

    return () => subscription.unsubscribe();
  }, []);

  const handleSignOut = async () => {
    await supabase.auth.signOut();
    toast.success('Signed Out', 'You have been successfully signed out.');
  };

  const handleResetData = async () => {
    setIsResetting(true);
    try {
      const res = await fetchRaw('/api/missions/reset', { method: 'POST' });
      if (!res.ok) throw new Error('Failed to reset operations data');
      toast.success('Operations Reset', 'All demo incidents and fleet journeys have been reset.');
      setResetDialogOpen(false);
    } catch (err: any) {
      toast.error('Reset Failed', err.message);
    } finally {
      setIsResetting(false);
    }
  };

  return (
    <div className="max-w-3xl space-y-6">
      <section className="space-y-4">
        <div className="border-b border-border pb-2">
          <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
            <User className="h-4 w-4" /> Current Administrator
          </h3>
        </div>
        
        {loadingAuth ? (
          <div className="h-24 bg-card border border-border rounded-lg animate-pulse" />
        ) : session ? (
          <div className="bg-card border border-border rounded-lg p-5 shadow-sm space-y-4">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-muted-foreground block text-xs uppercase tracking-wider font-bold mb-1">Email</span>
                <span className="font-medium">{session.user.email}</span>
              </div>
              <div>
                <span className="text-muted-foreground block text-xs uppercase tracking-wider font-bold mb-1">Role</span>
                <span className="font-medium text-primary">Administrator</span>
              </div>
            </div>
            <div className="pt-4 border-t border-border flex justify-end">
              <button
                onClick={handleSignOut}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-red-600 bg-red-500/10 hover:bg-red-500/20 rounded-md transition-colors"
              >
                <LogOut className="h-4 w-4" /> Sign Out
              </button>
            </div>
          </div>
        ) : (
          <div className="bg-card border border-border rounded-lg p-6 flex flex-col items-center justify-center text-center shadow-sm">
            <User className="h-8 w-8 text-muted-foreground mb-2 opacity-50" />
            <p className="font-medium text-foreground">Not authenticated</p>
            <p className="text-xs text-muted-foreground mt-1">
              You are currently viewing the system as a guest.
            </p>
          </div>
        )}
      </section>

      <section className="space-y-4">
        <div className="border-b border-border pb-2">
          <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
            <ShieldCheck className="h-4 w-4" /> System Administration
          </h3>
        </div>
        
        <div className="bg-card border border-red-500/20 rounded-lg p-5 shadow-sm space-y-4">
          <div>
            <h4 className="font-bold text-red-600 mb-1">Reset Operations Data</h4>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Resets all demonstration data. This will securely clear generated incidents, tasks, and reset fleet monitoring missions back to READY status. This operation does not truncate core master data.
            </p>
          </div>
          <button
            onClick={() => setResetDialogOpen(true)}
            className="flex items-center gap-2 px-4 py-2 text-sm font-bold text-white bg-red-600 hover:bg-red-700 rounded-md transition-colors"
          >
            <Trash2 className="h-4 w-4" /> Reset Operations
          </button>
        </div>
      </section>

      <ConfirmDialog
        isOpen={resetDialogOpen}
        title="Reset Operations Data?"
        description="Are you sure you want to reset all operational data? This will clear all recorded incidents, reset active journeys, and cancel any pending maintenance tasks. This action cannot be undone."
        confirmLabel="Yes, Reset Operations"
        onConfirm={handleResetData}
        onClose={() => setResetDialogOpen(false)}
        loading={isResetting}
        variant="destructive"
      />
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
    <div className="page-content flex flex-col h-[calc(100vh-2rem)] min-h-0">
      <PageHeader
        title="Settings & Administration"
        description="Configure platform behaviour, AI engine, and administrative access."
        icon={Settings2}
      />

      <Tabs tabs={TABS} activeTab={activeTab} onChange={handleTabChange} />

      <div className="flex-1 min-h-0 pt-2 flex flex-col overflow-y-auto custom-scrollbar">
        {activeTab === 'general' && <GeneralSettings />}
        {activeTab === 'ai'      && <AIControlCenter />}
        {activeTab === 'models'  && <PotholeLab />}
        {activeTab === 'admin'   && <AdminSettings />}
      </div>
    </div>
  );
}
