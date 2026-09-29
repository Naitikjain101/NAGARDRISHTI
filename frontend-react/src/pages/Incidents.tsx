import { useState } from 'react';
import { useRealtimeIncidents } from '@/hooks/useRealtimeIncidents';
import { DataTable } from '@/components/incidents/DataTable';
import { IncidentDrawer } from '@/components/incidents/IncidentDrawer';
import type { Incident } from '@/api/incidents';

import { Download, AlertTriangle } from 'lucide-react';
import { Skeleton } from '@/components/ui/Skeleton';
import { PageHeader } from '@/components/ui/PageHeader';
import { Button } from '@/components/ui/Button';
import { SearchInput } from '@/components/ui/SearchInput';
import { Select } from '@/components/ui/Select';

export function Incidents() {
  const { data, isLoading } = useRealtimeIncidents();
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);
  const [search, setSearch] = useState('');
  const [severityFilter, setSeverityFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  const allIncidents = data?.incidents || [];

  // Apply filters
  const incidents = allIncidents.filter((inc: any) => {
    const type = inc.incident_type || inc.type || '';
    const matchesSearch = !search ||
      inc.id?.toLowerCase().includes(search.toLowerCase()) ||
      type.toLowerCase().includes(search.toLowerCase());
    const matchesSeverity = !severityFilter || inc.severity?.toUpperCase() === severityFilter.toUpperCase();
    const matchesType = !typeFilter || type.toLowerCase() === typeFilter.toLowerCase();
    const matchesStatus = !statusFilter || inc.status?.toUpperCase() === statusFilter.toUpperCase();
    return matchesSearch && matchesSeverity && matchesType && matchesStatus;
  });

  return (
    <div className="page-content">
      <PageHeader
        title="Incident Center"
        icon={AlertTriangle}
        description="Manage and investigate urban infrastructure alerts detected across the network."
        actions={
          <Button variant="outline" size="sm" icon={Download}>
            Export CSV
          </Button>
        }
      />

      {/* Metrics Panel */}
      <div className="grid grid-cols-4 gap-4 mb-2">
        <div className="bg-card border border-border rounded-xl p-4 flex items-center justify-between">
          <div>
            <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Active Incidents</p>
            <p className="text-3xl font-black mt-1">{allIncidents.length}</p>
          </div>
          <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
            <AlertTriangle className="w-5 h-5 text-primary" />
          </div>
        </div>
        <div className="bg-card border border-border rounded-xl p-4 flex items-center justify-between">
          <div>
            <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Open</p>
            <p className="text-3xl font-black mt-1 text-orange-500">
              {allIncidents.filter((i: any) => i.status === 'OPEN').length}
            </p>
          </div>
          <div className="w-10 h-10 rounded-full bg-orange-500/10 flex items-center justify-center">
            <AlertTriangle className="w-5 h-5 text-orange-500" />
          </div>
        </div>
        <div className="bg-card border border-border rounded-xl p-4 flex items-center justify-between">
          <div>
            <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">In Progress</p>
            <p className="text-3xl font-black mt-1 text-blue-500">
              {allIncidents.filter((i: any) => i.status === 'IN_PROGRESS').length}
            </p>
          </div>
          <div className="w-10 h-10 rounded-full bg-blue-500/10 flex items-center justify-center">
            <AlertTriangle className="w-5 h-5 text-blue-500" />
          </div>
        </div>
        <div className="bg-card border border-border rounded-xl p-4 flex items-center justify-between">
          <div>
            <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Resolved</p>
            <p className="text-3xl font-black mt-1 text-emerald-500">
              {allIncidents.filter((i: any) => i.status === 'RESOLVED').length}
            </p>
          </div>
          <div className="w-10 h-10 rounded-full bg-emerald-500/10 flex items-center justify-center">
            <AlertTriangle className="w-5 h-5 text-emerald-500" />
          </div>
        </div>
      </div>

      {/* Filter bar */}
      <div className="bg-card border border-border rounded-lg p-3 flex flex-wrap items-center gap-3">
        <SearchInput
          value={search}
          onChange={setSearch}
          placeholder="Search by ID, location, or type..."
          className="min-w-[220px] flex-1"
          id="incidents-search"
        />

        <Select
          value={severityFilter}
          onChange={e => setSeverityFilter(e.target.value)}
          aria-label="Filter by severity"
        >
          <option value="">All Severities</option>
          <option value="CRITICAL">Critical</option>
          <option value="HIGH">High</option>
          <option value="MODERATE">Moderate</option>
          <option value="LOW">Low</option>
        </Select>

        <Select
          value={typeFilter}
          onChange={e => setTypeFilter(e.target.value)}
          aria-label="Filter by type"
        >
          <option value="">All Types</option>
          <option value="waterlogging">Waterlogging</option>
          <option value="pothole">Pothole</option>
        </Select>

        <Select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
          aria-label="Filter by status"
        >
          <option value="">All Statuses</option>
          <option value="OPEN">Open</option>
          <option value="ASSIGNED">Assigned</option>
          <option value="IN_PROGRESS">In Progress</option>
          <option value="RESOLVED">Resolved</option>
        </Select>

        {(search || severityFilter || typeFilter || statusFilter) && (
          <button
            onClick={() => { setSearch(''); setSeverityFilter(''); setTypeFilter(''); setStatusFilter(''); }}
            className="text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Count */}
      {!isLoading && (
        <p className="text-xs text-muted-foreground -mt-2">
          Showing <span className="font-semibold text-foreground">{incidents.length}</span> of{' '}
          <span className="font-semibold text-foreground">{allIncidents.length}</span> incidents
        </p>
      )}

      {/* Table */}
      <div className="flex-1 min-h-0">
        {isLoading ? (
          <div className="space-y-2">
            {[1, 2, 3, 4, 5, 6].map(i => (
              <Skeleton key={i} className="h-12 w-full rounded-lg" />
            ))}
          </div>
        ) : allIncidents.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-12 bg-card border border-border rounded-lg text-center h-[400px]">
            <AlertTriangle className="h-10 w-10 text-muted-foreground mb-4 opacity-50" />
            <p className="text-sm font-bold text-muted-foreground uppercase tracking-widest">
              No incidents recorded
            </p>
          </div>
        ) : incidents.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-12 bg-card border border-border rounded-lg text-center h-[400px]">
            <AlertTriangle className="h-10 w-10 text-muted-foreground mb-4 opacity-50" />
            <p className="text-sm font-bold text-muted-foreground uppercase tracking-widest">
              No active incidents matching filters
            </p>
          </div>
        ) : (
          <DataTable
            incidents={incidents}
            onRowClick={setSelectedIncident}
          />
        )}
      </div>

      <IncidentDrawer
        incident={selectedIncident as any}
        onClose={() => setSelectedIncident(null)}
      />
    </div>
  );
}
