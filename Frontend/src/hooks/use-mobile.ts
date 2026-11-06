import { useCallback, useSyncExternalStore } from "react";

const MOBILE_QUERY = "(max-width: 767px)";

export function useIsMobile() {
  const subscribe = useCallback((onChange: () => void) => {
    const mediaQuery = window.matchMedia(MOBILE_QUERY);
    mediaQuery.addEventListener("change", onChange);
    return () => mediaQuery.removeEventListener("change", onChange);
  }, []);

  const getSnapshot = useCallback(
    () => window.matchMedia(MOBILE_QUERY).matches,
    [],
  );
  const getServerSnapshot = useCallback(() => false, []);

  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
