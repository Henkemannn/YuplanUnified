import React, {useState} from "react";
import { useDepartments } from "../../hooks/admin/useDepartments";
import { DepartmentEditor } from "./components/DepartmentEditor";
import type { Department } from "../../api/admin";

export default function DepartmentsPage({siteId}:{siteId:string}) {
  const {data, isLoading, isError, refetch} = useDepartments(siteId);
  const [sel, setSel] = useState<string|null>(null);
  if (isLoading) return <p>Laddar…</p>;
  if (isError) return <p>Fel vid laddning</p>;
  const chosen = (data as Department[] | undefined)?.find((d:Department)=>d.id===sel) ?? (data && (data as Department[])[0]);
  return (
    <div style={{display:"grid",gridTemplateColumns:"1fr 2fr",gap:16}}>
      <div>
        <h2>Avdelningar</h2>
        <ul>
          {((data??[]) as Department[]).map((d:Department)=>(
            <li key={d.id}>
              <button onClick={()=>setSel(d.id)} style={{fontWeight: chosen?.id===d.id?"bold":"normal"}}>{d.name}</button>
            </li>
          ))}
        </ul>
        <button onClick={()=>refetch()}>Uppdatera lista</button>
      </div>
      <div>
        {chosen && <DepartmentEditor siteId={siteId} depart={chosen as any} />}
      </div>
    </div>
  );
}
