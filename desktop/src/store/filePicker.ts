type TauriFile = File & { path?: string };

export const pickVideoFile = async () => {
  return new Promise<string | null>((resolve) => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".mp4,.mkv,.mov,.m4v,video/*";
    input.onchange = () => {
      const file = input.files?.[0] as TauriFile | undefined;
      resolve(file?.path ?? null);
    };
    input.click();
  });
};
