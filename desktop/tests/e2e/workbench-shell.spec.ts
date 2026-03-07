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

const initTauriRuntimeMock = () => {
  Object.defineProperty(globalThis, "isTauri", {
    configurable: true,
    value: true
  });
  Object.defineProperty(globalThis, "__TAURI_INTERNALS__", {
    configurable: true,
    value: {
      convertFileSrc: (filePath) => `data:,${encodeURIComponent(String(filePath ?? ""))}`,
      metadata: {
        currentWindow: { label: "main" },
        currentWebview: { windowLabel: "main", label: "main" }
      }
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
      position_x: 0.5,
      position_y: 0.92,
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
  style: project.style ?? DEFAULT_PROJECT_STYLE,
  active_task: project.active_task ?? null,
  task_notice: project.task_notice ?? null
});

const DEFAULT_SRT = "1\n00:00:00,000 --> 00:00:04,000\nOriginal subtitle line\n";
const GENERATED_SRT = "1\n00:00:00,000 --> 00:00:03,000\nGenerated subtitle line\n";
const LONG_HEBREW_SRT =
  "1\n00:00:00,000 --> 00:00:04,000\nאז אני רוצה ברשותכם להתחיל בקטע קצר כדי להדגים את שבירת השורה ולוודא שהטקסט נעטף לפחות לשתי שורות\n";

const getProjectIdFromUrl = (url) => url.split("/projects/")[1]?.split("/")[0] ?? "";
const getJobIdFromEventsUrl = (url) => url.split("/jobs/")[1]?.split("/")[0] ?? "";
const toSseBody = (events) =>
  events.map((event) => `event: message\ndata: ${JSON.stringify(event)}\n\n`).join("");

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
      position_x: 0.5,
      position_y: 0.92,
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
  const projectGetDelaysByProject = new Map();
  const eventRequestCounts = new Map();
  const eventFailureByJob = new Map();
  const projectGetCounts = new Map();

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

  await page.route("**://127.0.0.1:8765/preview-overlay", async (route) => {
    const request = route.request();
    if (request.method() !== "POST") {
      await route.continue();
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ overlay_path: "C:\\fake\\overlay_preview.png" })
    });
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

    if (request.method() === "DELETE") {
      projects = projects.filter((entry) => entry.project_id !== projectId);
      subtitlesByProject.delete(projectId);
      projectGetCounts.delete(projectId);
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ok: true, project_id: projectId, cancelled_job_ids: [] })
      });
      return;
    }

    if (request.method() !== "GET") {
      await route.continue();
      return;
    }
    projectGetCounts.set(projectId, (projectGetCounts.get(projectId) ?? 0) + 1);
    const delays = projectGetDelaysByProject.get(projectId);
    if (Array.isArray(delays) && delays.length > 0) {
      const delayMs = delays.shift();
      if (typeof delayMs === "number" && delayMs > 0) {
        await new Promise((resolve) => setTimeout(resolve, delayMs));
      }
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
    eventRequestCounts.set(jobId, (eventRequestCounts.get(jobId) ?? 0) + 1);
    const forcedFailure = eventFailureByJob.get(jobId);
    if (forcedFailure) {
      await route.fulfill({
        status: forcedFailure.status,
        contentType: forcedFailure.contentType ?? "application/json",
        body: forcedFailure.body
      });
      return;
    }
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
    getLastJobPayload: () => lastJobPayload,
    getProjectFetchCount: (projectId) => projectGetCounts.get(projectId) ?? 0,
    setProjectFields: (projectId, patch) => {
      projects = projects.map((entry) =>
        entry.project_id === projectId ? { ...entry, ...patch } : entry
      );
    },
    setProjectGetDelays: (projectId, delays) => {
      projectGetDelaysByProject.set(projectId, [...delays]);
    },
    setJobEvents: (jobId, events) => {
      eventsByJob.set(jobId, events);
    },
    setJobEventFailure: (jobId, status, body, contentType = "application/json") => {
      eventFailureByJob.set(jobId, { status, body, contentType });
    },
    clearJobEventFailure: (jobId) => {
      eventFailureByJob.delete(jobId);
    },
    getJobEventsRequestCount: (jobId) => eventRequestCounts.get(jobId) ?? 0
  };
};

const primeVideoState = async (
  page,
  { playing = true, currentTime = 1, videoWidth = 1280, videoHeight = 720 } = {}
) => {
  await page.evaluate(
    ({ isPlaying, timeSeconds, mediaWidth, mediaHeight }) => {
      const video = document.querySelector("video");
      if (!video) {
        return;
      }
      const state = {
        paused: !isPlaying,
        pauseCalled: false,
        playCalled: false,
        videoWidth: mediaWidth,
        videoHeight: mediaHeight
      };
      Object.defineProperty(video, "__cueState", {
        configurable: true,
        value: state
      });
      Object.defineProperty(video, "videoWidth", {
        configurable: true,
        get() {
          return video.__cueState.videoWidth;
        }
      });
      Object.defineProperty(video, "videoHeight", {
        configurable: true,
        get() {
          return video.__cueState.videoHeight;
        }
      });
      Object.defineProperty(video, "clientWidth", {
        configurable: true,
        get() {
          return video.__cueState.videoWidth;
        }
      });
      Object.defineProperty(video, "clientHeight", {
        configurable: true,
        get() {
          return video.__cueState.videoHeight;
        }
      });
      Object.defineProperty(video, "offsetWidth", {
        configurable: true,
        get() {
          return video.__cueState.videoWidth;
        }
      });
      Object.defineProperty(video, "offsetHeight", {
        configurable: true,
        get() {
          return video.__cueState.videoHeight;
        }
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
      const centerPanel = document.querySelector("[data-testid='workbench-center-panel']");
      if (centerPanel instanceof HTMLElement) {
        centerPanel.style.height = `${mediaHeight}px`;
      }
      const videoWrapper = document.querySelector("[data-testid='workbench-center-panel-video-wrapper']");
      if (videoWrapper instanceof HTMLElement) {
        videoWrapper.style.width = `${mediaWidth}px`;
        videoWrapper.style.height = `${mediaHeight}px`;
      }
      video.style.width = `${mediaWidth}px`;
      video.style.height = `${mediaHeight}px`;
      if (video.parentElement instanceof HTMLElement) {
        video.parentElement.style.width = `${mediaWidth}px`;
        video.parentElement.style.height = `${mediaHeight}px`;
      }
      video.currentTime = timeSeconds;
      video.dispatchEvent(new Event("loadedmetadata"));
      video.dispatchEvent(new Event("loadeddata"));
      video.dispatchEvent(new Event("timeupdate"));
    },
    { isPlaying: playing, timeSeconds: currentTime, mediaWidth: videoWidth, mediaHeight: videoHeight }
  );
};

const readClientRect = async (locator) =>
  locator.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    return {
      top: rect.top,
      left: rect.left,
      right: rect.right,
      bottom: rect.bottom,
      width: rect.width,
      height: rect.height
    };
  });

const readTypographyMetrics = async (locator) =>
  locator.evaluate((element) => {
    const style = window.getComputedStyle(element);
    return {
      fontFamily: style.fontFamily,
      fontSize: style.fontSize,
      lineHeight: style.lineHeight,
      letterSpacing: style.letterSpacing,
      direction: style.direction,
      boxSizing: style.boxSizing,
      paddingLeft: style.paddingLeft,
      paddingRight: style.paddingRight
    };
  });

