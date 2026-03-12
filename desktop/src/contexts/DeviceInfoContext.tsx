import * as React from "react";
import { waitForBackendHealthy } from "@/backendHealth";
import { fetchDeviceInfo, type DeviceInfo } from "@/settingsClient";

type DeviceInfoContextValue = {
  deviceInfo: DeviceInfo | null;
  isLoading: boolean;
  refetch: () => Promise<void>;
};

const DeviceInfoContext = React.createContext<DeviceInfoContextValue | null>(null);
const DEVICE_INFO_CACHE_KEY = "cue_device_info_cache_v1";

export const useDeviceInfo = (): DeviceInfo | null => {
  const ctx = React.useContext(DeviceInfoContext);
  return ctx?.deviceInfo ?? null;
};

export const useDeviceInfoLoading = (): boolean => {
  const ctx = React.useContext(DeviceInfoContext);
  return ctx?.isLoading ?? false;
};

export const useDeviceInfoRefetch = (): (() => Promise<void>) => {
  const ctx = React.useContext(DeviceInfoContext);
  return ctx?.refetch ?? (() => Promise.resolve());
};

const deviceSimCached: "cpu-strong" | "cpu-weak" | null =
  typeof window !== "undefined"
    ? (() => {
        const d = new URLSearchParams(window.location.search).get("device");
        return d === "cpu-strong" || d === "cpu-weak" ? d : null;
      })()
    : null;

const canUseDeviceInfoCache =
  typeof window !== "undefined" && deviceSimCached === null;

const readCachedDeviceInfo = (): DeviceInfo | null => {
  if (!canUseDeviceInfoCache) {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(DEVICE_INFO_CACHE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as unknown;
    const cachedData =
      parsed && typeof parsed === "object" && "data" in parsed
        ? (parsed as { data?: unknown }).data
        : parsed;
    if (
      !cachedData ||
      typeof cachedData !== "object" ||
      typeof (cachedData as { gpu_available?: unknown }).gpu_available !== "boolean"
    ) {
      window.localStorage.removeItem(DEVICE_INFO_CACHE_KEY);
      return null;
    }
    return cachedData as DeviceInfo;
  } catch {
    window.localStorage.removeItem(DEVICE_INFO_CACHE_KEY);
    return null;
  }
};

const writeCachedDeviceInfo = (deviceInfo: DeviceInfo) => {
  if (!canUseDeviceInfoCache) {
    return;
  }
  try {
    window.localStorage.setItem(
      DEVICE_INFO_CACHE_KEY,
      JSON.stringify({ version: 1, data: deviceInfo })
    );
  } catch {
    // Ignore storage failures and keep in-memory state.
  }
};

export const DeviceInfoProvider = ({ children }: { children: React.ReactNode }) => {
  const initialDeviceInfoRef = React.useRef<DeviceInfo | null | undefined>(undefined);
  if (initialDeviceInfoRef.current === undefined) {
    initialDeviceInfoRef.current = readCachedDeviceInfo();
  }
  const initialDeviceInfo = initialDeviceInfoRef.current ?? null;
  const [deviceInfo, setDeviceInfo] = React.useState<DeviceInfo | null>(initialDeviceInfo);
  const [isLoading, setIsLoading] = React.useState(initialDeviceInfo === null);
  const deviceInfoRef = React.useRef<DeviceInfo | null>(initialDeviceInfo);
  deviceInfoRef.current = deviceInfo;

  const refetch = React.useCallback(async () => {
    if (deviceInfoRef.current === null) {
      setIsLoading(true);
    }
    try {
      await waitForBackendHealthy();
      let data = await fetchDeviceInfo();
      const deviceSim = deviceSimCached;
      if (deviceSim === "cpu-strong" || deviceSim === "cpu-weak") {
        data = {
          ...data,
          gpu_available: false,
          gpu_name: null,
          ultra_device: deviceSim === "cpu-strong" ? "cpu" : null,
          ultra_available: deviceSim === "cpu-strong"
        };
      }
      setDeviceInfo(data);
      writeCachedDeviceInfo(data);
    } catch {
      // Leave existing state
    } finally {
      setIsLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void refetch();
  }, [refetch]);

  const value = React.useMemo<DeviceInfoContextValue>(
    () => ({ deviceInfo, isLoading, refetch }),
    [deviceInfo, isLoading, refetch]
  );

  return (
    <DeviceInfoContext.Provider value={value}>
      {children}
    </DeviceInfoContext.Provider>
  );
};
