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
  subtitle_mode: "static",
  subtitle_style: {
    preset: "Default",
    highlight_color: "#FFD400",
    highlight_opacity: 1.0,
    custom: {
      font_family: "Assistant",
      font_size: 44,
      text_color: "#FFFFFF",
      outline: 0,
      shadow: 0,
      margin_v: 28,
      box_enabled: false,
      box_opacity: 70,
      box_padding: 8
    },
    appearance: {
      font_family: "Assistant",
      font_size: 44,
      text_align: "center",
      line_spacing: 1.0,
      text_color: "#FFFFFF",
      outline_width: 0,
      shadow_strength: 0,
      vertical_offset: 28,
      position_x: 0.5,
      position_y: 0.92,
      background_mode: "none",
      line_bg_opacity: 0.7,
      line_bg_padding: 8,
      subtitle_mode: "static",
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

  await page.route("**://127.0.0.1:8765/device", async (route) => {
    if (route.request().method() !== "GET") {
      await route.continue();
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        gpu_available: false,
        cpu_cores: 4,
        calibration_done: true,
        ultra_available: false,
        ultra_device: null
      })
    });
  });
});

test("save policy enables the path controls", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("title-bar").getByRole("button", { name: "Settings" }).click();
  await expect(page.getByTestId("settings-content")).toBeVisible();

  const pathField = page.getByPlaceholder("No folder selected");
  const browseButton = page.getByRole("button", { name: "Browse..." });

  await expect(pathField).toHaveCount(0);
  await expect(browseButton).toHaveCount(0);

  await page.getByLabel("Specific folder").click();
  await expect(pathField).toBeEnabled();
  await expect(browseButton).toBeEnabled();
});

test("diagnostics section is visible and master toggle gates categories", async ({
  page
}) => {
  await page.goto("/");
  await page.getByTestId("title-bar").getByRole("button", { name: "Settings" }).click();
  await expect(page.getByTestId("settings-content")).toBeVisible();

  const settingsHeading = page.locator("#settings-dialog-title [role='button']");
  await expect(settingsHeading).toBeVisible();
  for (let i = 0; i < 7; i++) {
    await settingsHeading.press("Enter");
  }

  await expect(page.getByTestId("settings-diagnostics-section")).toBeVisible({
    timeout: 10000
  });
  await page.getByTestId("settings-diagnostics-section").scrollIntoViewIfNeeded();

  const master = page.getByLabel("Save diagnostics");
  await expect(master).toBeVisible({ timeout: 5000 });

  const writeOnSuccess = page.getByLabel("Also save when jobs succeed");
  const category = page.getByLabel("Include app and system info");

  await expect(writeOnSuccess).toBeDisabled();
  await expect(category).toBeDisabled();

  await master.click();
  await expect(writeOnSuccess).toBeEnabled();
  await expect(category).toBeEnabled();
});

test("transcription quality updates settings", async ({ page }) => {
  await page.route("**://127.0.0.1:8765/device", async (route) => {
    if (route.request().method() !== "GET") return route.continue();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        gpu_available: true,
        cpu_cores: 8,
        ultra_available: false,
        ultra_device: null
      })
    });
  });

  await page.goto("/");
  await page.getByTestId("title-bar").getByRole("button", { name: "Settings" }).click();
  await expect(page.getByTestId("settings-content")).toBeVisible();
  await expect(page.getByTestId("transcription-quality-skeleton")).toHaveCount(0);

  const qualityRoot = page.getByTestId("transcription-quality-slider");
  await expect(qualityRoot).toBeVisible();
  await qualityRoot.scrollIntoViewIfNeeded();

  const requestPromise = page.waitForRequest(
    (request) => request.url().includes("/settings") && request.method() === "PUT"
  );

  const description = page.locator("#transcription-quality-description");
  await qualityRoot.getByRole("radio", { name: "Faster" }).click();

  const request = await requestPromise;
  const payload = request.postDataJSON();
  expect(payload.settings.transcription_quality).toBe("speed");
  await expect(description).toBeVisible();
  await expect(description).toContainText("Runs on GPU (int8).");
});

test("transcription quality shows a skeleton until device info resolves", async ({
  page
}) => {
  await page.route("**://127.0.0.1:8765/device", async (route) => {
    if (route.request().method() !== "GET") {
      await route.continue();
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 800));
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        gpu_available: true,
        cpu_cores: 8,
        calibration_done: true,
        ultra_available: false,
        ultra_device: null
      })
    });
  });

  await page.goto("/");
  await page.getByTestId("title-bar").getByRole("button", { name: "Settings" }).click();
  await expect(page.getByTestId("settings-content")).toBeVisible();

  await expect(page.getByTestId("transcription-quality-skeleton")).toBeVisible();
  await expect(page.getByTestId("transcription-quality-slider")).toHaveCount(0);

  await expect(page.getByTestId("transcription-quality-skeleton")).toHaveCount(0, {
    timeout: 5000
  });
  await expect(page.getByTestId("transcription-quality-slider")).toBeVisible();
  await expect(page.locator("#transcription-quality-description")).toContainText(
    "Runs on GPU"
  );
});

test("transcription quality uses cached device info on later app loads", async ({
  page
}) => {
  let deviceRequestCount = 0;

  await page.route("**://127.0.0.1:8765/device", async (route) => {
    if (route.request().method() !== "GET") {
      await route.continue();
      return;
    }
    deviceRequestCount += 1;
    if (deviceRequestCount > 1) {
      await new Promise((resolve) => setTimeout(resolve, 2000));
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        gpu_available: true,
        cpu_cores: 8,
        calibration_done: true,
        ultra_available: false,
        ultra_device: null
      })
    });
  });

  await page.goto("/");
  await page.getByTestId("title-bar").getByRole("button", { name: "Settings" }).click();
  await expect(page.getByTestId("settings-content")).toBeVisible();
  await expect(page.getByTestId("transcription-quality-slider")).toBeVisible();
  await expect(page.locator("#transcription-quality-description")).toContainText(
    "Runs on GPU"
  );

  await page.reload();
  await page.getByTestId("title-bar").getByRole("button", { name: "Settings" }).click();
  await expect(page.getByTestId("settings-content")).toBeVisible();
  await expect(page.getByTestId("transcription-quality-skeleton")).toHaveCount(0);
  await expect(page.getByTestId("transcription-quality-slider")).toBeVisible();
  await expect(page.locator("#transcription-quality-description")).toContainText(
    "Runs on GPU"
  );
});
