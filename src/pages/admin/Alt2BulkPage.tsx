import React, {useMemo, useState} from "react";
import { useAlt2, useSaveAlt2Bulk } from "../../hooks/admin/useAlt2Bulk";
import { useDepartments } from "../../hooks/admin/useDepartments";
import { useToast } from "../../ui/toast/ToastProvider";
import { useHandleConcurrency } from "../../hooks/admin/concurrency/useHandleConcurrency";

type CellKey = `${string}:${number}`; // depId:weekday

export default function Alt2BulkPage({siteId}:{siteId:string}) {
  const [week,setWeek]=useState<number>(1);
  const {data:deps} = useDepartments(siteId);
  const {data:alt2, isLoading, refetch} = useAlt2(week);
  const [local, setLocal] = useState<Record<CellKey, boolean>|null>(null);
  const save = useSaveAlt2Bulk();
  const {push}=useToast();
  const handle412 = useHandleConcurrency();

  const baseMap = useMemo(()=>{
    const m: Record<CellKey, boolean> = {} as any;
    (alt2?.items??[]).forEach((i:any)=> { (m as any)[`${i.department_id}:${i.weekday}`]= !!i.enabled; });
    return m;
  },[alt2]);

  const model = (local ?? baseMap) as Record<CellKey, boolean>;
  const toggle = (depId:string, weekday:number)=>{
    const k = `${depId}:${weekday}` as CellKey;
    setLocal(cur=> {
      const src = {...(cur ?? baseMap)} as Record<CellKey, boolean>;
      (src as any)[k] = !src[k];
      return src;
    });
  };

  const diffItems = useMemo(()=>{
    const items:any[]=[];
    if (!deps) return items;
    for (const d of deps as any[]) {
      for (let wd=1; wd<=7; wd++){
        const k = `${d.id}:${wd}` as CellKey;
        const before = (baseMap as any)[k]??false;
        const after = (model as any)[k]??false;
        if (before!==after) items.push({department_id:d.id, weekday:wd, enabled:after});
      }
    }
    return items;
  },[deps, baseMap, model]);

  return (
    <div>
      <h2>Alt2 – bulk per vecka</h2>
      <label>Vecka
        <input type="number" min={1} max={53} value={week} onChange={e=>{setWeek(Number(e.target.value)); setLocal(null);}} />
      </label>
      {isLoading? <p>Laddar…</p> : (
        <div style={{overflowX:"auto", marginTop:12}}>
          <table>
            <thead>
              <tr><th>Avdelning</th>{[1,2,3,4,5,6,7].map(w=><th key={w}>D{w}</th>)}</tr>
            </thead>
            <tbody>
              {((deps??[]) as any[]).map(d=>(
                <tr key={d.id}>
                  <td>{d.name}</td>
                  {[1,2,3,4,5,6,7].map(wd=>{
                    const k = `${d.id}:${wd}` as CellKey;
                    const checked = !!(model as any)[k];
                    return (
                      <td key={wd} style={{textAlign:"center"}}>
                        <input type="checkbox" checked={checked} onChange={()=>toggle(d.id, wd)} />
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <button disabled={!diffItems.length || (save as any).isPending}
        onClick={async ()=>{
          try {
            const prevEtag = (save as any).getCollectionEtag?.(week);
            const res = await (save as any).mutateAsync({week, items:diffItems});
            const nextEtag = res?.etag ?? null;
            if (prevEtag && nextEtag && prevEtag===nextEtag) {
              push({type:"info", msg:"Inga ändringar"});
            } else {
              push({type:"success", msg:"Sparat"});
            }
            setLocal(null);
          } catch (e:any) {
            if (e.code===412) { await handle412([["alt2", week]]); push({type:"error", msg:"Konflikt – laddar om…"}); }
            else if (e.code===403) { push({type:"error", msg:"Saknar behörighet"}); }
            else { push({type:"error", msg:"Kunde inte spara"}); }
          } finally {
            refetch();
          }
        }}>
        Spara{diffItems.length? ` (${diffItems.length})`:""}
      </button>
    </div>
  );
}
