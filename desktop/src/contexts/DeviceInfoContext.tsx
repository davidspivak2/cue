import * as React from "react";
import { waitForBackendHealthy } from "@/backendHealth";
import { fetchDeviceInfo, type DeviceInfo } from "@/settingsClient";

type DeviceInfoContextValue = {
  deviceInfo: DeviceInfo | null;
  refetch: () => Promise<void>;
};

const DeviceInfoContext = React.createContext<DeviceInfoContextValue | null>(null);

export const useDeviceInfo = (): DeviceInfo | null => {
  const ctx = React.useContext(DeviceInfoContext);
  return ctx?.deviceInfo ?? null;
};

export const useDeviceInfoRefetch = (): (() => Promise<void>) => {
  const ctx = React.useContext(DeviceInfoContext);
  return ctx?.refetch ?? (() => Promise.resolve());
};

export const DeviceInfoProvider = ({ children }: { children: React.ReactNode }) => {
  const [deviceInfo, setDeviceInfo] = React.useState<DeviceInfo | null>(null);

  const refetch = React.useCallback(async () => {
    try {
      await waitForBackendHealthy();
      const data = await fetchDeviceInfo();
      setDeviceInfo(data);
    } catch {
      // Leave existing state
    }
  }, []);

  React.useEffect(() => {
    void refetch();
  }, [refetch]);

  const value = React.useMemo<DeviceInfoContextValue>(
    () => ({ deviceInfo, refetch }),
    [deviceInfo, refetch]
  );

  return (
    <DeviceInfoContext.Provider value={value}>
      {children}
    </DeviceInfoContext.Provider>
  );
};