const ensureSubtitleLayerReady = async (page) => {
  const layer = page.getByTestId("workbench-subtitle-overlay-position-layer");
  await expect(layer).toHaveCount(1);

  const initialRect = await readClientRect(layer);
  if (initialRect.width <= 10 || initialRect.height <= 10) {
    await page.evaluate(() => {
      const targetWidth = 960;
      const targetHeight = 540;
      const videoWrapper = document.querySelector("[data-testid='workbench-center-panel-video-wrapper']");
      if (videoWrapper instanceof HTMLElement) {
        videoWrapper.style.width = `${targetWidth}px`;
        videoWrapper.style.height = `${targetHeight}px`;
      }
      const layer = document.querySelector("[data-testid='workbench-subtitle-overlay-position-layer']");
      if (!(layer instanceof HTMLElement)) {
        return;
      }
      const host = layer.parentElement;
      if (host instanceof HTMLElement) {
        host.style.left = "0px";
        host.style.top = "0px";
        host.style.width = `${targetWidth}px`;
        host.style.height = `${targetHeight}px`;
      }
      layer.style.width = `${targetWidth}px`;
      layer.style.height = `${targetHeight}px`;
      const video = document.querySelector("video");
      if (video instanceof HTMLVideoElement) {
        video.dispatchEvent(new Event("loadedmetadata"));
      }
      window.dispatchEvent(new Event("resize"));
    });
  }

  await expect
    .poll(async () => {
      const rect = await readClientRect(layer);
      return rect.width > 10 && rect.height > 10;
    })
    .toBe(true);
  return layer;
};

const readActiveSubtitleRect = async (page) => {
  const rect = await page.evaluate(() => {
    const editor = document.querySelector("[data-workbench-subtitle-editor]");
    const preview = document.querySelector("[data-testid='workbench-active-subtitle']");
    const element =
      editor instanceof HTMLElement
        ? editor
        : preview instanceof HTMLElement
          ? preview
          : null;
    if (!element) {
      return null;
    }
    const nextRect = element.getBoundingClientRect();
    return {
      top: nextRect.top,
      left: nextRect.left,
      right: nextRect.right,
      bottom: nextRect.bottom,
      width: nextRect.width,
      height: nextRect.height
    };
  });
  if (!rect) {
    throw new Error("Active subtitle element not found");
  }
  return rect;
};

const dragActiveSubtitleTo = async (
  page,
  xNorm,
  yNorm,
  source: "preview" | "editor" = "preview"
) => {
  const layer = await ensureSubtitleLayerReady(page);
  const preview = page.getByTestId("workbench-active-subtitle");
  const editor = page.locator("[data-workbench-subtitle-editor]");
  const previewCount = await preview.count();
  const editorCount = await editor.count();
  const sourceLocator =
    source === "editor"
      ? editorCount > 0
        ? editor
        : preview
      : previewCount > 0
        ? preview
        : editor;

  const layerRect = await readClientRect(layer);
  const sourceRect = await readClientRect(sourceLocator);
  const moveHandle = page.locator("[data-subtitle-move-handle]").first();
  const moveHandleCount = await moveHandle.count();
  let dragStartX = sourceRect.left + sourceRect.width / 2;
  let dragStartY = sourceRect.top + sourceRect.height / 2;
  if (moveHandleCount > 0) {
    const handleRect = await readClientRect(moveHandle);
    if (handleRect.width > 0 && handleRect.height > 0) {
      dragStartX = handleRect.left + handleRect.width / 2;
      dragStartY = handleRect.top + handleRect.height / 2;
    }
  }
  await page.mouse.move(dragStartX, dragStartY);
  await page.mouse.down();
  await page.waitForTimeout(20);
  await page.mouse.move(
    layerRect.left + layerRect.width * xNorm,
    layerRect.top + layerRect.height * yNorm,
    { steps: 12 }
  );
  await page.mouse.up();
};

const dragActiveSubtitleFromCenterTo = async (
  page,
  xNorm,
  yNorm,
  source: "preview" | "editor" = "preview"
) => {
  const layer = await ensureSubtitleLayerReady(page);
  const preview = page.getByTestId("workbench-active-subtitle");
  const editor = page.locator("[data-workbench-subtitle-editor]");
  const previewCount = await preview.count();
  const editorCount = await editor.count();
  const sourceLocator =
    source === "editor"
      ? editorCount > 0
        ? editor
        : preview
      : previewCount > 0
        ? preview
        : editor;

  const layerRect = await readClientRect(layer);
  const sourceRect = await readClientRect(sourceLocator);
  const dragStart = await page.evaluate(({ rect }) => {
    const candidates = [
      { x: rect.left + rect.width * 0.5, y: rect.top + rect.height * 0.5 },
      { x: rect.left + rect.width * 0.4, y: rect.top + rect.height * 0.5 },
      { x: rect.left + rect.width * 0.6, y: rect.top + rect.height * 0.5 },
      { x: rect.left + rect.width * 0.5, y: rect.top + rect.height * 0.4 },
      { x: rect.left + rect.width * 0.5, y: rect.top + rect.height * 0.6 }
    ];
    for (const point of candidates) {
      const element = document.elementFromPoint(point.x, point.y);
      const onMoveHandle =
        element instanceof Element &&
        Boolean(element.closest("[data-subtitle-move-handle]"));
      if (!onMoveHandle) {
        return { ...point, onMoveHandle: false };
      }
    }
    const fallback = candidates[0];
    return { ...fallback, onMoveHandle: true };
  }, { rect: sourceRect });
  if (dragStart.onMoveHandle) {
    throw new Error("Could not find a center drag start point outside subtitle move handles");
  }
  const dragStartX = dragStart.x;
  const dragStartY = dragStart.y;
  await page.mouse.move(dragStartX, dragStartY);
  await page.mouse.down();
  await page.waitForTimeout(20);
  await page.mouse.move(
    layerRect.left + layerRect.width * xNorm,
    layerRect.top + layerRect.height * yNorm,
    { steps: 12 }
  );
  await page.mouse.up();
};

const dragResizeHandleByDeltaY = async (
  page,
  handleAriaLabel: string,
  deltaY: number
) => {
  const start = await page.evaluate((label) => {
    const selector = `[data-subtitle-resize-handle][aria-label="${label}"]`;
    const handle = document.querySelector(selector);
    if (!(handle instanceof HTMLElement)) {
      throw new Error(`Resize handle not found: ${label}`);
    }
    const rect = handle.getBoundingClientRect();
    const startX = rect.left + rect.width / 2;
    const startY = rect.top + rect.height / 2;
    handle.dispatchEvent(
      new MouseEvent("mousedown", {
        bubbles: true,
        cancelable: true,
        button: 0,
        buttons: 1,
        clientX: startX,
        clientY: startY
      })
    );
    return { x: startX, y: startY };
  }, handleAriaLabel);

  await page.waitForTimeout(50);

  await page.evaluate(
    ({ startX, startY, dy }) => {
      for (let step = 1; step <= 10; step += 1) {
        document.dispatchEvent(
          new MouseEvent("mousemove", {
            bubbles: true,
            cancelable: true,
            buttons: 1,
            clientX: startX,
            clientY: startY + (dy * step) / 10
          })
        );
      }
      document.dispatchEvent(
        new MouseEvent("mouseup", {
          bubbles: true,
          cancelable: true,
          button: 0,
          buttons: 0,
          clientX: startX,
          clientY: startY + dy
        })
      );
    },
    { startX: start.x, startY: start.y, dy: deltaY }
  );
};


const ensureAdvancedStyleControlsVisible = async (page) => {
  const fontLabel = page.locator("label:has-text('Font')");
  if ((await fontLabel.count()) > 0 && (await fontLabel.isVisible())) {
    return;
  }
  const openStyleButton = page.getByTestId("workbench-open-style");
  if ((await openStyleButton.count()) > 0 && (await openStyleButton.isVisible())) {
    await openStyleButton.click();
  }
  const advancedButton = page.getByRole("button", { name: "Advanced" });
  if ((await advancedButton.count()) === 0) {
    return;
  }
  await advancedButton.click();
  await expect(fontLabel).toBeVisible();
};

/** No-op: vertical position is now set by dragging the subtitle on the video. */
const setVerticalAnchor = async (_page, _anchorLabel: "Top" | "Middle" | "Bottom") => {};

/** No-op: vertical position is now set by dragging the subtitle on the video. */
const setVerticalOffset = async (_page, _value: string) => {};

