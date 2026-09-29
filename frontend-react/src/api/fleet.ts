import { fetchApi } from './client';

export interface BusTelemetry {
  id: string;
  bus_id: string;
  timestamp: string;
  latitude: number;
  longitude: number;
  speed: number;
  heading: number;
}

export interface Journey {
  id: string;
  bus_id: string;
  route_id: string;
  route_name: string;
  video_filename: string;
  duration_seconds: number;
  status: string;
  metadata?: {
    bus_name?: string;
    video_id?: string;
    original_filename?: string;
    start_location?: string;
    destination?: string;
  };
  created_at: string;
}

export interface Bus {
  id: string;
  fleet_number: string;
  route_id: string;
  status: string;
  camera_status: string;
  ai_status: string;
  latest_telemetry?: BusTelemetry;
  journeys?: Journey[];
}

export const fleetApi = {
  getBuses: async (): Promise<Bus[]> => {
    return fetchApi<Bus[]>('/buses/');
  }
};
