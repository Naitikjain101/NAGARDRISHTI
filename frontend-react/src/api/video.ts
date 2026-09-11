import { fetchApi } from './client';

// Canonical status enum — must match backend ProcessingStatus exactly
export type JobStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface VideoUploadResponse {
  video_id: string;
  filename: string;
  metadata: VideoMetadata;
}

export interface VideoMetadata {
  video_id: string;
  filename: string;
  width: number;
  height: number;
  fps: number;
  frame_count: number;
  duration_seconds: number;
  codec?: string | null;
  file_size_bytes?: number | null;
}

export interface ProcessingStartResponse {
  message: string;
  job_id: string;
  video_id: string;
  status: JobStatus;
}

export interface ProcessingStatusResponse {
  video_id: string;
  status: JobStatus;
  progress_frames: number;
  total_frames: number;
  processing_fps: number | null;
  current_vehicles: number;
  current_potholes: number;
  current_helmets: number;
  current_no_helmets: number;
  error: string | null;
}

export interface JobStatusResponse {
  job_id: string;
  video_id: string;
  status: JobStatus;
  progress_frames: number;
  total_frames: number;
  processing_fps: number | null;
  error: string | null;
  created_at: string | null;
  completed_at: string | null;
}

export const videoApi = {
  uploadVideo: async (file: File): Promise<VideoUploadResponse> => {
    const formData = new FormData();
    // Field name must match FastAPI parameter: `file: UploadFile = File(...)`
    formData.append('file', file);

    // IMPORTANT: Do NOT set Content-Type header — the browser sets it with
    // the correct multipart/form-data boundary automatically.
    return fetchApi<VideoUploadResponse>('/video/upload', {
      method: 'POST',
      body: formData,
    });
  },

  startUnifiedProcessing: async (videoId: string): Promise<ProcessingStartResponse> => {
    return fetchApi<ProcessingStartResponse>(`/ai/unified/process/${videoId}`, {
      method: 'POST',
    });
  },

  /** Poll by video_id (original endpoint, still works) */
  getProcessingStatus: async (videoId: string): Promise<ProcessingStatusResponse> => {
    return fetchApi<ProcessingStatusResponse>(`/ai/unified/status/${videoId}`);
  },

  /** Poll by job_id (more precise, returned from startUnifiedProcessing) */
  getJobStatus: async (jobId: string): Promise<JobStatusResponse> => {
    return fetchApi<JobStatusResponse>(`/ai/unified/jobs/${jobId}/status`);
  },

  getResults: async (videoId: string): Promise<any> => {
    return fetchApi(`/ai/unified/results/${videoId}`);
  },

  /** Returns a URL for the video stream.
   *  In dev mode, bypasses the Vite proxy to avoid video buffering/seeking issues.
   *  In prod mode, uses the relative URL so Nginx/Caddy can route it. */
  getStreamUrl: (videoId: string): string => {
    if (import.meta.env.DEV) {
      return `http://localhost:8000/api/video/${videoId}/stream`;
    }
    return `/api/video/${videoId}/stream`;
  },
};
