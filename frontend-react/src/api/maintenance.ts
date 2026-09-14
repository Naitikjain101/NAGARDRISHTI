import { fetchApi } from './client';

export interface MaintenanceAction {
  id: string;
  incident_id: string;
  action_type: string;
  status: 'UNASSIGNED' | 'ASSIGNED' | 'IN_PROGRESS' | 'RESOLVED' | 'REJECTED';
  assigned_team?: string;
  assigned_department?: string;
  resolution_note?: string;
  created_at: string;
  updated_at: string;
}

export const maintenanceApi = {
  getTasks: async (): Promise<MaintenanceAction[]> => {
    return fetchApi<MaintenanceAction[]>('/actions');
  },
  updateTask: async (actionId: string, status: string, notes?: string): Promise<any> => {
    return fetchApi(`/actions/${actionId}`, {
      method: 'PATCH',
      body: JSON.stringify({ status, resolution_note: notes })
    });
  }
};
