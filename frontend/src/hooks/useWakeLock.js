import { useEffect } from "react";

export function useWakeLock() {
  useEffect(() => {
    if (!("wakeLock" in navigator)) return undefined;

    let sentinel = null;
    let released = false;

    const request = async () => {
      try {
        sentinel = await navigator.wakeLock.request("screen");
      } catch {
        sentinel = null;
      }
    };

    const handleVisibility = () => {
      if (document.visibilityState === "visible" && !released) request();
    };

    request();
    document.addEventListener("visibilitychange", handleVisibility);

    return () => {
      released = true;
      document.removeEventListener("visibilitychange", handleVisibility);
      sentinel?.release().catch(() => {});
    };
  }, []);
}
