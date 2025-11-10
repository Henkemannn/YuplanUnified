import { useCallback } from "react";
import { ConcurrencyError } from "../../../lib/errors";
import { useQueryClient } from "@tanstack/react-query";

// Minimal toast stub (replace with real system later)
function toast(msg:string){
  if (typeof window !== 'undefined') {
    // append basic div; in real system integrate library
    const el = document.createElement('div');
    el.textContent = msg;
    el.style.position='fixed'; el.style.bottom='1rem'; el.style.right='1rem'; el.style.background='#f44336'; el.style.color='#fff'; el.style.padding='0.5rem 0.75rem'; el.style.zIndex='9999';
    document.body.appendChild(el);
    setTimeout(()=> el.remove(), 4000);
  } else {
    console.log('[toast]', msg);
  }
}

export function useHandleConcurrency() {
  const qc = useQueryClient();
  return useCallback((err:any, invalidateKeys: (string|any[])[]) => {
    if (err instanceof ConcurrencyError || err?.code === 412) {
      toast("Uppgiften har uppdaterats av någon annan. Laddar om…");
      for (const k of invalidateKeys) {
        qc.invalidateQueries(typeof k === 'string' ? { queryKey: [k] } : { queryKey: k });
      }
    }
  }, [qc]);
}
