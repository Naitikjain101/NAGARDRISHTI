import { fetchApi } from './client';

export interface DeviceInfo {
  device: string;
  has_mps: boolean;
  has_cuda: boolean;
}

export interface SystemStatus {
  status: string;
  version: string;
}

export const aiApi = {
  getDevice: async (): Promise<DeviceInfo> => {
    return fetchApi<DeviceInfo>('/ai/device');
  },
  getSystemStatus: async (): Promise<SystemStatus> => {
    return fetchApi<SystemStatus>('/system/status');
  }
};
