import { useEffect, useState } from "react";
import { isNativeApp } from "@/lib/nativeDownloads";

/** true dans l'application Android. Décidé après l'affichage (côté navigateur) pour rester identique au rendu serveur. */
export function useIsApp(): boolean {
  const [app, setApp] = useState(false);
  useEffect(() => {
    setApp(isNativeApp());
  }, []);
  return app;
}
