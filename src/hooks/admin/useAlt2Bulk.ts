import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getAlt2, saveAlt2Bulk } from "../../api/admin";
import { alt2ResourceKey } from "./useDepartments";
import { getETag } from "../../lib/etagStore";

export function useAlt2(week: number) {
  const qc = useQueryClient();
  return useQuery({
    queryKey: ["alt2", week],
    queryFn: async () => {
      const r: any = await getAlt2(week);
      if (r && (r as any).__from304) {
        return (qc.getQueryData(["alt2", week]) as any) || null;
      }
      return r;
    },
    placeholderData: (prev:any) => prev,
    staleTime: 60_000,
  });
}

export function useSaveAlt2(week: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (items:any[]) => saveAlt2Bulk(week, items),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alt2", week] })
  });
}

export function alt2CollectionKey(week:number) { return alt2ResourceKey(week); }

// Convenience variant for Alt2BulkPage usage: exposes getCollectionEtag and accepts payload with week+items
export function useSaveAlt2Bulk() {
  const qc = useQueryClient();
  return Object.assign(
    useMutation({
      mutationFn: (p:{week:number; items:any[]}) => saveAlt2Bulk(p.week, p.items),
      onSuccess: (_res, vars) => qc.invalidateQueries({ queryKey: ["alt2", vars.week] })
    }),
    {
      getCollectionEtag(week:number){
        return getETag(alt2ResourceKey(week));
      }
    }
  );
}
