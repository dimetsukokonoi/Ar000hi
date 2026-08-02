// Central backend address. Uses explicit IPv4 `127.0.0.1` instead of the
// `localhost` hostname, because on many systems `localhost` resolves to the
// IPv6 loopback `::1` first — while the backend binds IPv4 only. Firefox/gecko
// (and some OSes) then fail to connect while Chromium silently falls back to
// IPv4. Hardcoding IPv4 here is deterministic and portable across browsers/OSes.
//
// Override at runtime/build-time with NEXT_PUBLIC_API_URL if the backend
// changes location, e.g.  NEXT_PUBLIC_API_URL=http://192.168.1.50:8000

const DEFAULT_API_BASE = "http://127.0.0.1:8000";
const API_BASE = (process.env.NEXT_PUBLIC_API_URL || DEFAULT_API_BASE).replace(/\/$/, "");

// REST prefix, e.g. http://127.0.0.1:8000/api
export const API = `${API_BASE}/api`;

// WebSocket base (for backend /ws endpoints), e.g. ws://127.0.0.1:8000/ws
export const WS = `${API_BASE.replace(/^http/, "ws")}/ws`;

// Raw backend base, for absolute links (e.g. uploaded-document URLs)
export { API_BASE };