import { expect, test } from "@playwright/test";

const initMocks = () => {
  Object.defineProperty(File.prototype, "path", {
    configurable: true,
    get() {
      const name = this.name || "video.mp4";
      return `C:\\\\fake\\\\${name}`;
    }
  });
};

const buildProjects = () => [
  {
    project_id: "project-1",
    title: "good.mp4",
    video_path: "C:\\fake\\good.mp4",
    missing_video: false,
    status: "needs_subtitles",
    created_at: "2026-02-09T00:00:00Z",
    updated_at: "2026-02-09T00:00:00Z",
    duration_seconds: 65,
    thumbnail_path: "",
    latest_export: null
  }
];

const DEFAULT_PROJECT_STYLE = {
  subtitle_mode: "word_highlight",
  subtitle_style: {
    preset: "Default",
    highlight_color: "#FFD400",
    highlight_opacity: 1.0,
    appearance: {
      font_family: "Arial",
      font_size: 28,
      font_style: "regular",
      text_color: "#FFFFFF",
      text_opacity: 1.0,
      letter_spacing: 0,
      outline_enabled: true,
      outline_width: 2,
      outline_color: "#000000",
      shadow_enabled: true,
      shadow_strength: 1,
      shadow_offset_x: 0,
      shadow_offset_y: 0,
      shadow_color: "#000000",
      shadow_opacity: 1.0,
      background_mode: "none",
      line_bg_color: "#000000",
      line_bg_opacity: 0.7,
      line_bg_padding: 8,
      line_bg_radius: 0,
      word_bg_color: "#000000",
      word_bg_opacity: 0.4,
      word_bg_padding: 8,
      word_bg_radius: 0,
      vertical_anchor: "bottom",
      vertical_offset: 28,
      subtitle_mode: "word_highlight",
      highlight_color: "#FFD400"
    }
  }
};

const buildManifest = (project) => ({
  project_id: project.project_id,
  status: project.status,
  created_at: project.created_at,
  updated_at: project.updated_at,
  video: {
    path: project.video_path,
    filename: project.title,
    duration_seconds: project.duration_seconds,
    thumbnail_path: project.thumbnail_path
  },
  artifacts: {
    subtitles_path: "subtitles.srt",
    word_timings_path: "word_timings.json",
    style_path: "style.json"
  },
  latest_export: project.latest_export ?? null,
  style: project.style ?? DEFAULT_PROJECT_STYLE
});

const DEFAULT_SRT = "1\n00:00:00,000 --> 00:00:04,000\nOriginal subtitle line\n";
const GENERATED_SRT = "1\n00:00:00,000 --> 00:00:03,000\nGenerated subtitle line\n";

const getProjectIdFromUrl = (url) => url.split("/projects/")[1]?.split("/")[0] ?? "";
const getJobIdFromEventsUrl = (url) => url.split("/jobs/")[1]?.split("/")[0] ?? "";

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
    appearance: {
      font_family: "Arial",
      font_size: 28,
      text_color: "#FFFFFF",
      outline_width: 2,
      shadow_strength: 1,
      vertical_offset: 28,
      subtitle_mode: "word_highlight",
      highlight_color: "#FFD400"
    }
  }
});

