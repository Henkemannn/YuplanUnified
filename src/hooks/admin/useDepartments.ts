import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listDepartments, updateDepartment, createDepartment } from "../../api/admin";
import { etagKey } from "../../lib/etagStore";

export function useDepartments(siteId: string) {
  return useQuery({ queryKey: ["departments", siteId], queryFn: () => listDepartments(siteId) });
}

export function useUpdateDepartment(siteId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (p:{id:string; data:any}) => updateDepartment(p.id, p.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["departments", siteId] })
  });
}

export function useCreateDepartment(siteId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data:any) => createDepartment({ ...data, site_id: siteId }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["departments", siteId] })
  });
}

export function depResourceKey(depId:string) { return etagKey("admin","department",depId); }
export function alt2ResourceKey(week:number) { return etagKey("admin","alt2","week",String(week)); }
