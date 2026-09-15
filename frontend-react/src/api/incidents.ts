import { fetchApi } from './client';

export interface Incident {
  id: string;
  video_id: string;
  type: string;
  class_name: string;
  canonical_capability: string;
  confidence: number;
  composite_score: number | null;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  timestamp: number;
  frame: number;
  occurrence_count: number;
  bbox: number[] | null;
  gps_available: boolean;
  latitude: number | null;
  longitude: number | null;
  gps_accuracy_meters: number | null;
  road_segment_id: string | null;
  status: 'active' | 'confirmed' | 'suppressed' | 'rejected';
  suppression_reason: string | null;
  track_id: number | null;
  created_at: string;
  metadata?: any;
  source_mission_id?: string;
  route_name?: string;
}

export interface IncidentsResponse {
  incidents: Incident[];
  total: number;
  page_size: number;
  offset: number;
  gps_note: string;
}

export const incidentsApi = {
  getIncidents: async (params?: {
    type?: string;
    status?: string;
    severity?: string;
    limit?: number;
    offset?: number;
  }): Promise<IncidentsResponse> => {
    const query = new URLSearchParams();
    if (params?.type) query.append('incident_type', params.type);
    if (params?.status) query.append('status', params.status);
    if (params?.severity) query.append('severity', params.severity);
    if (params?.limit) query.append('limit', params.limit.toString());
    if (params?.offset) query.append('offset', params.offset.toString());
    
    const queryString = query.toString() ? `?${query.toString()}` : '';
    return fetchApi<IncidentsResponse>(`/incidents/${queryString}`);
  },

  getIncidentById: async (id: string): Promise<Incident> => {
    return fetchApi<Incident>(`/incidents/${id}`);
  }
};