const mockProjects = async (page, projects, initialSrtText = DEFAULT_SRT) => {
  let putCallCount = 0;
  let subtitlePutCallCount = 0;
  let lastPutPayload = null;
  let lastJobPayload = null;
  let createdProjectCount = 0;
  let settings = buildSettings();
  const subtitlesByProject = new Map();
  if (typeof initialSrtText === "string") {
    projects.forEach((project) => {
      subtitlesByProject.set(project.project_id, initialSrtText);
    });
  }
  const eventsByJob = new Map();

  await page.route("**://127.0.0.1:8765/settings", async (route) => {
    const request = route.request();
    if (request.method() === "OPTIONS") {
      await route.fulfill({
        status: 204,
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "GET, PUT, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type"
        }
      });
      return;
    }
    if (request.method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(settings)
      });
      return;
    }
    if (request.method() === "PUT") {
      try {
        const payload = JSON.parse(request.postData() ?? "{}");
        const update = payload?.settings ?? {};
        settings = { ...settings, ...update };
      } catch {
        // ignore malformed payloads in test mocks.
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(settings)
      });
      return;
    }
    await route.continue();
  });

  await page.route("**://127.0.0.1:8765/projects", async (route) => {
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
    if (request.method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(projects)
      });
      return;
    }
    if (request.method() === "POST") {
      createdProjectCount += 1;
      let payload: Record<string, unknown> = {};
      try {
        payload = JSON.parse(request.postData() ?? "{}");
      } catch {
        payload = {};
      }
      const videoPath =
        typeof payload.video_path === "string" && payload.video_path
          ? payload.video_path
          : `C:\\fake\\created_${createdProjectCount}.mp4`;
      const title = videoPath.split(/[/\\]/).pop() || `created_${createdProjectCount}.mp4`;
      const now = "2026-02-09T00:00:00Z";
      const createdProject = {
        project_id: `project-new-${createdProjectCount}`,
        title,
        video_path: videoPath,
        missing_video: false,
        status: "needs_subtitles",
        created_at: now,
        updated_at: now,
        duration_seconds: 65,
        thumbnail_path: ""
      };
      projects = [createdProject, ...projects];
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(createdProject)
      });
      return;
    }
    await route.continue();
  });

  await page.route("**://127.0.0.1:8765/projects/*/subtitles", async (route) => {
    const request = route.request();
    if (request.method() !== "GET") {
      await route.continue();
      return;
    }
    const projectId = getProjectIdFromUrl(request.url());
    if (!projectId || !subtitlesByProject.has(projectId)) {
      await route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({ detail: "subtitles_not_found" })
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ subtitles_srt_text: subtitlesByProject.get(projectId) })
    });
  });

  await page.route("**://127.0.0.1:8765/projects/*", async (route) => {
    const request = route.request();
    const projectId = getProjectIdFromUrl(request.url());
    const project = projects.find((entry) => entry.project_id === projectId);
    if (!project) {
      await route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({ detail: "not_found" })
      });
      return;
    }

    if (request.method() === "PUT") {
      putCallCount += 1;
      try {
        lastPutPayload = JSON.parse(request.postData() ?? "{}");
      } catch {
        lastPutPayload = null;
      }
      if (lastPutPayload && typeof lastPutPayload.subtitles_srt_text === "string") {
        subtitlePutCallCount += 1;
        subtitlesByProject.set(projectId, lastPutPayload.subtitles_srt_text);
      }
      if (lastPutPayload && typeof lastPutPayload.style === "object") {
        projects = projects.map((entry) =>
          entry.project_id === projectId
            ? { ...entry, style: lastPutPayload.style, updated_at: "2026-02-09T00:05:00Z" }
            : entry
        );
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(buildManifest(project))
      });
      return;
    }

    if (request.method() !== "GET") {
      await route.continue();
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(buildManifest(project))
    });
  });

  await page.route("**://127.0.0.1:8765/jobs", async (route) => {
    const request = route.request();
    if (request.method() !== "POST") {
      await route.continue();
      return;
    }
    try {
      lastJobPayload = JSON.parse(request.postData() ?? "{}");
    } catch {
      lastJobPayload = null;
    }
    const jobId = `job-${Date.now()}`;
    const eventsUrl = `http://127.0.0.1:8765/jobs/${jobId}/events`;
    const ts = new Date().toISOString();
    const payloadProjectId =
      (lastJobPayload && typeof lastJobPayload.project_id === "string"
        ? lastJobPayload.project_id
        : projects[0]?.project_id) || "";
    const kind = lastJobPayload?.kind;
    let heading = "Creating subtitles";
    let eventsBody = "";
    if (kind === "create_subtitles" && payloadProjectId) {
      subtitlesByProject.set(payloadProjectId, GENERATED_SRT);
      const target = projects.find((entry) => entry.project_id === payloadProjectId);
      if (target) {
        target.status = "ready";
      }
      heading = "Creating subtitles";
      eventsBody = [
        `event: message\ndata: ${JSON.stringify({ job_id: jobId, ts, type: "started", heading })}\n\n`,
        `event: message\ndata: ${JSON.stringify({ job_id: jobId, ts, type: "progress", pct: 100, message: "Done" })}\n\n`,
        `event: message\ndata: ${JSON.stringify({ job_id: jobId, ts, type: "completed", status: "completed" })}\n\n`
      ].join("");
    } else if (kind === "create_video_with_subtitles" && payloadProjectId) {
      const outputPath = "C:\\fake\\good_subtitled.mp4";
      const target = projects.find((entry) => entry.project_id === payloadProjectId);
      if (target) {
        target.status = "done";
        target.latest_export = {
          output_video_path: outputPath,
          exported_at: "2026-02-09T00:06:00Z"
        };
      }
      heading = "Creating video with subtitles";
      eventsBody = [
        `event: message\ndata: ${JSON.stringify({ job_id: jobId, ts, type: "started", heading })}\n\n`,
        `event: message\ndata: ${JSON.stringify({ job_id: jobId, ts, type: "checklist", step_id: "get_video_info", state: "done" })}\n\n`,
        `event: message\ndata: ${JSON.stringify({ job_id: jobId, ts, type: "checklist", step_id: "add_subtitles", state: "start" })}\n\n`,
        `event: message\ndata: ${JSON.stringify({ job_id: jobId, ts, type: "progress", pct: 55, message: "Adding subtitles to video" })}\n\n`,
        `event: message\ndata: ${JSON.stringify({ job_id: jobId, ts, type: "checklist", step_id: "add_subtitles", state: "done" })}\n\n`,
        `event: message\ndata: ${JSON.stringify({ job_id: jobId, ts, type: "checklist", step_id: "save_video", state: "done" })}\n\n`,
        `event: message\ndata: ${JSON.stringify({ job_id: jobId, ts, type: "result", payload: { output_path: outputPath } })}\n\n`,
        `event: message\ndata: ${JSON.stringify({ job_id: jobId, ts, type: "completed", status: "completed" })}\n\n`
      ].join("");
    } else {
      eventsBody = [
        `event: message\ndata: ${JSON.stringify({ job_id: jobId, ts, type: "started", heading })}\n\n`,
        `event: message\ndata: ${JSON.stringify({ job_id: jobId, ts, type: "completed", status: "completed" })}\n\n`
      ].join("");
    }
    eventsByJob.set(jobId, eventsBody);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ job_id: jobId, events_url: eventsUrl, status: "running" })
    });
  });

  await page.route("**://127.0.0.1:8765/jobs/*/events", async (route) => {
    const request = route.request();
    const jobId = getJobIdFromEventsUrl(request.url());
    await route.fulfill({
      status: 200,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache"
      },
      body:
        eventsByJob.get(jobId) ??
        `event: message\ndata: ${JSON.stringify({ job_id: jobId, ts: new Date().toISOString(), type: "completed", status: "completed" })}\n\n`
    });
  });

  await page.route("**://127.0.0.1:8765/jobs/*/cancel", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ok: true })
    });
  });

  return {
    getPutCallCount: () => putCallCount,
    getSubtitlePutCallCount: () => subtitlePutCallCount,
    getLastPutPayload: () => lastPutPayload,
    getLastJobPayload: () => lastJobPayload
  };
};

