/**
 * Frontend configuration utilities.
 *
 * Auto-detects backend URLs based on current hostname.
 */

/**
 * Get the backend API base URL.
 *
 * If VITE_API_URL is set, use it.
 * Otherwise, auto-detect based on window.location.hostname.
 */
export function getApiBaseUrl(): string {
  const envUrl = import.meta.env.VITE_API_URL;
  if (envUrl) {
    return envUrl;
  }

  // Auto-detect: use same hostname as frontend, but port 8000
  const hostname = window.location.hostname;
  return `http://${hostname}:8000`;
}

/**
 * Get the WebSocket base URL.
 *
 * If VITE_WS_URL is set, use it.
 * Otherwise, auto-detect based on window.location.hostname.
 */
export function getWsBaseUrl(): string {
  const envUrl = import.meta.env.VITE_WS_URL;
  if (envUrl) {
    return envUrl;
  }

  // Auto-detect: use same hostname as frontend, but port 8000
  const hostname = window.location.hostname;
  return `ws://${hostname}:8000`;
}
