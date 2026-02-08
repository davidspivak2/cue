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

const initMocks = () => {
  const state = {
    last: null,
    lastUrl: "",
    createdCount: 0
  };

  class MockEventSource {
    constructor(url) {
      this.url = url;
      this.readyState = 1;
      this._listeners = {};
      state.last = this;
      state.lastUrl = url;
      state.createdCount += 1;
      setTimeout(() => this._emit("open", {}), 0);
    }

    addEventListener(type, callback) {
      if (!this._listeners[type]) {
        this._listeners[type] = [];
      }
      this._listeners[type].push(callback);
    }

    removeEventListener(type, callback) {
      if (!this._listeners[type]) {
        return;
      }
      this._listeners[type] = this._listeners[type].filter((item) => item !== callback);
    }

    close() {
      this.readyState = 2;
    }

    _emit(type, event) {
      (this._listeners[type] || []).forEach((callback) => callback(event));
    }

    _emitMessage(data) {
      this._emit("message", { data: JSON.stringify(data) });
    }

    _emitError() {
      this._emit("error", {});
    }
  }

  Object.defineProperty(File.prototype, "path", {
    configurable: true,
    get() {
      const name = this.name || "video.mp4";
      return `C:\\\\fake\\\\${name}`;
    }
  });

  window.EventSource = MockEventSource;
  window.__mockEventSourceState = state;
  window.__mockEventSourceEmit = (payload) => {
    if (state.last) {
      state.last._emitMessage(payload);
    }
  };
  window.__mockEventSourceError = () => {
    if (state.last) {
      state.last._emitError();
    }
  };
};

test("home flow shows Qt-parity copy", async ({ page }) => {
  await page.addInitScript(initMocks);

  let currentSettings = buildSettings();
  let jobCounter = 0;
  let lastJobId = "";
  let lastEventsUrl = "";

  await page.route("**/settings", async (route) => {
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

  await page.route("**://127.0.0.1:8765/preview-style", async (route) => {
    if (route.request().method() === "OPTIONS") {
      await route.fulfill({
        status: 204,
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "POST, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type"
        }
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ preview_path: "C:\\fake\\preview.png" })
    });
  });

  await page.route("**://127.0.0.1:8765/jobs", async (route) => {
    const request = route.request();
    if (request.method() === "OPTIONS") {
      await route.fulfill({
        status: 204,
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type"
        }
      });
      return;
    }
    if (request.method() === "POST") {
      jobCounter += 1;
      lastJobId = `job-${jobCounter}`;
      lastEventsUrl = `http://127.0.0.1:8765/jobs/${lastJobId}/events`;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          job_id: lastJobId,
          events_url: lastEventsUrl,
          status: "running"
        })
      });
      return;
    }
    await route.continue();
  });

  await page.goto("/");

  await expect(page.getByText("Drop a video here")).toBeVisible();
  await expect(page.getByText("or choose one from your computer")).toBeVisible();
  await expect(page.getByRole("button", { name: "Choose video..." })).toBeVisible();

  await page.locator("input[type='file']").setInputFiles({
    name: "sample.mp4",
    mimeType: "video/mp4",
    buffer: Buffer.from("fake")
  });

  const createSubtitles = page.getByRole("button", { name: "Create subtitles" });
  await expect(createSubtitles).toBeVisible();

  const createRequest = page.waitForRequest(
    (request) => request.url().endsWith("/jobs") && request.method() === "POST"
  );
  await createSubtitles.click();
  await createRequest;

  await page.waitForFunction(
    (expectedUrl) => window.__mockEventSourceState?.lastUrl === expectedUrl,
    lastEventsUrl
  );

  await page.evaluate((payload) => window.__mockEventSourceEmit(payload), {
    job_id: lastJobId,
    ts: "2026-02-06T00:00:00Z",
    type: "started",
    heading: "Creating subtitles",
    log_path: "C:\\fake\\session.log"
  });
  await page.evaluate((payload) => window.__mockEventSourceEmit(payload), {
    job_id: lastJobId,
    ts: "2026-02-06T00:00:01Z",
    type: "progress",
    pct: 25,
    message: "Extracting audio"
  });

  await expect(page.getByRole("heading", { name: "Creating subtitles" })).toBeVisible();
  await expect(page.getByText("25%")).toBeVisible();
  await expect(page.getByText("Elapsed:")).toBeVisible();
  await expect(page.getByRole("button", { name: "Cancel" })).toBeVisible();

  await page.evaluate((payload) => window.__mockEventSourceEmit(payload), {
    job_id: lastJobId,
    ts: "2026-02-06T00:00:02Z",
    type: "result",
    payload: {
      srt_path: "C:\\fake\\sample.srt",
      log_path: "C:\\fake\\session.log"
    }
  });
  await page.evaluate((payload) => window.__mockEventSourceEmit(payload), {
    job_id: lastJobId,
    ts: "2026-02-06T00:00:03Z",
    type: "completed",
    status: "completed"
  });

  /* After subtitle creation completes, app navigates to /review */
  await expect(page.getByRole("heading", { name: "Review subtitles" })).toBeVisible();
  await expect(page.url()).toContain("/review");

  /* Verify style controls are visible on the Review page */
  await expect(page.getByText("Mode")).toBeVisible();
  await expect(page.getByText("Quick settings")).toBeVisible();
  await expect(page.getByText("Background")).toBeVisible();

  /* Click Export to go back to Home and start the export job */
  const exportSettingsRequest = page.waitForRequest(
    (request) => request.url().includes("/settings") && request.method() === "PUT"
  );
  const exportButton = page.getByRole("button", { name: "Export video" });
  await expect(exportButton).toBeVisible();
  await exportButton.click();

  await exportSettingsRequest;

  /* Should navigate back to Home and auto-start export */
  const exportJobRequest = page.waitForRequest(
    (request) => request.url().endsWith("/jobs") && request.method() === "POST"
  );
  await exportJobRequest;

  await page.waitForFunction(
    (expectedUrl) => window.__mockEventSourceState?.lastUrl === expectedUrl,
    lastEventsUrl
  );

  await page.evaluate((payload) => window.__mockEventSourceEmit(payload), {
    job_id: lastJobId,
    ts: "2026-02-06T00:00:04Z",
    type: "started",
    heading: "Creating video with subtitles",
    log_path: "C:\\fake\\session.log"
  });
  await page.evaluate((payload) => window.__mockEventSourceEmit(payload), {
    job_id: lastJobId,
    ts: "2026-02-06T00:00:05Z",
    type: "result",
    payload: {
      output_path: "C:\\fake\\sample_subtitled.mp4",
      log_path: "C:\\fake\\session.log"
    }
  });
  await page.evaluate((payload) => window.__mockEventSourceEmit(payload), {
    job_id: lastJobId,
    ts: "2026-02-06T00:00:06Z",
    type: "completed",
    status: "completed"
  });

  await expect(page.getByText("Your video is ready")).toBeVisible();
  await expect(page.getByRole("button", { name: "Play video" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Open folder" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Edit subtitles and export again" })).toBeVisible();
});
