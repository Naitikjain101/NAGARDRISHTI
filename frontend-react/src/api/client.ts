export const API_BASE = import.meta.env.VITE_API_BASE_URL || (import.meta.env.PROD ? 'https://nagardristhi.onrender.com' : 'http://localhost:8000');

export function buildUrl(endpoint: string): string {
  if (endpoint.startsWith('http')) return endpoint;
  
  let base = API_BASE.endsWith('/') ? API_BASE.slice(0, -1) : API_BASE;
  let cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  
  if (base.endsWith('/api')) {
     base = base.substring(0, base.length - 4);
  }
  
  if (!cleanEndpoint.startsWith('/api')) {
     cleanEndpoint = `/api${cleanEndpoint}`;
  }
  
  return `${base}${cleanEndpoint}`;
}

import { supabase } from '../lib/supabase';

export async function fetchRaw(endpoint: string, options: RequestInit = {}): Promise<Response> {
  const url = buildUrl(endpoint);
  
  const { data: { session } } = await supabase.auth.getSession();
  const headers = new Headers(options.headers || {});
  headers.set('Accept', 'application/json');
  
  if (session?.access_token) {
    headers.set('Authorization', `Bearer ${session.access_token}`);
  }

  return fetch(url, {
    ...options,
    headers
  });
}

export async function fetchApi<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const response = await fetchRaw(endpoint, options);

  if (!response.ok) {
    let errorMessage = 'An error occurred';
    try {
      const errorData = await response.json();
      errorMessage = errorData.detail || errorData.message || response.statusText;
    } catch (e) {
      errorMessage = response.statusText;
    }
    throw new Error(errorMessage);
  }

  return response.json();
}
