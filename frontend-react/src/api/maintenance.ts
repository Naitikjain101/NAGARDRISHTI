import { fetchApi } from './client';

export interface MaintenanceTask {
  id: string;
  incident_id?: string;
  road_segment_id?: string;
  title: string;
  description?: string;
  severity: 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL';
  status: 'OPEN' | 'ASSIGNED' | 'IN_PROGRESS' | 'RESOLVED' | 'DISMISSED';
  assigned_to?: string;
  resolution_notes?: string;
  resolved_at?: string;
  created_at: string;
  updated_at: string;
}

export const maintenanceApi = {
  getTasks: async (): Promise<MaintenanceTask[]> => {
    return fetchApi<MaintenanceTask[]>('/maintenance/');
  },
  updateTask: async (taskId: string, status: string, notes?: string): Promise<any> => {
    return fetchApi(`/maintenance/${taskId}`, {
      method: 'PATCH',
      body: JSON.stringify({ status, resolution_notes: notes })
    });
  }
};