const primeVideoState = async (page, { playing = true, currentTime = 1 } = {}) => {
  await page.evaluate(
    ({ isPlaying, timeSeconds }) => {
      const video = document.querySelector("video");
      if (!video) {
        return;
      }
      const state = {
        paused: !isPlaying,
        pauseCalled: false,
        playCalled: false
      };
      Object.defineProperty(video, "__cueState", {
        configurable: true,
        value: state
      });
      Object.defineProperty(video, "paused", {
        configurable: true,
        get() {
          return video.__cueState.paused;
        }
      });
      video.pause = () => {
        video.__cueState.pauseCalled = true;
        video.__cueState.paused = true;
      };
      video.play = () => {
        video.__cueState.playCalled = true;
        video.__cueState.paused = false;
        return Promise.resolve();
      };
      video.currentTime = timeSeconds;
      video.dispatchEvent(new Event("timeupdate"));
    },
    { isPlaying: playing, timeSeconds: currentTime }
  );
};

test("workbench shell wide layout", async ({ page }) => {
  await page.setViewportSize({ width: 1300, height: 800 });
  const projects = buildProjects();
  await mockProjects(page, projects);

  await page.goto("/");
  await page.getByText("good.mp4").click();
  await page.waitForURL("**/workbench/project-1");

  await expect(page.getByTestId("workbench-center-panel")).toBeVisible();
  await expect(page.getByTestId("workbench-right-panel")).toBeVisible();
  await expect(page.getByTestId("workbench-left-drawer")).toHaveCount(0);
});

