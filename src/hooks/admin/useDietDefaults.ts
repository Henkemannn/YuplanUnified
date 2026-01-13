import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getDietDefaults, saveDietDefaults } from "../../api/admin";

export function useDietDefaults(depId: string) {
  const qc = useQueryClient();
  return useQuery({
    queryKey: ["diet-defaults", depId],
    queryFn: async () => {
      const r: any = await getDietDefaults(depId);
      if (r && r.__from304) {
        return (qc.getQueryData(["diet-defaults", depId]) as any) || [];
      }
      return r;
    },
    placeholderData: (prev:any) => prev,
    staleTime: 60_000,
  });
}

export function useSaveDietDefaults(depId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (items:any[]) => saveDietDefaults(depId, items),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["diet-defaults", depId] })
  });
}
