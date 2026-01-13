import React, {createContext, useContext, useState, ReactNode} from "react";

type Toast = { id: number; type: "info"|"success"|"error"; msg: string };
const Ctx = createContext<{push:(t:Omit<Toast,"id">)=>void}>({push:()=>{}});
export function ToastProvider({children}:{children:ReactNode}) {
  const [items,setItems]=useState<Toast[]>([]);
  const push = (t:Omit<Toast,"id">)=>setItems(s=>[...s,{...t,id:Date.now()+Math.random()}]);
  return (
    <Ctx.Provider value={{push}}>
      {children}
      <div style={{position:"fixed",right:16,bottom:16,display:"grid",gap:8}}>
        {items.map(t=>(
          <div key={t.id} style={{padding:"8px 12px",borderRadius:8,boxShadow:"0 2px 10px rgba(0,0,0,.12)", background:t.type==="success"?"#ecfff1":t.type==="error"?"#ffecec":"#f3f7ff"}}>
            {t.msg}
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}
export const useToast=()=>useContext(Ctx);
