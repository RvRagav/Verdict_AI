// Axios API client. The X-Officer-ID header travels with every request,
// reflecting the officer currently selected in the picker. Errors are
// normalised to a thrown Error with .status on it for the UI to handle.

import axios, { AxiosError } from 'axios';

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) || '/api/v1';

const api = axios.create({ baseURL: API_BASE, timeout: 60_000 });

let currentOfficerId = 'officer-sharma';

export function setOfficer(id: string) {
  currentOfficerId = id;
  try { localStorage.setItem('verdictai.officer', id); } catch {}
}

export function getOfficer(): string {
  try {
    const stored = localStorage.getItem('verdictai.officer');
    if (stored) currentOfficerId = stored;
  } catch {}
  return currentOfficerId;
}

api.interceptors.request.use(cfg => {
  cfg.headers = cfg.headers || {};
  (cfg.headers as Record<string, string>)['X-Officer-ID'] = getOfficer();
  return cfg;
});

api.interceptors.response.use(
  r => r,
  (err: AxiosError) => {
    const status = err.response?.status ?? 0;
    const detail = (err.response?.data as { detail?: string } | undefined)?.detail
      ?? err.message ?? 'Request failed';
    const error = new Error(detail);
    (error as { status?: number }).status = status;
    return Promise.reject(error);
  },
);

export default api;
