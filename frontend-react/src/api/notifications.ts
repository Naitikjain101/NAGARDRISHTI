import { fetchApi } from './client';

export interface Notification {
  id: string;
  type: string;
  title: string;
  message: string;
  incident_id?: string;
  read: boolean;
  created_at: string;
}

export const notificationsApi = {
  getRecent: async (): Promise<Notification[]> => {
    return fetchApi<Notification[]>('/notifications/');
  },
  markRead: async (id: string): Promise<any> => {
    return fetchApi(`/notifications/${id}/read`, {
      method: 'PATCH'
    });
  }
};
