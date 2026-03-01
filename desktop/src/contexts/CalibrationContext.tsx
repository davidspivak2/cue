import * as React from "react";
import { useLocation } from "react-router-dom";
import { invoke, isTauri } from "@tauri-apps/api/core";
import { createCalibrationJob } from "@/jobsClient";
import { useDeviceInfo, useDeviceInfoRefetch } from "@/contexts/DeviceInfoContext";

const DEFAULT_CALIBRATION_OPTIONS: Record<string, unknown> = {
  transcription_quality: "speed",
  punctuation_rescue_fallback_enabled: false,
  apply_audio_filter: false,
  subtitle_mode: "words",
  highlight_color: "#FFD400",
  vad_gap_rescue_enabled: true
};

type CalibrationContextValue = {
  isCalibrating: boolean;
  calibrationPct: number;
};

const CalibrationContext = React.createContext<CalibrationContextValue | null>(null);

export const useCalibration = (): CalibrationContextValue => {
  const ctx = React.useContext(CalibrationContext);
  if (!ctx) {
    return { isCalibrating: false, calibrationPct: 0 };
  }
  return ctx;
};

export const CalibrationProvider = ({ children }: { children: React.ReactNode }) => {
  const location = useLocation();
  const deviceInfo = useDeviceInfo();
  const refetchDevice = useDeviceInfoRefetch();
  const [isCalibrating, setIsCalibrating] = React.useState(false);
  const [calibrationPct, setCalibrationPct] = React.useState(0);
  const autoStartedRef = React.useRef(false);
  const streamRef = React.useRef<{ close: () => void; cancel: () => Promise<void> } | null>(null);

  const runCalibration = React.useCallback(async () => {
    if (!isTauri()) return;
    try {
      const path = await invoke<string>("get_calibration_video_path");
      setIsCalibrating(true);
      setCalibrationPct(0);
      const stream = await createCalibrationJob(
        { inputPath: path, options: DEFAULT_CALIBRATION_OPTIONS },
        {
          onEvent(ev) {
            if (ev.type === "progress" && typeof ev.pct === "number") {
              setCalibrationPct(Math.round(ev.pct));
            }
            if (ev.type === "completed" || ev.type === "cancelled" || ev.type === "error") {
              streamRef.current = null;
              setIsCalibrating(false);
              void refetchDevice();
            }
          }
        }
      );
      streamRef.current = stream;
    } catch {
      setIsCalibrating(false);
    }
  }, [refetchDevice]);

  React.useEffect(() => {
    if (
      location.pathname === "/" &&
      deviceInfo !== null &&
      !deviceInfo.calibration_done &&
      isTauri() &&
      !autoStartedRef.current
    ) {
      autoStartedRef.current = true;
      void runCalibration();
    }
  }, [location.pathname, deviceInfo, runCalibration]);

  React.useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.close();
        streamRef.current = null;
      }
    };
  }, []);

  const value = React.useMemo<CalibrationContextValue>(
    () => ({ isCalibrating, calibrationPct }),
    [isCalibrating, calibrationPct]
  );

  return (
    <CalibrationContext.Provider value={value}>
      {children}
    </CalibrationContext.Provider>
  );
};
