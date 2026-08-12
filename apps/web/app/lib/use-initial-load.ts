"use client";

import { useEffect } from "react";

export function useInitialLoad(load: () => Promise<void>): void {
  useEffect(() => {
    let active = true;
    void Promise.resolve().then(async () => {
      if (active) await load();
    });
    return () => { active = false; };
  }, [load]);
}