test("workbench shell narrow overlays", async ({ page }) => {
  await page.setViewportSize({ width: 900, height: 800 });
  const projects = buildProjects();
  await mockProjects(page, projects);

  await page.goto("/");
  await page.getByText("good.mp4").click();
  await page.waitForURL("**/workbench/project-1");

  await expect(page.getByTestId("workbench-right-panel")).toHaveCount(0);
  await expect(page.getByTestId("workbench-open-style")).toBeVisible();

  await page.getByTestId("workbench-open-style").click();
  await expect(page.getByTestId("workbench-right-drawer")).toBeVisible();
  await expect(page.getByTestId("workbench-overlay-scrim")).toBeVisible();

  await page.getByTestId("workbench-overlay-scrim").click();
  await expect(page.getByTestId("workbench-right-drawer")).toHaveCount(0);
});

test("workbench shows empty state before subtitles are created", async ({ page }) => {
  await page.setViewportSize({ width: 1300, height: 800 });
  const projects = buildProjects();
  await mockProjects(page, projects, null);

  await page.goto("/");
  await page.getByText("good.mp4").click();
  await page.waitForURL("**/workbench/project-1");

  await expect(page.getByTestId("workbench-empty-state")).toBeVisible();
  await expect(page.getByText("No subtitles yet.")).toBeVisible();
  await expect(page.getByTestId("workbench-create-subtitles")).toBeVisible();
  await expect(page.getByTestId("workbench-right-panel")).toHaveCount(0);
  await expect(page.getByTestId("workbench-open-style")).toHaveCount(0);
});

test("workbench creates subtitles from empty state", async ({ page }) => {
  await page.setViewportSize({ width: 1300, height: 800 });
  const projects = buildProjects();
  const api = await mockProjects(page, projects, null);

  await page.goto("/");
  await page.getByText("good.mp4").click();
  await page.waitForURL("**/workbench/project-1");

  const createRequest = page.waitForRequest(
    (request) => request.url().includes("/jobs") && request.method() === "POST"
  );
  await page.getByTestId("workbench-create-subtitles").click();
  await createRequest;

  await expect(page.getByTestId("workbench-empty-state")).toHaveCount(0);
  await expect(page.getByTestId("workbench-right-panel")).toBeVisible();
  expect(api.getLastJobPayload()?.project_id).toBe("project-1");
});

test("workbench exports video from the bottom action bar", async ({ page }) => {
  await page.setViewportSize({ width: 1300, height: 800 });
  const projects = buildProjects();
  projects[0].status = "ready";
  const api = await mockProjects(page, projects);

  await page.goto("/");
  await page.getByText("good.mp4").click();
  await page.waitForURL("**/workbench/project-1");

  await expect(page.getByTestId("workbench-export-panel")).toBeVisible();
  const exportCta = page.getByTestId("workbench-export-cta");
  await expect(exportCta).toBeEnabled();

  const exportRequest = page.waitForRequest(
    (request) => request.url().includes("/jobs") && request.method() === "POST"
  );
  await exportCta.click();
  const request = await exportRequest;
  const payload = request.postDataJSON() as {
    kind?: string;
    project_id?: string;
    output_dir?: string;
    srt_path?: string;
  };
  expect(payload.kind).toBe("create_video_with_subtitles");
  expect(payload.project_id).toBe("project-1");
  expect(payload.srt_path).toBeUndefined();

  await expect(page.getByTestId("workbench-play-export-video")).toBeVisible();
  await expect(page.getByTestId("workbench-open-export-folder")).toBeVisible();
  expect(api.getLastJobPayload()?.project_id).toBe("project-1");
});

test("new project auto-starts subtitle creation in Workbench", async ({ page }) => {
  await page.addInitScript(initMocks);
  await page.setViewportSize({ width: 1300, height: 800 });
  const projects = buildProjects();
  await mockProjects(page, projects, null);

  await page.goto("/");
  const createJobRequest = page.waitForRequest(
    (request) => request.url().includes("/jobs") && request.method() === "POST"
  );
  await page.getByTestId("new-project-input").setInputFiles({
    name: "fresh.mp4",
    mimeType: "video/mp4",
    buffer: Buffer.from("fake")
  });
  await page.waitForURL("**/workbench/project-new-1");
  const createRequest = await createJobRequest;
  const createPayload = createRequest.postDataJSON() as { kind?: string; project_id?: string };

  expect(createPayload.kind).toBe("create_subtitles");
  expect(createPayload.project_id).toBe("project-new-1");
  await expect(page.getByTestId("workbench-empty-state")).toHaveCount(0);
});

