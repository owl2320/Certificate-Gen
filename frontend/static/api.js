// Thin wrapper over the backend. Every function returns parsed data or throws Error(message).
async function request(path, opts) {
  let res;
  try {
    res = await fetch(API_BASE + path, opts);
  } catch {
    throw new Error(`Cannot reach the server at ${API_BASE || location.origin}. Is uvicorn running?`);
  }
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try { detail = (await res.json()).detail || detail; } catch {}
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  return res;
}

const api = {
  createSession: async (dataFile, templateFile, bijoy) => {
    const fd = new FormData();
    fd.append('data_file', dataFile);
    fd.append('template_file', templateFile);
    fd.append('bijoy_to_unicode', bijoy);
    return (await request('/api/sessions', { method: 'POST', body: fd })).json();
  },
  generate: (sid, columns, merge) =>
    request(`/api/sessions/${sid}/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ columns, merge }),
    }),
  progress: async sid => (await request(`/api/sessions/${sid}/progress`)).json(),
  downloadUrl: sid => `${API_BASE}/api/sessions/${sid}/download`,
  remove: sid => request(`/api/sessions/${sid}`, { method: 'DELETE' }),
};