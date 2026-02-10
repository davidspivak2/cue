import { expect, test } from "@playwright/test";

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
    thumbnail_path: ""
  }
];

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
  latest_export: null
});

const DEFAULT_SRT = "1\n00:00:00,000 --> 00:00:04,000\nOriginal subtitle line\n";

const getProjectIdFromUrl = (url) => url.split("/projects/")[1]?.split("/")[0] ?? "";

const mockProjects = async (page, projects, initialSrtText = DEFAULT_SRT) => {
  let putCallCount = 0;
  let lastPutPayload = null;
  const subtitlesByProject = new Map(
    projects.map((project) => [project.project_id, initialSrtText])
  );

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
        subtitlesByProject.set(projectId, lastPutPayload.subtitles_srt_text);
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

  return {
    getPutCallCount: () => putCallCount,
    getLastPutPayload: () => lastPutPayload
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
        pauseCalled: false
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
  await expect(subtitleButton).toHaveClass(/outline-primary/);

  await subtitleButton.click();
  const editor = page.getByTestId("workbench-subtitle-editor");
  await expect(editor).toBeVisible();
  await editor.fill("Edited subtitle line");
  await editor.press("Enter");

  await expect(editor).toHaveCount(0);
  await expect(subtitleButton).toContainText("Edited subtitle line");
  expect(api.getPutCallCount()).toBe(1);
  expect(api.getLastPutPayload()?.subtitles_srt_text ?? "").toContain("Edited subtitle line");
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
  await subtitleButton.click();

  const editor = page.getByTestId("workbench-subtitle-editor");
  await expect(editor).toBeVisible();
  await editor.fill("This should not save");
  await editor.press("Escape");

  await expect(editor).toHaveCount(0);
  await expect(subtitleButton).toContainText("Original subtitle line");
  expect(api.getPutCallCount()).toBe(0);
});
