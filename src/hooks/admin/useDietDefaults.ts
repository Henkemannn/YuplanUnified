import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getDietDefaults, saveDietDefaults } from "../../api/admin";

export function useDietDefaults(depId: string) {
  return useQuery({ queryKey: ["diet-defaults", depId], queryFn: () => getDietDefaults(depId) });
}

export function useSaveDietDefaults(depId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (items:any[]) => saveDietDefaults(depId, items),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["diet-defaults", depId] })
  });
}
