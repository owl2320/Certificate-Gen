// Where the FastAPI server lives.
// '' = same origin (page is served by FastAPI on :8000, or in production behind a proxy).
// Otherwise (Live Server, file://, etc.) talk to the local backend directly.
const API_BASE =
  location.protocol !== 'file:' && (location.port === '8000' || location.port === '')
    ? ''
    : 'http://localhost:8000';