import React from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useUpdateDepartment } from "../../../hooks/admin/useDepartments";
import { useHandleConcurrency } from "../../../hooks/admin/concurrency/useHandleConcurrency";
import { useToast } from "../../../ui/toast/ToastProvider";

const schema = z.object({
  name: z.string().min(1, "Ange namn"),
  resident_count_mode: z.enum(["fixed","weekly"]),
  resident_count_fixed: z.number().int().positive().optional(),
}).refine(v=> v.resident_count_mode==="fixed" ? (v.resident_count_fixed ?? 0) > 0 : true, {
  message:"Ange antal för fast läge", path:["resident_count_fixed"]
});

type FormData = z.infer<typeof schema>;

export function DepartmentEditor({siteId,depart}:{siteId:string, depart:{id:string; name:string; resident_count_mode:"fixed"|"weekly"; resident_count_fixed?:number}}) {
  const f = useForm<FormData>({resolver:zodResolver(schema), defaultValues: depart});
  const m = useUpdateDepartment(siteId);
  const handle412 = useHandleConcurrency();
  const {push} = useToast();

  return (
    <form onSubmit={f.handleSubmit(async (data)=>{
      try {
        await m.mutateAsync({id:depart.id, data});
        push({type:"success", msg:"Sparat"});
      } catch (e:any) {
  if (e.code===412) { await handle412([["departments", siteId]]); push({type:"error", msg:"Konflikt – laddade om senaste värden."}); }
        else if (e.code===403) { push({type:"error", msg:"Saknar behörighet"}); }
        else { push({type:"error", msg:"Kunde inte spara"}); }
      }
    })} style={{display:"grid",gap:8}}>
      <label>Namn <input {...f.register("name")} /></label>
      <label>Läge
        <select {...f.register("resident_count_mode")}>
          <option value="fixed">Fast</option>
          <option value="weekly">Per vecka</option>
        </select>
      </label>
      {f.watch("resident_count_mode")==="fixed" && (
        <label>Antal boende <input type="number" {...f.register("resident_count_fixed",{valueAsNumber:true})} /></label>
      )}
      <button type="submit" disabled={m.isPending}>Spara</button>
    </form>
  );
}
