import React, {useMemo, useState} from "react";
import { useDietDefaults, useSaveDietDefaults } from "../../hooks/admin/useDietDefaults";
import { diffRows } from "../../lib/diff";
import { useToast } from "../../ui/toast/ToastProvider";
import { useHandleConcurrency } from "../../hooks/admin/concurrency/useHandleConcurrency";

export default function DietDefaultsPage({departmentId}:{departmentId:string}) {
  const {data, isLoading, isError, refetch} = useDietDefaults(departmentId);
  const [local, setLocal] = useState<any[]|null>(null);
  const save = useSaveDietDefaults(departmentId);
  const handle412 = useHandleConcurrency();
  const {push}=useToast();

  const rows = local ?? data ?? [];
  const onChange = (id:string, amount:number)=> setLocal((cur)=> {
    const src = (cur ?? data ?? []).map((r:any)=> r.id===id? {...r, amount}: r);
    return src;
  });

  const changes = useMemo(()=> diffRows((data??[]) as any, (rows as any)), [data, rows]);

  if (isLoading) return <p>Laddar…</p>;
  if (isError) return <p>Fel vid laddning</p>;
  return (
    <div>
      <h2>Standardkoster</h2>
      <table><thead><tr><th>Kost</th><th>Antal</th></tr></thead>
        <tbody>
          {rows.map((r:any)=>(
            <tr key={r.id}>
              <td>{r.name ?? r.id}</td>
              <td><input type="number" value={r.amount} onChange={e=>onChange(r.id, Number(e.target.value))}/></td>
            </tr>
          ))}
        </tbody>
      </table>
      <button disabled={!changes.length || save.isPending}
        onClick={async ()=>{
          try {
            await save.mutateAsync(changes);
            push({type:"success", msg: changes.length? "Sparat":"Inga ändringar"});
            setLocal(null);
          } catch (e:any) {
            if (e.code===412) { await handle412([["diet-defaults", departmentId]]); push({type:"error", msg:"Konflikt – laddar om…"}); }
            else if (e.code===403) { push({type:"error", msg:"Saknar behörighet"}); }
            else { push({type:"error", msg:"Kunde inte spara"}); }
          }
        }}>
        Spara{changes.length? ` (${changes.length})`:""}
      </button>
      <button onClick={()=>{setLocal(null); refetch();}}>Ångra</button>
    </div>
  );
}
