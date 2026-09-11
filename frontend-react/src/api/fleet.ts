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

export interface Bus {
  id: string;
  fleet_number: string;
  route_id: string;
  status: string;
  camera_status: string;
  ai_status: string;
  latest_telemetry?: BusTelemetry;
}

export const fleetApi = {
  getBuses: async (): Promise<Bus[]> => {
    return fetchApi<Bus[]>('/buses/');
  }
};