const showVideoControls = async (page) => {
  const readControlsOpacity = async () =>
    page.getByTestId("workbench-video-controls").evaluate((element) => {
      const opacity = Number.parseFloat(window.getComputedStyle(element).opacity);
      return Number.isFinite(opacity) ? opacity : 0;
    });

  const waitUntilVisible = async (timeout: number) => {
    await expect.poll(readControlsOpacity, { timeout }).toBeGreaterThan(0.95);
  };

  const subtitleButton = page.getByTestId("workbench-active-subtitle");
  if ((await subtitleButton.count()) > 0) {
    await subtitleButton.first().hover();
  } else {
    const editor = page.locator("[data-workbench-subtitle-editor]");
    if ((await editor.count()) > 0) {
      await editor.first().hover();
    }
  }

  try {
    await waitUntilVisible(1200);
    return;
  } catch {
    // Fallback for mocked-video cases where hover does not trigger enter handlers reliably.
  }

  await primeVideoState(page, { playing: false, currentTime: 1.2 });
  const layer = await ensureSubtitleLayerReady(page);
  const layerRect = await readClientRect(layer);
  const sourceRect = await readActiveSubtitleRect(page);
  await page.mouse.move(sourceRect.left + sourceRect.width / 2, sourceRect.top + sourceRect.height / 2);
  await page.mouse.down();
  await page.mouse.move(layerRect.left + layerRect.width / 2 + 3, layerRect.top + layerRect.height / 2 + 3, {
    steps: 6
  });
  await page.mouse.up();

  await waitUntilVisible(5000);
};

const expectVideoControlsHiddenSoon = async (page) => {
  await expect
    .poll(
      async () =>
        page.getByTestId("workbench-video-controls").evaluate((element) => {
          const opacity = Number.parseFloat(window.getComputedStyle(element).opacity);
          return Number.isFinite(opacity) ? opacity : 1;
        }),
      { timeout: 1200 }
    )
    .toBeLessThan(0.05);
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

test("title bar: switch between Home and video tab", async ({ page }) => {
  await page.addInitScript(initTauriRuntimeMock);
  await page.setViewportSize({ width: 900, height: 800 });
  const projects = buildProjects();
  projects[0].status = "ready";
  projects.push({
    ...buildProjects()[0],
    project_id: "project-2",
    title: "other.mp4",
    video_path: "C:\\fake\\other.mp4",
    status: "ready"
  });
  await mockProjects(page, projects);

  await page.goto("/");
  await page.getByText("good.mp4").click();
  await page.waitForURL("**/workbench/project-1");
  await expect(page.getByTestId("workbench-heading")).toBeVisible();
  await expect(page.getByTestId("title-bar-tab-project-1")).toBeVisible();

  await page.getByTestId("title-bar-home").click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: "Videos" })).toBeVisible();

  await page.getByText("other.mp4").click();
  await page.waitForURL("**/workbench/project-2");
  await expect(page.getByTestId("workbench-heading")).toContainText("other");
  await expect(page.getByTestId("title-bar-tab-project-1")).toBeVisible();
  await expect(page.getByTestId("title-bar-tab-project-2")).toBeVisible();

  await page.getByTestId("title-bar-tab-project-1").click();
  await expect(page).toHaveURL(/\/workbench\/project-1/);
  await expect(page.getByTestId("workbench-heading")).toContainText("good");
});

test("navigation without sidebar: Projects to Editor to Home via title bar", async ({
  page
}) => {
  await page.addInitScript(initTauriRuntimeMock);
  const projects = buildProjects();
  await mockProjects(page, projects);

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Videos" })).toBeVisible();
  await page.getByText("good.mp4").click();
  await page.waitForURL(/\/workbench\/project-1/);
  await expect(page.getByTestId("workbench")).toBeVisible();

  await page.getByTestId("title-bar-home").click();
  await expect(page.getByRole("heading", { name: "Videos" })).toBeVisible();
  await expect(page).toHaveURL(/\/$/);
});

test("title bar: close active tab switches to adjacent or Home", async ({ page }) => {
  await page.addInitScript(initTauriRuntimeMock);
  await page.setViewportSize({ width: 900, height: 800 });
  const projects = buildProjects();
  projects[0].status = "ready";
  projects.push({
    ...buildProjects()[0],
    project_id: "project-2",
    title: "other.mp4",
    video_path: "C:\\fake\\other.mp4",
    status: "ready"
  });
  await mockProjects(page, projects);

  await page.goto("/");
  await page.getByText("good.mp4").click();
  await page.waitForURL("**/workbench/project-1");
  await page.getByTestId("title-bar-home").click();
  await expect(page).toHaveURL(/\/$/);
  await page.getByText("other.mp4").click();
  await page.waitForURL("**/workbench/project-2");

  await page.getByTestId("title-bar-tab-close-project-2").click();
  await expect(page).toHaveURL(/\/workbench\/project-1/);
  await expect(page.getByTestId("title-bar-tab-project-1")).toBeVisible();
  await expect(page.getByTestId("title-bar-tab-project-2")).toHaveCount(0);

  await page.getByTestId("title-bar-tab-close-project-1").click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: "Videos" })).toBeVisible();
  await expect(page.getByTestId("title-bar-tab-project-1")).toHaveCount(0);
});

