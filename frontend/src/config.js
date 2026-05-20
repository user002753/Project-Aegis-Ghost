// Resolve API base URL for both local and LAN access.
// If env uses localhost/127.0.0.1 but app is opened from another device,
// rewrite host to current page hostname while keeping protocol/port.
const rawApiUrl = (process.env.REACT_APP_API_URL || '').trim();

function resolveApiBaseUrl() {
  if (!rawApiUrl) return '';

  try {
    const parsed = new URL(rawApiUrl);
    const isLoopback = parsed.hostname === '127.0.0.1' || parsed.hostname === 'localhost';
    const pageHost = window?.location?.hostname || '';
    const pageIsLoopback = pageHost === '127.0.0.1' || pageHost === 'localhost';

    if (isLoopback && pageHost && !pageIsLoopback) {
      parsed.hostname = pageHost;
      return parsed.origin;
    }

    return parsed.origin;
  } catch {
    return rawApiUrl;
  }
}

export const API_BASE_URL = resolveApiBaseUrl();
