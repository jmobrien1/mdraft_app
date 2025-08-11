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