test("title bar: close non-active tab removes tab without navigation", async ({
  page
}) => {
  await page.addInitScript(initTauriRuntimeMock);
  await page.setViewportSize({ width: 900, height: 800 });
  const projects = buildProjects();
  projects[0].status = "ready";
  projects.push({
    ...buildProjects()[0],
    project_id: "project-2",
    title: "other.mp4",
    video_path: "C:\\fake\\other.mp4",
    status: "ready"
  });
  await mockProjects(page, projects);

  await page.goto("/");
  await page.getByText("good.mp4").click();
  await page.waitForURL("**/workbench/project-1");
  await page.getByTestId("title-bar-home").click();
  await expect(page).toHaveURL(/\/$/);
  await page.getByText("other.mp4").click();
  await page.waitForURL("**/workbench/project-2");

  await page.getByTestId("title-bar-tab-close-project-1").click();
  await expect(page).toHaveURL(/\/workbench\/project-2/);
  await expect(page.getByTestId("workbench-heading")).toContainText("other");
  await expect(page.getByTestId("title-bar-tab-project-1")).toHaveCount(0);
  await expect(page.getByTestId("title-bar-tab-project-2")).toBeVisible();
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

test("workbench exports video from the top bar", async ({ page }) => {
  await page.setViewportSize({ width: 1300, height: 800 });
  const projects = buildProjects();
  projects[0].status = "ready";
  const api = await mockProjects(page, projects);

  await page.goto("/");
  await page.getByText("good.mp4").click();
  await page.waitForURL("**/workbench/project-1");

  const exportCta = page.getByTestId("workbench-export-cta");
  await expect(exportCta).toBeVisible();
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

test("workbench resumes create progress with inline checklist detail and elapsed header", async ({
  page
}) => {
  await page.setViewportSize({ width: 1300, height: 800 });
  const projects = buildProjects();
  const startedAt = new Date(Date.now() - 15_000).toISOString();
  const ts = new Date().toISOString();
  projects[0].active_task = {
    job_id: "job-resume-create",
    kind: "create_subtitles",
    status: "running",
    heading: "Creating subtitles",
    message: "Warmup",
    pct: 12,
    step_id: "load_model",
    started_at: startedAt,
    updated_at: ts,
    checklist: [
      {
        id: "load_model",
        label: "Loading AI model",
        state: "active",
        detail: "Initializing"
      }
    ]
  };
  const api = await mockProjects(page, projects, null);
  api.setJobEvents(
    "job-resume-create",
    toSseBody([
      { job_id: "job-resume-create", ts, type: "started", heading: "Creating subtitles" },
      {
        job_id: "job-resume-create",
        ts,
        type: "progress",
        step_id: "load_model",
        pct: 19,
        message: "Warming up engine"
      }
    ])
  );

  await page.goto("/");
  await page.getByText("good.mp4").click();
  await page.waitForURL("**/workbench/project-1");

  // Project fetch + effect to set isCreatingSubtitles can take a moment
  await expect(page.getByTestId("workbench-cancel-create-subtitles")).toBeVisible({
    timeout: 10000
  });
  await expect(page.getByTestId("workbench-create-elapsed")).toContainText("Elapsed");
  await expect(page.getByTestId("workbench-create-elapsed")).not.toContainText("Warming up engine");
  const checklistRow = page.locator("[data-testid='workbench-create-checklist'] p").first();
  await expect(checklistRow).toBeVisible();
  // Checklist shows create-subtitles progress (exact text depends on stream/default steps)
  await expect(checklistRow).toContainText(/Loading AI model|Extracting audio|Warming up/);
});

test("workbench falls back to project polling when resumed create stream attach fails", async ({
  page
}) => {
  await page.setViewportSize({ width: 1300, height: 800 });
  const projects = buildProjects();
  const startedAt = new Date(Date.now() - 9_000).toISOString();
  const ts = new Date().toISOString();
  projects[0].active_task = {
    job_id: "job-resume-fail",
    kind: "create_subtitles",
    status: "running",
    heading: "Creating subtitles",
    message: "Connecting",
    pct: 5,
    step_id: "load_model",
    started_at: startedAt,
    updated_at: ts,
    checklist: [
      {
        id: "load_model",
        label: "Loading AI model",
        state: "active",
        detail: "Connecting stream"
      }
    ]
  };
  const api = await mockProjects(page, projects, null);
  let resumeAttachRequested = false;
  await page.route("**://127.0.0.1:8765/jobs/job-resume-fail/events", async (route) => {
    resumeAttachRequested = true;
    api.setProjectFields("project-1", {
      active_task: null,
      task_notice: {
        notice_id: "notice-resume-fail",
        project_id: "project-1",
        job_id: "job-resume-fail",
        kind: "create_subtitles",
        status: "error",
        message: "Runner disconnected while resuming.",
        created_at: new Date().toISOString(),
        finished_at: new Date().toISOString()
      }
    });
    await route.fulfill({ status: 500, body: "stream unavailable" });
  });

  await page.goto("/");
  await page.getByText("good.mp4").click();
  await page.waitForURL("**/workbench/project-1");

  await expect.poll(() => resumeAttachRequested).toBe(true);
  await expect.poll(() => api.getProjectFetchCount("project-1")).toBeGreaterThan(1);
  await expect(page.getByText("Runner disconnected while resuming.")).toBeVisible();
  await expect(page.getByTestId("workbench-create-subtitles")).toBeVisible();
});

test("workbench reattach cooldown throttles repeated create stream failures", async ({ page }) => {
  await page.setViewportSize({ width: 1300, height: 800 });
  const projects = buildProjects();
  const ts = new Date().toISOString();
  projects[0].active_task = {
    job_id: "job-reattach-throttle",
    kind: "create_subtitles",
    status: "running",
    heading: "Creating subtitles",
    message: "Waiting for stream",
    pct: 0,
    step_id: "extract_audio",
    started_at: ts,
    updated_at: ts,
    checklist: [
      {
        id: "extract_audio",
        label: "Extracting audio",
        state: "active",
        detail: "Starting"
      }
    ]
  };
  const api = await mockProjects(page, projects, null);
  api.setJobEventFailure(
    "job-reattach-throttle",
    409,
    JSON.stringify({ error: "sse_client_already_connected", job_id: "job-reattach-throttle" })
  );

  await page.goto("/");
  await page.getByText("good.mp4").click();
  await page.waitForURL("**/workbench/project-1");

  await expect(page.getByTestId("workbench-cancel-create-subtitles")).toBeVisible();
  await page.waitForTimeout(6500);
  await expect.poll(() => api.getProjectFetchCount("project-1")).toBeGreaterThan(1);
  await expect.poll(() => api.getJobEventsRequestCount("job-reattach-throttle")).toBeLessThanOrEqual(2);
  await expect(page.getByTestId("workbench-cancel-create-subtitles")).toBeVisible();
});

test("workbench keeps live create progress when snapshot updated_at is stale", async ({ page }) => {
  await page.setViewportSize({ width: 1300, height: 800 });
  const projects = buildProjects();
  const startedAt = new Date(Date.now() - 20_000).toISOString();
  const staleTs = new Date(Date.now() - 10_000).toISOString();
  const liveTs = new Date().toISOString();
  projects[0].active_task = {
    job_id: "job-snapshot-precedence",
    kind: "create_subtitles",
    status: "running",
    heading: "Creating subtitles",
    message: "Snapshot stale",
    pct: 5,
    step_id: "load_model",
    started_at: startedAt,
    updated_at: staleTs,
    checklist: [
      {
        id: "load_model",
        label: "Loading AI model",
        state: "active",
        detail: "Snapshot stale detail"
      }
    ]
  };
  const api = await mockProjects(page, projects, null);
  api.setProjectGetDelays("project-1", [0, 700]);
  api.setJobEvents(
    "job-snapshot-precedence",
    toSseBody([
      {
        job_id: "job-snapshot-precedence",
        ts: liveTs,
        type: "started",
        heading: "Creating subtitles"
      },
      {
        job_id: "job-snapshot-precedence",
        ts: liveTs,
        type: "progress",
        step_id: "load_model",
        pct: 42,
        message: "Live stream update"
      }
    ])
  );

  await page.goto("/");
  await page.getByText("good.mp4").click();
  await page.waitForURL("**/workbench/project-1");

  await expect(page.getByTestId("workbench-cancel-create-subtitles")).toBeVisible();
  await expect(page.getByTestId("workbench-create-elapsed")).toHaveAttribute(
    "title",
    "Live stream update"
  );
  await expect.poll(() => api.getProjectFetchCount("project-1")).toBeGreaterThan(1);
  await expect(page.getByText("42%")).toBeVisible();
});

test("workbench timing fallback shows incremental words from ALIGN_WORDS progress", async ({
  page
}) => {
  await page.setViewportSize({ width: 1300, height: 800 });
  const projects = buildProjects();
  const ts = new Date().toISOString();
  projects[0].active_task = {
    job_id: "job-timing-fallback",
    kind: "create_subtitles",
    status: "running",
    heading: "Creating subtitles",
    message: "Building word-by-word karaoke effect",
    pct: 18,
    step_id: "timing_word_highlights",
    started_at: ts,
    updated_at: ts,
    checklist: [
      {
        id: "timing_word_highlights",
        label: "Building word-by-word karaoke effect",
        state: "active",
        detail: "0/100 words"
      }
    ]
  };
  const api = await mockProjects(page, projects, null);
  api.setJobEvents(
    "job-timing-fallback",
    toSseBody([
      {
        job_id: "job-timing-fallback",
        ts,
        type: "started",
        heading: "Creating subtitles"
      },
      {
        job_id: "job-timing-fallback",
        ts: new Date(Date.now() + 1000).toISOString(),
        type: "progress",
        step_id: "ALIGN_WORDS",
        step_progress: 0.35,
        pct: 35,
        message: "Building word-by-word karaoke effect"
      }
    ])
  );

  await page.goto("/");
  await page.getByText("good.mp4").click();
  await page.waitForURL("**/workbench/project-1");

  await expect(page.getByTestId("workbench-cancel-create-subtitles")).toBeVisible();
  await expect(
    page.locator("[data-testid='workbench-create-checklist']").getByText("35/100 words")
  ).toBeVisible();
});

test("workbench timing fallback ignores stale snapshot detail with newer updated_at", async ({
  page
}) => {
  await page.setViewportSize({ width: 1300, height: 800 });
  const projects = buildProjects();
  const startedAt = new Date(Date.now() - 8_000).toISOString();
  const streamTs = new Date(Date.now() - 4_000).toISOString();
  const activeTask = {
    job_id: "job-timing-fallback-stale",
    kind: "create_subtitles",
    status: "running",
    heading: "Creating subtitles",
    message: "Building word-by-word karaoke effect",
    pct: 18,
    step_id: "timing_word_highlights",
    started_at: startedAt,
    updated_at: startedAt,
    checklist: [
      {
        id: "timing_word_highlights",
        label: "Building word-by-word karaoke effect",
        state: "active",
        detail: "0/100 words"
      }
    ]
  };
  projects[0].active_task = activeTask;
  const api = await mockProjects(page, projects, null);
  api.setJobEvents(
    "job-timing-fallback-stale",
    toSseBody([
      {
        job_id: "job-timing-fallback-stale",
        ts: streamTs,
        type: "started",
        heading: "Creating subtitles"
      },
      {
        job_id: "job-timing-fallback-stale",
        ts: new Date(Date.now() - 3_000).toISOString(),
        type: "progress",
        step_id: "ALIGN_WORDS",
        step_progress: 0.35,
        pct: 35,
        message: "Building word-by-word karaoke effect"
      }
    ])
  );

  await page.goto("/");
  await page.getByText("good.mp4").click();
  await page.waitForURL("**/workbench/project-1");

  const checklist = page.locator("[data-testid='workbench-create-checklist']");
  await expect(page.getByTestId("workbench-cancel-create-subtitles")).toBeVisible();
  await expect(checklist.getByText("35/100 words")).toBeVisible();

  const fetchCountBeforeSnapshotRefresh = api.getProjectFetchCount("project-1");
  api.setProjectFields("project-1", {
    active_task: {
      ...activeTask,
      pct: 35,
      updated_at: new Date(Date.now() + 60_000).toISOString()
    }
  });

  await expect
    .poll(() => api.getProjectFetchCount("project-1"))
    .toBeGreaterThan(fetchCountBeforeSnapshotRefresh);
  await expect(checklist.getByText("35/100 words")).toBeVisible();
  await expect(checklist).not.toContainText("0/100 words");
});

test("workbench shows Queued and cancel when project active_task is queued", async ({ page }) => {
  await page.setViewportSize({ width: 1300, height: 800 });
  const projects = buildProjects();
  const ts = new Date().toISOString();
  (projects[0] as { active_task?: object }).active_task = {
    job_id: "job-queued-1",
    kind: "create_subtitles",
    status: "queued",
    heading: "Queued",
    started_at: ts,
    updated_at: ts
  };
  const api = await mockProjects(page, projects, null);
  api.setJobEvents("job-queued-1", toSseBody([]));

  await page.goto("/");
  await page.getByText("good.mp4").click();
  await page.waitForURL("**/workbench/project-1");

  await expect(page.getByText("Queued")).toBeVisible();
  await expect(page.getByTestId("workbench-cancel-create-subtitles")).toBeVisible();

  const cancelRequest = page.waitForRequest(
    (request) =>
      request.url().includes("/jobs/job-queued-1/cancel") && request.method() === "POST"
  );
  await page.getByTestId("workbench-cancel-create-subtitles").click();
  await cancelRequest;
});

test("workbench keeps export cancel available after resume attach", async ({ page }) => {
  await page.setViewportSize({ width: 1300, height: 800 });
  const projects = buildProjects();
  projects[0].status = "ready";
  const startedAt = new Date(Date.now() - 11_000).toISOString();
  const ts = new Date().toISOString();
  projects[0].active_task = {
    job_id: "job-resume-export",
    kind: "create_video_with_subtitles",
    status: "running",
    heading: "Exporting video",
    message: "Muxing frames",
    pct: 61,
    step_id: "save_video",
    started_at: startedAt,
    updated_at: ts,
    checklist: [
      {
        id: "save_video",
        label: "Saving video",
        state: "active",
        detail: "Writing final file"
      }
    ]
  };
  const api = await mockProjects(page, projects);
  api.setJobEvents(
    "job-resume-export",
    toSseBody([
      { job_id: "job-resume-export", ts, type: "started", heading: "Exporting video" },
      {
        job_id: "job-resume-export",
        ts,
        type: "progress",
        step_id: "save_video",
        pct: 63,
        message: "Muxing frames"
      }
    ])
  );

  await page.goto("/");
  await page.getByText("good.mp4").click();
  await page.waitForURL("**/workbench/project-1");

  await expect(page.getByTestId("workbench-cancel-export")).toBeVisible();
  await expect(page.getByTestId("workbench-export-elapsed")).toContainText("Elapsed");
  await expect(page.getByTestId("workbench-export-elapsed")).not.toContainText("Muxing frames");
  const cancelRequest = page.waitForRequest(
    (request) => request.url().includes("/jobs/job-resume-export/cancel") && request.method() === "POST"
  );
  await page.getByTestId("workbench-cancel-export").click();
  await cancelRequest;
});

test("workbench does not show export error banner on cancelled export event", async ({
  page
}) => {
  await page.setViewportSize({ width: 1300, height: 800 });
  const projects = buildProjects();
  projects[0].status = "ready";
  const startedAt = new Date(Date.now() - 11_000).toISOString();
  const ts = new Date().toISOString();
  projects[0].active_task = {
    job_id: "job-export-cancel-stream",
    kind: "create_video_with_subtitles",
    status: "running",
    heading: "Exporting video",
    message: "Muxing frames",
    pct: 61,
    step_id: "save_video",
    started_at: startedAt,
    updated_at: ts,
    checklist: [
      {
        id: "save_video",
        label: "Saving video",
        state: "active",
        detail: "Writing final file"
      }
    ]
  };
  const api = await mockProjects(page, projects);
  api.setJobEvents(
    "job-export-cancel-stream",
    toSseBody([
      { job_id: "job-export-cancel-stream", ts, type: "started", heading: "Exporting video" },
      {
        job_id: "job-export-cancel-stream",
        ts,
        type: "cancelled",
        status: "cancelled",
        message: "Operation cancelled."
      }
    ])
  );

  await page.goto("/");
  await page.getByText("good.mp4").click();
  await page.waitForURL("**/workbench/project-1");

  await expect(page.getByTestId("workbench-export-cta")).toBeVisible();
  await expect(page.getByText("Operation cancelled.")).toHaveCount(0);
});

test("cancel create subtitles returns home, removes the project, and shows no cancel toast", async ({
  page
}) => {
  await page.setViewportSize({ width: 1300, height: 800 });
  const projects = buildProjects();
  const startedAt = new Date(Date.now() - 12_000).toISOString();
  const ts = new Date().toISOString();
  projects[0].active_task = {
    job_id: "job-cancel-create-1",
    kind: "create_subtitles",
    status: "running",
    heading: "Creating subtitles",
    message: "Loading model",
    pct: 21,
    step_id: "load_model",
    started_at: startedAt,
    updated_at: ts,
    checklist: [
      {
        id: "load_model",
        label: "Loading AI model",
        state: "active"
      }
    ]
  };
  const api = await mockProjects(page, projects, null);
  api.setJobEvents(
    "job-cancel-create-1",
    toSseBody([
      { job_id: "job-cancel-create-1", ts, type: "started", heading: "Creating subtitles" },
      {
        job_id: "job-cancel-create-1",
        ts,
        type: "progress",
        step_id: "load_model",
        pct: 23,
        message: "Loading model"
      }
    ])
  );

  await page.goto("/");
  await page.getByText("good.mp4").click();
  await page.waitForURL("**/workbench/project-1");
  await expect(page.getByTestId("workbench-cancel-create-subtitles")).toBeVisible();

  const cancelRequest = page.waitForRequest(
    (request) =>
      request.url().includes("/jobs/job-cancel-create-1/cancel") &&
      request.method() === "POST"
  );
  const deleteRequest = page.waitForRequest(
    (request) => request.url().includes("/projects/project-1") && request.method() === "DELETE"
  );
  await page.getByTestId("workbench-cancel-create-subtitles").click();

  await page.waitForURL("**/");
  await cancelRequest;
  await deleteRequest;
  await expect(page.getByTestId("project-card-project-1")).toHaveCount(0);
  await expect(
    page.getByRole("status").filter({ hasText: "Task cancelled: Operation cancelled." })
  ).toHaveCount(0);
});

test("app layout suppresses export-cancel task notices from toast polling", async ({ page }) => {
  await page.setViewportSize({ width: 1300, height: 800 });
  const now = new Date().toISOString();
  const projects = [
    {
      ...buildProjects()[0],
      status: "ready",
      task_notice: {
        notice_id: "notice-export-cancel",
        project_id: "project-1",
        job_id: "job-export-cancel-1",
        kind: "create_video_with_subtitles",
        status: "cancelled",
        message: "Operation cancelled.",
        created_at: now,
        finished_at: now
      }
    },
    {
      project_id: "project-2",
      title: "other.mp4",
      video_path: "C:\\fake\\other.mp4",
      missing_video: false,
      status: "ready",
      created_at: "2026-02-09T00:00:00Z",
      updated_at: "2026-02-09T00:00:00Z",
      duration_seconds: 42,
      thumbnail_path: "",
      latest_export: null,
      task_notice: {
        notice_id: "notice-error-other",
        project_id: "project-2",
        job_id: "job-error-other",
        kind: "create_subtitles",
        status: "error",
        message: "Background subtitle run failed.",
        created_at: now,
        finished_at: now
      }
    }
  ];
  await mockProjects(page, projects);

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Videos" })).toBeVisible();
  await expect(page.getByTestId("project-card-task-notice-project-1")).toHaveCount(0);
  await expect(page.getByText("Operation cancelled.")).toHaveCount(0);
  await expect(
    page.getByRole("status").filter({ hasText: "Task failed: Background subtitle run failed." })
  ).toBeVisible();
  await expect(
    page.getByRole("status").filter({ hasText: "Task cancelled: Operation cancelled." })
  ).toHaveCount(0);
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
  const api = await mockProjects(page, projects);

  await page.goto("/");
  await page.getByText("good.mp4").click();
  await page.waitForURL("**/workbench/project-1");

  await primeVideoState(page, { playing: false, currentTime: 1.2 });
  const subtitleButton = page.getByTestId("workbench-active-subtitle");
  await expect(subtitleButton).toHaveCount(1);

  const fontSizeInput = page
    .locator("label:has-text('Font size')")
    .locator("xpath=../../input[@type='number']");
  await fontSizeInput.fill("44");
  await fontSizeInput.blur();

  await expect
    .poll(() => {
      const payload = api.getLastPutPayload();
      const style = payload?.style?.subtitle_style?.appearance;
      return style?.font_size ?? null;
    })
    .toBe(44);
});

test("subtitle width stays stable when dragging horizontally", async ({ page }) => {
  await page.setViewportSize({ width: 1300, height: 800 });
  const projects = buildProjects();
  await mockProjects(page, projects);

  await page.goto("/");
  await page.getByText("good.mp4").click();
  await page.waitForURL("**/workbench/project-1");

  await primeVideoState(page, { playing: false, currentTime: 1.2 });
  const subtitleButton = page.getByTestId("workbench-active-subtitle");
  await expect(subtitleButton).toHaveCount(1);
  await ensureSubtitleLayerReady(page);

  await dragActiveSubtitleTo(page, 0.5, 0.75);
  await page.waitForTimeout(40);
  const centerRect = await readActiveSubtitleRect(page);

  await dragActiveSubtitleTo(page, 0.9, 0.75);
  await page.waitForTimeout(40);
  const rightRect = await readActiveSubtitleRect(page);

  await dragActiveSubtitleTo(page, 0.1, 0.75);
  await page.waitForTimeout(40);
  const leftRect = await readActiveSubtitleRect(page);

  const maxWidthDelta = Math.max(
    Math.abs(centerRect.width - rightRect.width),
    Math.abs(centerRect.width - leftRect.width),
    Math.abs(rightRect.width - leftRect.width)
  );
  expect(maxWidthDelta).toBeLessThanOrEqual(1);
});

test("subtitle corner handles resize text", async ({ page }) => {
  await page.setViewportSize({ width: 1300, height: 800 });
  const projects = buildProjects();
  await mockProjects(page, projects);

  await page.goto("/");
  await page.getByText("good.mp4").click();
  await page.waitForURL("**/workbench/project-1");

  await primeVideoState(page, { playing: false, currentTime: 1.2 });
  const subtitleButton = page.getByTestId("workbench-active-subtitle");
  await expect(subtitleButton).toHaveCount(1);
  await subtitleButton.click();

  const editor = page.getByTestId("workbench-subtitle-editor");
  await expect(editor).toHaveCount(1);

  const topLeftHandle = page.locator(
    "[data-subtitle-resize-handle][aria-label='Resize subtitle from top-left']"
  );
  await expect(topLeftHandle).toHaveCount(1);
  const bottomRightHandle = page.locator(
    "[data-subtitle-resize-handle][aria-label='Resize subtitle from bottom-right']"
  );
  await expect(bottomRightHandle).toHaveCount(1);

  const beforeFontSizePx = Number.parseFloat((await readTypographyMetrics(editor)).fontSize);
  expect(Number.isFinite(beforeFontSizePx)).toBe(true);

  await dragResizeHandleByDeltaY(page, "Resize subtitle from top-left", -80);
  await page.waitForTimeout(80);

  const afterFontSizePx = Number.parseFloat((await readTypographyMetrics(editor)).fontSize);
  expect(Number.isFinite(afterFontSizePx)).toBe(true);
  expect(afterFontSizePx).toBeGreaterThan(beforeFontSizePx + 2);

  const beforeBottomDragFontSizePx = afterFontSizePx;
  await dragResizeHandleByDeltaY(page, "Resize subtitle from bottom-right", 80);
  await page.waitForTimeout(80);

  const afterBottomDragFontSizePx = Number.parseFloat((await readTypographyMetrics(editor)).fontSize);
  expect(Number.isFinite(afterBottomDragFontSizePx)).toBe(true);
  expect(afterBottomDragFontSizePx).toBeGreaterThan(beforeBottomDragFontSizePx + 2);
});

test("subtitle move starts only from border handles", async ({ page }) => {
  await page.setViewportSize({ width: 1300, height: 800 });
  const projects = buildProjects();
  await mockProjects(page, projects);

  await page.goto("/");
  await page.getByText("good.mp4").click();
  await page.waitForURL("**/workbench/project-1");

  await primeVideoState(page, { playing: false, currentTime: 1.2 });
  const subtitleButton = page.getByTestId("workbench-active-subtitle");
  await expect(subtitleButton).toHaveCount(1);
  await ensureSubtitleLayerReady(page);

  await dragActiveSubtitleTo(page, 0.5, 0.6);
  await page.waitForTimeout(40);

  await subtitleButton.click();
  const editor = page.getByTestId("workbench-subtitle-editor");
  await expect(editor).toHaveCount(1);

  const beforeInsideDrag = await readActiveSubtitleRect(page);
  await dragActiveSubtitleFromCenterTo(page, 0.9, 0.2, "editor");
  await page.waitForTimeout(40);
  const afterInsideDrag = await readActiveSubtitleRect(page);
  const insideDragDelta = Math.hypot(
    afterInsideDrag.left + afterInsideDrag.width / 2 - (beforeInsideDrag.left + beforeInsideDrag.width / 2),
    afterInsideDrag.top + afterInsideDrag.height / 2 - (beforeInsideDrag.top + beforeInsideDrag.height / 2)
  );
  expect(insideDragDelta).toBeLessThanOrEqual(2);

  await dragActiveSubtitleTo(page, 0.9, 0.2, "editor");
  await page.waitForTimeout(40);
  const afterBorderDrag = await readActiveSubtitleRect(page);
  const borderDragDelta = Math.hypot(
    afterBorderDrag.left + afterBorderDrag.width / 2 - (afterInsideDrag.left + afterInsideDrag.width / 2),
    afterBorderDrag.top + afterBorderDrag.height / 2 - (afterInsideDrag.top + afterInsideDrag.height / 2)
  );
  expect(borderDragDelta).toBeGreaterThan(20);
});

test("preview subtitle stays fully inside video when dragged to extremes", async ({ page }) => {
  await page.setViewportSize({ width: 1300, height: 800 });
  const projects = buildProjects();
  await mockProjects(page, projects);

  await page.goto("/");
  await page.getByText("good.mp4").click();
  await page.waitForURL("**/workbench/project-1");

  await primeVideoState(page, { playing: false, currentTime: 1.2 });
  const subtitleButton = page.getByTestId("workbench-active-subtitle");
  await expect(subtitleButton).toHaveCount(1);
  const layer = await ensureSubtitleLayerReady(page);

  for (const [xNorm, yNorm] of [
    [0, 0.1],
    [1, 0.1],
    [1, 0.9],
    [0, 0.9]
  ]) {
    await dragActiveSubtitleTo(page, xNorm, yNorm);
    await page.waitForTimeout(40);
    const layerRect = await readClientRect(layer);
    const subtitleRect = await readActiveSubtitleRect(page);
    expect(subtitleRect.left).toBeGreaterThanOrEqual(layerRect.left - 2);
    expect(subtitleRect.right).toBeLessThanOrEqual(layerRect.right + 2);
  }
});

test("editor textarea stays fully inside video when dragged to extremes", async ({ page }) => {
  await page.setViewportSize({ width: 1300, height: 800 });
  const projects = buildProjects();
  await mockProjects(page, projects);

  await page.goto("/");
  await page.getByText("good.mp4").click();
  await page.waitForURL("**/workbench/project-1");

  await primeVideoState(page, { playing: false, currentTime: 1.2 });
  await page.getByTestId("workbench-active-subtitle").click();
  const editor = page.getByTestId("workbench-subtitle-editor");
  await expect(editor).toHaveCount(1);
  const videoWrapper = page.getByTestId("workbench-center-panel-video-wrapper");
  await expect(videoWrapper).toHaveCount(1);
  await ensureSubtitleLayerReady(page);

  for (const [xNorm, yNorm] of [
    [0, 0.1],
    [1, 0.1],
    [1, 0.9],
    [0, 0.9]
  ]) {
    await dragActiveSubtitleTo(page, xNorm, yNorm, "editor");
    await page.waitForTimeout(40);
    const wrapperRect = await readClientRect(videoWrapper);
    const editorRect = await readClientRect(editor);
    expect(editorRect.left).toBeGreaterThanOrEqual(wrapperRect.left - 2);
    expect(editorRect.right).toBeLessThanOrEqual(wrapperRect.right + 2);
  }
});

test("off-screen saved subtitle position is auto-corrected and persisted", async ({ page }) => {
  await page.setViewportSize({ width: 1300, height: 800 });
  const projects = [
    {
      ...buildProjects()[0],
      style: {
        ...DEFAULT_PROJECT_STYLE,
        subtitle_style: {
          ...DEFAULT_PROJECT_STYLE.subtitle_style,
          appearance: {
            ...DEFAULT_PROJECT_STYLE.subtitle_style.appearance,
            position_x: 0,
            position_y: 0
          }
        }
      }
    }
  ];
  const api = await mockProjects(page, projects);

  await page.goto("/");
  await page.getByText("good.mp4").click();
  await page.waitForURL("**/workbench/project-1");

  await primeVideoState(page, { playing: false, currentTime: 1.2 });
  const subtitleButton = page.getByTestId("workbench-active-subtitle");
  await expect(subtitleButton).toHaveCount(1);
  const layer = await ensureSubtitleLayerReady(page);
  await subtitleButton.hover();
  await page.mouse.move(0, 0);

  await expect
    .poll(async () => {
      const layerRect = await readClientRect(layer);
      const subtitleRect = await readActiveSubtitleRect(page);
      return (
        subtitleRect.left >= layerRect.left - 2 &&
        subtitleRect.right <= layerRect.right + 2 &&
        subtitleRect.top >= layerRect.top - 2 &&
        subtitleRect.bottom <= layerRect.bottom + 2
      );
    })
    .toBe(true);

  await expect
    .poll(() => {
      const appearance = api.getLastPutPayload()?.style?.subtitle_style?.appearance;
      return typeof appearance?.position_x === "number" ? appearance.position_x : -1;
    })
    .toBeGreaterThan(0);

  await expect
    .poll(() => {
      const appearance = api.getLastPutPayload()?.style?.subtitle_style?.appearance;
      return typeof appearance?.position_y === "number" ? appearance.position_y : -1;
    })
    .toBeGreaterThan(0);
});

test.skip("vertical anchor middle offset matches overlay direction in wide and narrow layouts", async ({ page }) => {
  // Position is now set by dragging on the video; Style pane Position controls removed.
  const projects = buildProjects();
  await mockProjects(page, projects);

  const getSubtitleTop = async () =>
    page.evaluate(() => {
      const subtitle = document.querySelector("[data-testid='workbench-active-subtitle']");
      if (!(subtitle instanceof HTMLElement)) {
        return null;
      }
      return subtitle.getBoundingClientRect().top;
    });

  for (const viewport of [
    { width: 1300, height: 800 },
    { width: 900, height: 800 }
  ]) {
    await page.setViewportSize(viewport);
    await page.goto("/");
    await page.getByText("good.mp4").click();
    await page.waitForURL("**/workbench/project-1");
    await primeVideoState(page, { playing: false, currentTime: 1.2 });
    await expect(page.getByTestId("workbench-active-subtitle")).toHaveCount(1);

    await setVerticalAnchor(page, "Middle");
    await setVerticalOffset(page, "20");
    const middleTopAt20 = await getSubtitleTop();
    expect(middleTopAt20).not.toBeNull();

    await setVerticalOffset(page, "80");
    const middleTopAt80 = await getSubtitleTop();
    expect(middleTopAt80).not.toBeNull();
    expect(middleTopAt80 ?? 0).toBeLessThan(middleTopAt20 ?? 0);

    await setVerticalAnchor(page, "Top");
    await setVerticalOffset(page, "24");
    const topAnchorTop = await getSubtitleTop();
    expect(topAnchorTop).not.toBeNull();

    await setVerticalAnchor(page, "Bottom");
    await setVerticalOffset(page, "24");
    const bottomAnchorTop = await getSubtitleTop();
    expect(bottomAnchorTop).not.toBeNull();
    expect(bottomAnchorTop ?? 0).toBeGreaterThan(topAnchorTop ?? 0);
  }
});

test("controls overlap causes push and click opens editor", async ({ page }) => {
  await page.addInitScript(initTauriRuntimeMock);
  await page.setViewportSize({ width: 1300, height: 800 });
  const projects = buildProjects();
  await mockProjects(page, projects);

  await page.goto("/");
  await page.getByText("good.mp4").click();
  await page.waitForURL("**/workbench/project-1");

  await primeVideoState(page, { playing: false, currentTime: 1.2 });

  const subtitleButton = page.getByTestId("workbench-active-subtitle");
  await expect(subtitleButton).toHaveCount(1);
  await ensureSubtitleLayerReady(page);
  await dragActiveSubtitleTo(page, 0.5, 0.98);
  await page.mouse.move(0, 0);
  await expectVideoControlsHiddenSoon(page);

  const subtitleRectBefore = await readActiveSubtitleRect(page);

  await showVideoControls(page);
  await expect
    .poll(async () => (await readActiveSubtitleRect(page)).top)
    .toBeLessThan(subtitleRectBefore.top - 1);

  const subtitleRectAfter = await readActiveSubtitleRect(page);
  const subtitleDeltaY = subtitleRectAfter.top - subtitleRectBefore.top;
  expect(subtitleDeltaY).toBeLessThan(-1);

  const editor = page.getByTestId("workbench-subtitle-editor");
  if ((await editor.count()) === 0 && (await subtitleButton.count()) > 0) {
    await subtitleButton.first().click();
  }

  await expect(editor).toHaveCount(1);
  const editorRect = await readClientRect(editor);
  expect(Math.abs(editorRect.top - subtitleRectAfter.top)).toBeLessThanOrEqual(2);
  expect(Math.abs(editorRect.left - subtitleRectAfter.left)).toBeLessThanOrEqual(2);
});

test.skip("no-overlap scenario does not push subtitle position when controls appear", async ({ page }) => {
  // Position is now set by dragging; test required Top/24 from removed Position UI.
  await page.setViewportSize({ width: 1300, height: 800 });
  const projects = buildProjects();
  await mockProjects(page, projects);

  await page.goto("/");
  await page.getByText("good.mp4").click();
  await page.waitForURL("**/workbench/project-1");

  await primeVideoState(page, { playing: false, currentTime: 1.2 });
  await setVerticalAnchor(page, "Top");
  await setVerticalOffset(page, "24");

  const subtitleButton = page.getByTestId("workbench-active-subtitle");
  await expect(subtitleButton).toHaveCount(1);
  const subtitleRectBefore = await readClientRect(subtitleButton);

  await showVideoControls(page);
  await page.waitForTimeout(50);

  const subtitleRectAfter = await readClientRect(subtitleButton);
  expect(Math.abs(subtitleRectAfter.top - subtitleRectBefore.top)).toBeLessThanOrEqual(1);
});

test("video controls hide immediately on mouse leave", async ({ page }) => {
  await page.setViewportSize({ width: 1300, height: 800 });
  const projects = buildProjects();
  await mockProjects(page, projects);

  await page.goto("/");
  await page.getByText("good.mp4").click();
  await page.waitForURL("**/workbench/project-1");

  await primeVideoState(page, { playing: false, currentTime: 1.2 });
  await showVideoControls(page);
  await page.mouse.move(0, 0);
  await expectVideoControlsHiddenSoon(page);
});

test("edit overlay geometry matches preview subtitle and controls do not shift editor", async ({ page }) => {
  await page.setViewportSize({ width: 1300, height: 800 });
  const projects = buildProjects();
  await mockProjects(page, projects, LONG_HEBREW_SRT);

  await page.goto("/");
  await page.getByText("good.mp4").click();
  await page.waitForURL("**/workbench/project-1");

  await primeVideoState(page, { playing: false, currentTime: 1.2 });
  await setVerticalAnchor(page, "Bottom");
  await setVerticalOffset(page, "63");
  const fontSizeInput = page
    .locator("label:has-text('Font size')")
    .locator("xpath=../../input[@type='number']");
  await fontSizeInput.fill("66");
  await fontSizeInput.blur();

  const subtitleButton = page.getByTestId("workbench-active-subtitle");
  await expect(subtitleButton).toHaveCount(1);
  const previewRect = await readClientRect(subtitleButton);
  const previewTypography = await readTypographyMetrics(subtitleButton);
  const previewLineHeight = Number.parseFloat(previewTypography.lineHeight);
  expect(Number.isFinite(previewLineHeight)).toBe(true);
  expect(previewRect.height).toBeGreaterThan(previewLineHeight * 1.5);

  await subtitleButton.evaluate((element) => {
    if (element instanceof HTMLElement) {
      element.click();
    }
  });

  const editor = page.getByTestId("workbench-subtitle-editor");
  const controls = page.getByTestId("workbench-subtitle-editor-controls");
  await expect(editor).toHaveCount(1);
  await expect(controls).toHaveCount(1);

  const editorRectOnEnter = await readClientRect(editor);
  const editorTypography = await readTypographyMetrics(editor);
  expect(Math.abs(editorRectOnEnter.top - previewRect.top)).toBeLessThanOrEqual(2);
  expect(Math.abs(editorRectOnEnter.bottom - previewRect.bottom)).toBeLessThanOrEqual(1);
  expect(Math.abs(editorRectOnEnter.left - previewRect.left)).toBeLessThanOrEqual(2);
  expect(Math.abs(editorRectOnEnter.width - previewRect.width)).toBeLessThanOrEqual(2);
  expect(Math.abs(editorRectOnEnter.height - previewRect.height)).toBeLessThanOrEqual(2);
  expect(editorTypography.fontFamily).toBe(previewTypography.fontFamily);
  expect(editorTypography.fontSize).toBe(previewTypography.fontSize);
  expect(editorTypography.lineHeight).toBe(previewTypography.lineHeight);
  expect(editorTypography.letterSpacing).toBe(previewTypography.letterSpacing);
  expect(editorTypography.direction).toBe(previewTypography.direction);
  expect(editorTypography.boxSizing).toBe(previewTypography.boxSizing);
  expect(editorTypography.paddingLeft).toBe(previewTypography.paddingLeft);
  expect(editorTypography.paddingRight).toBe(previewTypography.paddingRight);

  await page.waitForTimeout(50);
  const editorRectAfterControls = await readClientRect(editor);
  expect(Math.abs(editorRectAfterControls.top - editorRectOnEnter.top)).toBeLessThanOrEqual(1);
  expect(Math.abs(editorRectAfterControls.left - editorRectOnEnter.left)).toBeLessThanOrEqual(1);
  expect(Math.abs(editorRectAfterControls.width - editorRectOnEnter.width)).toBeLessThanOrEqual(1);
  expect(Math.abs(editorRectAfterControls.height - editorRectOnEnter.height)).toBeLessThanOrEqual(1);
});

test("tauri subtitle editor geometry aligns with preview and uses Qt-calibrated line height", async ({
  page
}) => {
  await page.addInitScript(initTauriRuntimeMock);
  await page.setViewportSize({ width: 1300, height: 800 });
  const projects = buildProjects();
  await mockProjects(page, projects, LONG_HEBREW_SRT);

  await page.goto("/");
  await page.getByText("good.mp4").click();
  await page.waitForURL("**/workbench/project-1");

  await primeVideoState(page, { playing: false, currentTime: 1.2 });
  await setVerticalAnchor(page, "Bottom");
  await setVerticalOffset(page, "63");

  const fontSizeInput = page
    .locator("label:has-text('Font size')")
    .locator("xpath=../../input[@type='number']");
  await fontSizeInput.fill("66");
  await fontSizeInput.blur();

  const subtitleButton = page.getByTestId("workbench-active-subtitle");
  await expect(subtitleButton).toHaveCount(1);
  const previewRect = await readClientRect(subtitleButton);

  await subtitleButton.evaluate((element) => {
    if (element instanceof HTMLElement) {
      element.click();
    }
  });

  const editor = page.getByTestId("workbench-subtitle-editor");
  await expect(editor).toHaveCount(1);
  const editorRect = await readClientRect(editor);
  const editorTypography = await readTypographyMetrics(editor);
  expect(Math.abs(editorRect.top - previewRect.top)).toBeLessThanOrEqual(2);
  expect(Math.abs(editorRect.bottom - previewRect.bottom)).toBeLessThanOrEqual(1);

  const fontSizePx = Number.parseFloat(editorTypography.fontSize);
  const lineHeightPx = Number.parseFloat(editorTypography.lineHeight);
  expect(Number.isFinite(fontSizePx)).toBe(true);
  expect(Number.isFinite(lineHeightPx)).toBe(true);
  expect(Math.abs(lineHeightPx / fontSizePx - 1.125)).toBeLessThanOrEqual(0.02);
});

test("editor controls flip above when bottom anchor has no room and below when room exists", async ({
  page
}) => {
  await page.setViewportSize({ width: 1300, height: 800 });
  const projects = buildProjects();
  await mockProjects(page, projects);

  await page.goto("/");
  await page.getByText("good.mp4").click();
  await page.waitForURL("**/workbench/project-1");

  await primeVideoState(page, { playing: false, currentTime: 1.2 });
  await setVerticalAnchor(page, "Bottom");
  await setVerticalOffset(page, "0");

  const subtitleButton = page.getByTestId("workbench-active-subtitle");
  await expect(subtitleButton).toHaveCount(1);
  await subtitleButton.evaluate((element) => {
    if (element instanceof HTMLElement) {
      element.click();
    }
  });
  const editor = page.getByTestId("workbench-subtitle-editor");
  const controls = page.getByTestId("workbench-subtitle-editor-controls");
  await expect(editor).toHaveCount(1);
  await expect(controls).toHaveCount(1);

  const editorRectAtBottom = await readClientRect(editor);
  const controlsRectAtBottom = await readClientRect(controls);
  expect(controlsRectAtBottom.bottom).toBeLessThanOrEqual(editorRectAtBottom.top + 1);

  await page.getByTestId("workbench-subtitle-cancel").click();
  await expect(editor).toHaveCount(0);

  await setVerticalOffset(page, "120");
  await subtitleButton.evaluate((element) => {
    if (element instanceof HTMLElement) {
      element.click();
    }
  });
  await expect(editor).toHaveCount(1);
  await expect(controls).toHaveCount(1);

  const editorRectWithRoom = await readClientRect(editor);
  const controlsRectWithRoom = await readClientRect(controls);
  expect(controlsRectWithRoom.top).toBeGreaterThanOrEqual(editorRectWithRoom.bottom - 1);
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

test("on-video contract saves and resumes when Play is clicked during edit", async ({ page }) => {
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
  await editor.fill("Saved via Play button during edit");

  await page.evaluate(() => {
    document.querySelector("video")?.dispatchEvent(new Event("play", { bubbles: true }));
  });

  await expect(editor).toHaveCount(0);
  await expect(subtitleButton).toContainText("Saved via Play button during edit");
  await expect(subtitleButton).not.toHaveClass(/outline-primary/);
  expect(api.getSubtitlePutCallCount()).toBe(1);
  expect(api.getLastPutPayload()?.subtitles_srt_text ?? "").toContain("Saved via Play button during edit");
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

