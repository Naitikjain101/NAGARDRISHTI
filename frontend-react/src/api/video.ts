import { fetchApi, buildUrl } from './client';
import { supabase } from '../lib/supabase';

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
   *  Falls back to a Supabase signed URL if Render backend is unavailable. */
  getStreamUrl: (videoId: string): string => {
    return buildUrl(`/video/${videoId}/stream`);
  },

  /**
   * Directly generates a signed URL from Supabase Storage, bypassing Render.
   * This is the primary method used on Vercel where Render may be slow/unavailable.
   */
  getSignedStreamUrl: async (videoId: string): Promise<string | null> => {
    // Try multiple path patterns since videoId might already include .mp4
    const cleanId = videoId.replace(/\.mp4$/i, '');
    const pathsToTry = [
      `uploads/${cleanId}.mp4`,
      `uploads/${videoId}`,        // videoId might already have extension
      `${cleanId}.mp4`,            // might be at bucket root
    ];

    for (const storagePath of pathsToTry) {
      try {
        const { data, error } = await supabase.storage
          .from('urban_watch_evidence')
          .createSignedUrl(storagePath, 3600);
        if (!error && data?.signedUrl) {
          console.log('[VideoAPI] Signed URL created for path:', storagePath);
          return data.signedUrl;
        }
        if (error) {
          console.warn('[VideoAPI] Signed URL failed for path:', storagePath, error.message);
        }
      } catch (e) {
        console.warn('[VideoAPI] Exception creating signed URL for:', storagePath, e);
      }
    }
    return null;
  },

  /**
   * Try getting a Supabase public URL (if bucket is public or has public policy).
   */
  getPublicUrl: (videoId: string): string | null => {
    const cleanId = videoId.replace(/\.mp4$/i, '');
    try {
      const { data } = supabase.storage
        .from('urban_watch_evidence')
        .getPublicUrl(`uploads/${cleanId}.mp4`);
      return data?.publicUrl || null;
    } catch {
      return null;
    }
  },

  /**
   * Smart URL resolver: tries multiple strategies to get a working video URL.
   * Priority:
   *   1. Supabase signed URL (works on Vercel, reliable for private buckets)
   *   2. Supabase public URL (works if bucket has public read policy)
   *   3. Backend stream endpoint (works locally / when Render is up)
   * 
   * Use this everywhere instead of getStreamUrl for production reliability.
   */
  getSmartStreamUrl: async (videoId: string): Promise<string> => {
    const cleanId = videoId.replace(/\.mp4$/i, '');
    console.log('[VideoAPI] Resolving stream URL for videoId:', videoId, '(clean:', cleanId, ')');

    // Strategy 1: Supabase signed URL (most reliable on Vercel)
    const pathsToTry = [
      `uploads/${cleanId}.mp4`,
      `uploads/${videoId}`,
      `${cleanId}.mp4`,
    ];

    for (const storagePath of pathsToTry) {
      try {
        const { data, error } = await supabase.storage
          .from('urban_watch_evidence')
          .createSignedUrl(storagePath, 3600);
        if (!error && data?.signedUrl) {
          console.log('[VideoAPI] ✅ Signed URL resolved via path:', storagePath);
          return data.signedUrl;
        }
        if (error) {
          console.warn('[VideoAPI] Signed URL attempt failed for:', storagePath, '-', error.message);
        }
      } catch (e) {
        console.warn('[VideoAPI] Exception for signed URL path:', storagePath, e);
      }
    }

    // Strategy 2: Supabase public URL (if bucket allows public reads)
    try {
      const { data } = supabase.storage
        .from('urban_watch_evidence')
        .getPublicUrl(`uploads/${cleanId}.mp4`);
      if (data?.publicUrl) {
        console.log('[VideoAPI] ⚠️ Falling back to public URL:', data.publicUrl);
        return data.publicUrl;
      }
    } catch (e) {
      console.warn('[VideoAPI] Public URL fallback failed:', e);
    }

    // Strategy 3: Backend stream endpoint (works locally / when Render is up)
    const backendUrl = buildUrl(`/video/${cleanId}/stream`);
    console.log('[VideoAPI] ⚠️ All Supabase strategies failed. Falling back to backend:', backendUrl);
    return backendUrl;
  },
};
