// API Contract: api() returns parsed JSON (not Response object)
// This prevents confusion with 'res' variable usage after api() calls
window.__mdraftApiContract__ = 'api() returns JSON (not Response)';

export function toast(msg, ms=1500){
  let t = document.querySelector(".toast"); if(!t){ t = document.createElement("div"); t.className="toast"; document.body.appendChild(t); }
  t.textContent = msg; t.classList.add("show");
  setTimeout(()=>t.classList.remove("show"), ms);
}

export async function copy(text){
  try{ await navigator.clipboard.writeText(text); toast("Copied"); }catch{ toast("Copy failed", 2000); }
}

export function fmtDate(s){ try{ return new Date(s).toLocaleString(); }catch{ return s||""; } }

export function dragAndDrop(fileInput, dropEl){
  function prevent(e){ e.preventDefault(); e.stopPropagation(); }
  ["dragenter","dragover","dragleave","drop"].forEach(e=>dropEl.addEventListener(e, prevent, false));
  ["dragenter","dragover"].forEach(e=>dropEl.addEventListener(e, ()=>dropEl.classList.add("dragover")));
  ["dragleave","drop"].forEach(e=>dropEl.addEventListener(e, ()=>dropEl.classList.remove("dragover")));
  dropEl.addEventListener("drop", (e)=>{ const dt=e.dataTransfer; if(dt?.files?.length){ fileInput.files = dt.files; fileInput.dispatchEvent(new Event("change")); }});
}

// API fetch guard to handle JSON errors gracefully
export async function api(url, init = {}) {
  const res = await fetch(url, {
    ...init,
    headers: { 'Accept': 'application/json', ...(init.headers || {}) }
  });

  const ctype = res.headers.get('content-type') || '';
  const isJSON = ctype.includes('application/json');

  if (!res.ok) {
    // Try to parse JSON error; fallback to text
    if (isJSON) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || body.error || `Request failed (${res.status})`);
    } else {
      const text = await res.text().catch(() => '');
      throw new Error(text || `Request failed (${res.status})`);
    }
  }

  return isJSON ? res.json() : (await res.text());
}

// Make api function globally available for templates
window.api = api;
