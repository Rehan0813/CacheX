// Centralized API configuration for CacheX
// In production on Render (or other hosts), set VITE_API_BASE_URL (e.g. https://cachex-api.onrender.com).
// In local development, falls back to '/api' which Vite proxies to http://127.0.0.1:8000.
const rawUrl = import.meta.env.VITE_API_BASE_URL;

export const API_BASE = rawUrl
    ? rawUrl.replace(/\/+$/, '')
    : (import.meta.env.DEV ? '/api' : '');

export default API_BASE;
