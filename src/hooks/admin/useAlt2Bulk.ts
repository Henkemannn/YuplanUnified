import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getAlt2, saveAlt2Bulk } from "../../api/admin";
import { alt2ResourceKey } from "./useDepartments";

export function useAlt2(week: number) {
  return useQuery({ queryKey: ["alt2", week], queryFn: () => getAlt2(week) });
}

export function useSaveAlt2(week: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (items:any[]) => saveAlt2Bulk(week, items),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alt2", week] })
  });
}

export function alt2CollectionKey(week:number) { return alt2ResourceKey(week); }
