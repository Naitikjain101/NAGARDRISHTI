import { Save } from 'lucide-react';

export function Settings() {
  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold">System Settings</h1>
        <p className="text-muted-foreground">Configure AI thresholds, API keys, and notification preferences.</p>
      </div>

      <div className="bg-card border border-border rounded-lg overflow-hidden">
        <div className="p-6 space-y-8">
          
          {/* AI Inference Section */}
          <section className="space-y-4">
            <h3 className="text-lg font-medium border-b border-border pb-2">AI Inference Engine</h3>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-sm font-medium">Global Confidence Threshold (%)</label>
                <input 
                  type="number" 
                  defaultValue={60} 
                  className="w-full bg-background border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                />
                <p className="text-xs text-muted-foreground">Minimum confidence score to record an incident.</p>
              </div>
              
              <div className="space-y-2">
                <label className="text-sm font-medium">Inference Device Priority</label>
                <select className="w-full bg-background border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary">
                  <option value="auto">Auto (MPS/CUDA fallback)</option>
                  <option value="cpu">CPU Only</option>
                  <option value="mps">Apple MPS</option>
                  <option value="cuda">NVIDIA CUDA</option>
                </select>
                <p className="text-xs text-muted-foreground">Hardware acceleration for YOLOv8 models.</p>
              </div>
            </div>
          </section>

          {/* Database Section */}
          <section className="space-y-4">
            <h3 className="text-lg font-medium border-b border-border pb-2">Database & Storage</h3>
            
            <div className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Supabase URL</label>
                <input 
                  type="text" 
                  value={import.meta.env.VITE_SUPABASE_URL || 'Configured via Environment Variables'}
                  disabled
                  className="w-full bg-secondary/50 border border-border rounded-md px-3 py-2 text-sm text-muted-foreground cursor-not-allowed"
                />
              </div>
              
              <div className="space-y-2">
                <label className="text-sm font-medium">Data Retention Policy</label>
                <select className="w-full bg-background border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary">
                  <option value="30">30 Days</option>
                  <option value="90">90 Days</option>
                  <option value="365">1 Year</option>
                  <option value="forever">Indefinitely</option>
                </select>
              </div>
            </div>
          </section>

          {/* Notifications Section */}
          <section className="space-y-4">
            <h3 className="text-lg font-medium border-b border-border pb-2">Alerts & Notifications</h3>
            
            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <input type="checkbox" id="crit" defaultChecked className="w-4 h-4 rounded border-border bg-background text-primary" />
                <label htmlFor="crit" className="text-sm">Push notifications for CRITICAL severity incidents</label>
              </div>
              <div className="flex items-center gap-3">
                <input type="checkbox" id="sys" defaultChecked className="w-4 h-4 rounded border-border bg-background text-primary" />
                <label htmlFor="sys" className="text-sm">Alert when AI Inference Engine goes offline</label>
              </div>
            </div>
          </section>

        </div>
        
        <div className="p-6 bg-secondary/30 border-t border-border flex justify-end">
          <button className="flex items-center gap-2 px-6 py-2 bg-primary text-primary-foreground rounded-md font-medium hover:bg-primary/90 transition-colors">
            <Save className="h-4 w-4" />
            Save Configuration
          </button>
        </div>
      </div>
    </div>
  );
}
