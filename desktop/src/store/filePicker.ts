type TauriFile = File & { path?: string };

type DialogOpen = (options: { multiple: boolean; filters: Array<{ name: string; extensions: string[] }> }) => Promise<string | string[] | null>;

const getDialogOpen = (): DialogOpen | null => {
  const tauriDialog = (window as typeof window & { __TAURI__?: { dialog?: { open?: DialogOpen } } })
    .__TAURI__?.dialog?.open;
  if (tauriDialog) {
    return tauriDialog;
  }
  return null;
};

export const pickVideoFile = async () => {
  const dialogOpen = getDialogOpen();
  if (dialogOpen) {
    return dialogOpen({
      multiple: false,
      filters: [{ name: "Video", extensions: ["mp4", "mkv", "mov", "m4v", "avi", "webm"] }]
    });
  }
  return new Promise<string | null>((resolve) => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".mp4,.mkv,.mov,.m4v,.avi,.webm,video/*";
    input.onchange = () => {
      const file = input.files?.[0] as TauriFile | undefined;
      resolve(file?.path ?? null);
    };
    input.click();
  });
};