test("style controls change subtitle preview appearance", async ({ page }) => {
  await page.setViewportSize({ width: 1300, height: 800 });
  const projects = buildProjects();
  await mockProjects(page, projects);

  await page.goto("/");
  await page.getByText("good.mp4").click();
  await page.waitForURL("**/workbench/project-1");

  await primeVideoState(page, { playing: false, currentTime: 1.2 });
  const subtitleButton = page.getByTestId("workbench-active-subtitle");
  await expect(subtitleButton).toBeVisible();
  await expect
    .poll(async () =>
      page.evaluate(() => {
        const node = document.querySelector("[data-testid='workbench-active-subtitle']");
        if (!(node instanceof HTMLElement)) return "";
        return getComputedStyle(node).fontSize;
      })
    )
    .toBe("28px");

  const fontSizeInput = page
    .locator("label:has-text('Font size')")
    .locator("xpath=../../input[@type='number']");
  await fontSizeInput.fill("44");
  await fontSizeInput.blur();

  await expect
    .poll(async () =>
      page.evaluate(() => {
        const node = document.querySelector("[data-testid='workbench-active-subtitle']");
        if (!(node instanceof HTMLElement)) return "";
        return getComputedStyle(node).fontSize;
      })
    )
    .toBe("44px");
});

test("on-video contract saves subtitle with Enter", async ({ page }) => {
  await page.setViewportSize({ width: 1300, height: 800 });
  const projects = buildProjects();
  const api = await mockProjects(page, projects);

  await page.goto("/");
  await page.getByText("good.mp4").click();
  await page.waitForURL("**/workbench/project-1");

  await primeVideoState(page, { playing: true, currentTime: 1.2 });
  const subtitleButton = page.getByTestId("workbench-active-subtitle");
  await expect(subtitleButton).toBeVisible();
  await expect(subtitleButton).toContainText("Original subtitle line");

  await subtitleButton.click();
  await expect
    .poll(async () =>
      page.evaluate(() => Boolean(document.querySelector("video")?.__cueState?.pauseCalled))
    )
    .toBe(true);
  const editor = page.getByTestId("workbench-subtitle-editor");
  await expect(editor).toBeVisible();
  await editor.fill("Edited subtitle line");
  await editor.press("Enter");

  await expect(editor).toHaveCount(0);
  await expect(subtitleButton).toContainText("Edited subtitle line");
  await expect(subtitleButton).not.toHaveClass(/outline-primary/);
  expect(api.getSubtitlePutCallCount()).toBe(1);
  expect(api.getLastPutPayload()?.subtitles_srt_text ?? "").toContain("Edited subtitle line");
  await expect
    .poll(async () =>
      page.evaluate(() => Boolean(document.querySelector("video")?.__cueState?.playCalled))
    )
    .toBe(true);
});

test("on-video contract cancels edit with Escape", async ({ page }) => {
  await page.setViewportSize({ width: 1300, height: 800 });
  const projects = buildProjects();
  const api = await mockProjects(page, projects);

  await page.goto("/");
  await page.getByText("good.mp4").click();
  await page.waitForURL("**/workbench/project-1");

  await primeVideoState(page, { playing: true, currentTime: 1.2 });
  const subtitleButton = page.getByTestId("workbench-active-subtitle");
  await expect(subtitleButton).toBeVisible();
  await subtitleButton.click();

  const editor = page.getByTestId("workbench-subtitle-editor");
  await expect(editor).toBeVisible();
  await editor.fill("This should not save");
  await editor.press("Escape");

  await expect(editor).toHaveCount(0);
  await expect(subtitleButton).toContainText("Original subtitle line");
  await expect(subtitleButton).not.toHaveClass(/outline-primary/);
  expect(api.getSubtitlePutCallCount()).toBe(0);
  await expect
    .poll(async () =>
      page.evaluate(() => Boolean(document.querySelector("video")?.__cueState?.playCalled))
    )
    .toBe(true);
});

test("on-video contract saves subtitle with Save icon", async ({ page }) => {
  await page.setViewportSize({ width: 1300, height: 800 });
  const projects = buildProjects();
  const api = await mockProjects(page, projects);

  await page.goto("/");
  await page.getByText("good.mp4").click();
  await page.waitForURL("**/workbench/project-1");

  await primeVideoState(page, { playing: true, currentTime: 1.2 });
  const subtitleButton = page.getByTestId("workbench-active-subtitle");
  await subtitleButton.click();

  const editor = page.getByTestId("workbench-subtitle-editor");
  await expect(editor).toBeVisible();
  await editor.fill("Saved from icon button");
  await page.getByTestId("workbench-subtitle-save").click();

  await expect(editor).toHaveCount(0);
  await expect(subtitleButton).toContainText("Saved from icon button");
  await expect(subtitleButton).not.toHaveClass(/outline-primary/);
  expect(api.getSubtitlePutCallCount()).toBe(1);
  expect(api.getLastPutPayload()?.subtitles_srt_text ?? "").toContain("Saved from icon button");
  await expect
    .poll(async () =>
      page.evaluate(() => Boolean(document.querySelector("video")?.__cueState?.playCalled))
    )
    .toBe(true);
});

