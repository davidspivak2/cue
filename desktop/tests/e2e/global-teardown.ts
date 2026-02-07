import fs from "fs";
import path from "path";
import { spawnSync } from "child_process";

const EXTRA_DIR = "C:\\Cue_extra\\e2e";
const PID_FILE = path.join(EXTRA_DIR, "backend_pid.json");

export default async () => {
  if (!fs.existsSync(PID_FILE)) {
    return;
  }

  const payload = JSON.parse(fs.readFileSync(PID_FILE, "utf-8")) as { pid?: number };
  const pid = payload.pid;

  if (pid) {
    if (process.platform === "win32") {
      spawnSync("taskkill", ["/PID", String(pid), "/T", "/F"], { stdio: "ignore" });
    } else {
      try {
        process.kill(pid);
      } catch {
        // ignore
      }
    }
  }

  try {
    fs.unlinkSync(PID_FILE);
  } catch {
    // ignore
  }
};
