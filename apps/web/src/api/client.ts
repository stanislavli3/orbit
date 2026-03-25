import { useAuth } from '@clerk/clerk-react';

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

/**
 * Hook that returns an authenticated fetch wrapper.
 * Automatically attaches the Clerk JWT to every request.
 * Does NOT set Content-Type for FormData — the browser sets it with the boundary.
 */
export function useApiClient() {
  const { getToken } = useAuth();

  return async function apiFetch(path: string, options?: RequestInit): Promise<Response> {
    const token = await getToken();

    const headers: Record<string, string> = {
      Authorization: `Bearer ${token}`,
    };

    if (!(options?.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
    }

    return fetch(`${API_BASE}${path}`, {
      ...options,
      headers: { ...headers, ...(options?.headers as Record<string, string>) },
    });
  };
}