test("on-video contract cancels edit with Cancel icon", async ({ page }) => {
  await page.setViewportSize({ width: 1300, height: 800 });
  const projects = buildProjects();
  const api = await mockProjects(page, projects);

  await page.goto("/");
  await page.getByText("good.mp4").click();
  await page.waitForURL("**/workbench/project-1");

  await primeVideoState(page, { playing: true, currentTime: 1.2 });
  const subtitleButton = page.getByTestId("workbench-active-subtitle");
  await subtitleButton.click();

  const editor = page.getByTestId("workbench-subtitle-editor");
  await expect(editor).toBeVisible();
  await editor.fill("This should not save from icon");
  await page.getByTestId("workbench-subtitle-cancel").click();

  await expect(editor).toHaveCount(0);
  await expect(subtitleButton).toContainText("Original subtitle line");
  await expect(subtitleButton).not.toHaveClass(/outline-primary/);
  expect(api.getSubtitlePutCallCount()).toBe(0);
  await expect
    .poll(async () =>
      page.evaluate(() => Boolean(document.querySelector("video")?.__cueState?.playCalled))
    )
    .toBe(true);
});

test("on-video contract undo icon reverts unsaved edits", async ({ page }) => {
  await page.setViewportSize({ width: 1300, height: 800 });
  const projects = buildProjects();
  await mockProjects(page, projects);

  await page.goto("/");
  await page.getByText("good.mp4").click();
  await page.waitForURL("**/workbench/project-1");

  await primeVideoState(page, { playing: false, currentTime: 1.2 });
  await page.getByTestId("workbench-active-subtitle").click();

  const editor = page.getByTestId("workbench-subtitle-editor");
  const undoButton = page.getByTestId("workbench-subtitle-undo");
  await expect(editor).toBeVisible();
  await expect(undoButton).toBeDisabled();

  await editor.fill("First unsaved version");
  await expect(undoButton).toBeEnabled();
  await page.waitForTimeout(700);
  await editor.fill("Second unsaved version");

  await undoButton.click();
  await expect(editor).toHaveValue("First unsaved version");
  await undoButton.click();
  await expect(editor).toHaveValue("Original subtitle line");
});

test("on-video contract supports keyboard undo shortcut", async ({ page }) => {
  await page.setViewportSize({ width: 1300, height: 800 });
  const projects = buildProjects();
  await mockProjects(page, projects);

  await page.goto("/");
  await page.getByText("good.mp4").click();
  await page.waitForURL("**/workbench/project-1");

  await primeVideoState(page, { playing: false, currentTime: 1.2 });
  await page.getByTestId("workbench-active-subtitle").click();

  const editor = page.getByTestId("workbench-subtitle-editor");
  await expect(editor).toBeVisible();
  await editor.fill("Keyboard undo first");
  await page.waitForTimeout(700);
  await editor.fill("Keyboard undo second");
  await editor.press("ControlOrMeta+z");
  await expect(editor).toHaveValue("Keyboard undo first");
});

test("on-video editor controls render in dark theme", async ({ page }) => {
  await page.setViewportSize({ width: 1300, height: 800 });
  const projects = buildProjects();
  await mockProjects(page, projects);

  await page.goto("/");
  await page.getByText("good.mp4").click();
  await page.waitForURL("**/workbench/project-1");

  await page.evaluate(() => {
    document.documentElement.classList.add("dark");
  });

  await primeVideoState(page, { playing: false, currentTime: 1.2 });
  await page.getByTestId("workbench-active-subtitle").click();

  await expect(page.getByTestId("workbench-subtitle-editor")).toBeVisible();
  await expect(page.getByTestId("workbench-subtitle-undo")).toBeVisible();
  await expect(page.getByTestId("workbench-subtitle-cancel")).toBeVisible();
  await expect(page.getByTestId("workbench-subtitle-save")).toBeVisible();
});
