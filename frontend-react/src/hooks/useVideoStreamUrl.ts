import { useState, useEffect } from 'react';
import { videoApi } from '@/api/video';

/**
 * Resolves the best available video stream URL for a given videoId.
 * 
 * On Vercel: uses a Supabase signed URL (direct from storage, always works).
 * Locally / when Render is up: falls back to the backend /video/{id}/stream endpoint.
 * 
 * Returns { url, isLoading, error } so the UI can show a loading/error state.
 */
export function useVideoStreamUrl(videoId: string | null | undefined) {
  const [url, setUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!videoId) {
      setUrl(null);
      setError(null);
      return;
    }

    let cancelled = false;
    setIsLoading(true);
    setUrl(null);
    setError(null);

    console.log('[useVideoStreamUrl] Resolving URL for videoId:', videoId);

    videoApi.getSmartStreamUrl(videoId)
      .then((resolvedUrl) => {
        if (!cancelled) {
          console.log('[useVideoStreamUrl] Resolved URL:', resolvedUrl);
          setUrl(resolvedUrl);
          setIsLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          console.error('[useVideoStreamUrl] Failed to resolve URL:', err);
          setError(err?.message || 'Failed to load video URL');
          setIsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [videoId]);

  return { url, isLoading, error };
}
