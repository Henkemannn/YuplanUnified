import { useCallback } from "react";
import { ConcurrencyError } from "../../../lib/errors";
import { useQueryClient } from "@tanstack/react-query";
import { useToast } from "../../../ui/toast/ToastProvider";

export function useHandleConcurrency() {
  const qc = useQueryClient();
  const { push } = useToast();
  return useCallback(async (invalidateQueryKeys: (any[])[]) => {
    push({type:"error", msg:"Uppgiften har uppdaterats av någon annan. Laddar om…"});
    for (const qk of invalidateQueryKeys) {
      await qc.invalidateQueries({ queryKey: qk });
    }
  }, [qc, push]);
}
