import { expect, test } from "@playwright/test";

const buildSettings = () => ({
  save_policy: "same_folder",
  save_folder: "",
  transcription_quality: "auto",
  punctuation_rescue_fallback_enabled: true,
  apply_audio_filter: false,
  keep_extracted_audio: false,
  diagnostics: {
    enabled: false,
    write_on_success: false,
    archive_on_exit: false,
    categories: {
      app_system: true,
      video_info: true,
      audio_info: true,
      transcription_config: true,
      srt_stats: true,
      commands_timings: true
    }
  },
  subtitle_mode: "word_highlight",
  subtitle_style: {
    preset: "Default",
    highlight_color: "#FFD400",
    highlight_opacity: 1.0,
    custom: {
      font_family: "Arial",
      font_size: 28,
      text_color: "#FFFFFF",
      outline: 2,
      shadow: 1,
      margin_v: 28,
      box_enabled: false,
      box_opacity: 70,
      box_padding: 8
    },
    appearance: {
      font_family: "Arial",
      font_size: 28,
      text_color: "#FFFFFF",
      outline_width: 2,
      shadow_strength: 1,
      vertical_offset: 28,
      background_mode: "none",
      line_bg_opacity: 0.7,
      line_bg_padding: 8,
      subtitle_mode: "word_highlight",
      highlight_color: "#FFD400"
    }
  }
});

const mergeDeep = (base, update) => {
  const next = { ...base };
  Object.entries(update || {}).forEach(([key, value]) => {
    if (
      value &&
      typeof value === "object" &&
      !Array.isArray(value) &&
      next[key] &&
      typeof next[key] === "object" &&
      !Array.isArray(next[key])
    ) {
      next[key] = mergeDeep(next[key], value);
    } else {
      next[key] = value;
    }
  });
  return next;
};

test.beforeEach(async ({ page }) => {
  let currentSettings = buildSettings();

  await page.route("**://127.0.0.1:8765/settings", async (route) => {
    const request = route.request();
    if (request.method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(currentSettings)
      });
      return;
    }
    if (request.method() === "PUT") {
      const payload = request.postDataJSON();
      currentSettings = mergeDeep(currentSettings, payload?.settings ?? {});
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(currentSettings)
      });
      return;
    }
    await route.continue();
  });
});

test("save policy enables the path controls", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Settings" }).click();
  await expect(page.getByTestId("settings-content")).toBeVisible();

  const pathField = page.getByPlaceholder("No folder selected");
  const browseButton = page.getByRole("button", { name: "Browse..." });

  await expect(pathField).toBeDisabled();
  await expect(browseButton).toBeDisabled();

  await page.getByLabel("Always save to this folder").click();
  await expect(pathField).toBeEnabled();
  await expect(browseButton).toBeEnabled();
});

test("diagnostics section is visible and master toggle gates categories", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Settings" }).click();
  await expect(page.getByTestId("settings-content")).toBeVisible();

  await expect(page.getByTestId("settings-diagnostics-section")).toBeVisible({
    timeout: 10000
  });
  await page.getByTestId("settings-diagnostics-section").scrollIntoViewIfNeeded();

  const master = page.getByLabel("Enable diagnostics logging");
  await expect(master).toBeVisible({ timeout: 5000 });

  const writeOnSuccess = page.getByLabel("Write diagnostics on successful completion");
  const category = page.getByLabel("App + system info");

  await expect(writeOnSuccess).toBeDisabled();
  await expect(category).toBeDisabled();

  await master.check();
  await expect(writeOnSuccess).toBeEnabled();
  await expect(category).toBeEnabled();
});

test("transcription quality updates settings", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Settings" }).click();
  await expect(page.getByTestId("settings-content")).toBeVisible();

  const requestPromise = page.waitForRequest(
    (request) => request.url().includes("/settings") && request.method() === "PUT"
  );

  await page.locator("#transcription-quality").click();
  await page.getByRole("option", { name: "Fast (int8)" }).click();

  const request = await requestPromise;
  const payload = request.postDataJSON();
  expect(payload.settings.transcription_quality).toBe("fast");
});
