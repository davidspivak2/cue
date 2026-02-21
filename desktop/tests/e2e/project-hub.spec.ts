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

const DEFAULT_PROJECT_STYLE = {
  subtitle_mode: "word_highlight",
  subtitle_style: {
    preset: "Default",
    highlight_color: "#FFD400",
    highlight_opacity: 1,
    appearance: {
      subtitle_mode: "word_highlight",
      highlight_color: "#FFD400"
    }
  }
};

test("project hub card interactions", async ({ page }) => {
  await page.addInitScript(initMocks);
  await page.addInitScript(initTauriRuntimeMock);

  let projects = [
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
    },
    {
      project_id: "project-3",
      title: "another.mp4",
      video_path: "C:\\fake\\another.mp4",
      missing_video: false,
      status: "ready",
      created_at: "2026-02-09T00:00:00Z",
      updated_at: "2026-02-09T00:00:00Z",
      duration_seconds: 42,
      thumbnail_path: ""
    },
    {
      project_id: "project-2",
      title: "missing.mp4",
      video_path: "C:\\fake\\missing.mp4",
      missing_video: true,
      status: "missing_file",
      created_at: "2026-02-09T00:00:00Z",
      updated_at: "2026-02-09T00:00:00Z",
      duration_seconds: 120,
      thumbnail_path: ""
    }
  ];
  let createdCount = 0;

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
    latest_export: null,
    style: project.style ?? DEFAULT_PROJECT_STYLE
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
      const payload = request.postDataJSON();
      createdCount += 1;
      const path = payload?.video_path || `C:\\fake\\video_${createdCount}.mp4`;
      const title = String(path).split(/[/\\]/).pop() || "Untitled video";
      const now = "2026-02-09T00:00:00Z";
      const newProject = {
        project_id: `project-${createdCount}`,
        title,
        video_path: path,
        missing_video: false,
        status: "needs_subtitles",
        created_at: now,
        updated_at: now,
        duration_seconds: 65,
        thumbnail_path: ""
      };
      projects = [newProject, ...projects];
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(newProject)
      });
      return;
    }
    await route.continue();
  });

  await page.route("**://127.0.0.1:8765/projects/*/relink", async (route) => {
    const request = route.request();
    if (request.method() !== "POST") {
      await route.continue();
      return;
    }
    const payload = request.postDataJSON();
    const url = request.url();
    const projectId = url.split("/projects/")[1]?.split("/")[0];
    const relinkPath = payload?.video_path || "C:\\fake\\relinked.mp4";
    const title = String(relinkPath).split(/[/\\]/).pop() || "Relinked video";
    projects = projects.map((project) =>
      project.project_id === projectId
        ? {
            ...project,
            title,
            video_path: relinkPath,
            missing_video: false,
            status: "needs_subtitles",
            updated_at: "2026-02-09T00:10:00Z"
          }
        : project
    );
    const updated = projects.find((project) => project.project_id === projectId) ?? projects[0];
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(updated)
    });
  });

  await page.route("**://127.0.0.1:8765/projects/*", async (route) => {
    const request = route.request();
    const url = request.url();
    if (request.method() === "OPTIONS") {
      await route.fulfill({
        status: 204,
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "GET, DELETE, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type"
        }
      });
      return;
    }
    const projectId = url.split("/projects/")[1]?.split("/")[0];
    const project = projects.find((entry) => entry.project_id === projectId);

    if (request.method() === "GET") {
      if (!project) {
        await route.fulfill({
          status: 404,
          contentType: "application/json",
          body: JSON.stringify({ detail: "not_found" })
        });
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(buildManifest(project))
      });
      return;
    }

    if (request.method() === "PUT") {
      let payload: Record<string, unknown> = {};
      try {
        payload = request.postDataJSON() as Record<string, unknown>;
      } catch {
        payload = {};
      }
      projects = projects.map((entry) =>
        entry.project_id === projectId
          ? {
              ...entry,
              style:
                payload && typeof payload.style === "object"
                  ? payload.style
                  : entry.style ?? DEFAULT_PROJECT_STYLE
            }
          : entry
      );
      const updated = projects.find((entry) => entry.project_id === projectId) ?? project;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(buildManifest(updated))
      });
      return;
    }

    if (request.method() === "DELETE") {
      if (!project) {
        await route.fulfill({
          status: 404,
          contentType: "application/json",
          body: JSON.stringify({ detail: "project_not_found" })
        });
        return;
      }
      projects = projects.filter((entry) => entry.project_id !== projectId);
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ok: true, project_id: projectId, cancelled_job_ids: [] })
      });
      return;
    }

    await route.continue();
  });

  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Videos" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Add video" })).toBeVisible();
  await expect(page.getByTestId("project-hub").getByText("another.mp4")).toBeVisible();
  await expect(page.getByTestId("project-hub").getByText("good.mp4")).toBeVisible();

  await page.getByTestId("project-hub").getByText("good.mp4").click();
  await page.waitForURL("**/workbench/project-1");
  await expect(page.getByTestId("workbench")).toBeVisible();
  await page.getByTestId("title-bar-home").click();
  await expect(page.getByRole("heading", { name: "Videos" })).toBeVisible();

  await page.getByTestId("project-card-delete-project-3").click();
  await expect(page.getByRole("heading", { name: "Delete video?" })).toBeVisible();
  await page.getByRole("button", { name: "Cancel" }).click();
  await expect(page.getByText("another.mp4")).toBeVisible();

  const deleteRequest = page.waitForRequest(
    (request) => request.url().includes("/projects/project-3") && request.method() === "DELETE"
  );
  await page.getByTestId("project-card-delete-project-3").click();
  await page.getByRole("button", { name: "Delete video" }).click();
  await deleteRequest;
  // D4: delete success must be toast, not inline banner (CUE_UX_UI_SPEC).
  await expect(
    page.getByRole("status").filter({ hasText: "Video deleted" })
  ).toBeVisible();
  await expect(page.getByTestId("project-hub").getByText("another.mp4")).toHaveCount(0);
  await expect(page.getByTestId("project-hub-banner")).toHaveCount(0);

  await page.getByTestId("project-hub").getByText("good.mp4").click();
  await page.waitForURL("**/workbench/project-1");
  await expect(page.getByTestId("workbench")).toBeVisible();
  await expect(page.getByTestId("workbench-heading")).toBeVisible();
  await expect(page.getByTestId("title-bar-tab-project-1")).toBeVisible();
  await page.getByTestId("title-bar-home").click();
  await expect(page.getByRole("heading", { name: "Videos" })).toBeVisible();

  await page.getByTestId("project-hub").getByText("missing.mp4").click();
  await expect(page.getByRole("heading", { name: "Video file not found" })).toBeVisible();
  await expect(
    page.getByText("We cannot find the original video file.")
  ).toBeVisible();
  await page.getByRole("button", { name: "Select file" }).click();

  await page.locator("[data-testid='relink-input']").setInputFiles({
    name: "different.mp4",
    mimeType: "video/mp4",
    buffer: Buffer.from("fake")
  });

  await expect(page.getByRole("heading", { name: "This file looks different" })).toBeVisible();
  await expect(page.getByText("Captions and timing may be wrong")).toBeVisible();

  const relinkRequest = page.waitForRequest(
    (request) => request.url().includes("/relink") && request.method() === "POST"
  );
  await page.getByRole("button", { name: "Use this file anyway" }).click();
  await relinkRequest;

  await expect(page.getByText("different.mp4")).toBeVisible();
});

test("project hub shows active task cards, inline notices, and background toasts", async ({
  page
}) => {
  await page.addInitScript(initMocks);
  await page.addInitScript(initTauriRuntimeMock);

  const projects = [
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
      active_task: {
        job_id: "job-bg-1",
        kind: "create_subtitles",
        status: "running",
        heading: "Creating subtitles",
        message: "Loading model",
        pct: 17,
        step_id: "load_model",
        started_at: "2026-02-09T00:00:01Z",
        updated_at: "2026-02-09T00:00:01Z",
        checklist: [
          {
            id: "load_model",
            label: "Loading AI model",
            state: "active",
            detail: "Loading model"
          }
        ]
      },
      task_notice: null
    },
    {
      project_id: "project-2",
      title: "another.mp4",
      video_path: "C:\\fake\\another.mp4",
      missing_video: false,
      status: "ready",
      created_at: "2026-02-09T00:00:00Z",
      updated_at: "2026-02-09T00:00:00Z",
      duration_seconds: 42,
      thumbnail_path: "",
      active_task: null,
      task_notice: null
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
    latest_export: null,
    style: project.style ?? DEFAULT_PROJECT_STYLE,
    active_task: project.active_task ?? null,
    task_notice: project.task_notice ?? null
  });
  const settingsPayload = {
    save_policy: "same_folder",
    save_folder: "",
    transcription_quality: "auto",
    punctuation_rescue_fallback_enabled: true,
    apply_audio_filter: false,
    keep_extracted_audio: false,
    subtitle_mode: "word_highlight",
    subtitle_style: {
      preset: "Default",
      highlight_color: "#FFD400",
      highlight_opacity: 1,
      appearance: {
        subtitle_mode: "word_highlight",
        highlight_color: "#FFD400"
      }
    }
  };
  let projectsGetCount = 0;

  await page.route("**://127.0.0.1:8765/health", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ok: true })
    });
  });

  await page.route("**://127.0.0.1:8765/settings", async (route) => {
    const request = route.request();
    if (request.method() !== "GET") {
      await route.continue();
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(settingsPayload)
    });
  });

  await page.route("**://127.0.0.1:8765/projects/*/subtitles", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        subtitles_srt_text: "1\n00:00:00,000 --> 00:00:02,000\nBackground subtitle\n"
      })
    });
  });

  await page.route("**://127.0.0.1:8765/projects/*", async (route) => {
    const request = route.request();
    if (request.method() !== "GET") {
      await route.continue();
      return;
    }
    const projectId = request.url().split("/projects/")[1]?.split("/")[0];
    const project = projects.find((entry) => entry.project_id === projectId);
    if (!project) {
      await route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({ detail: "project_not_found" })
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(buildManifest(project))
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
    if (request.method() !== "GET") {
      await route.continue();
      return;
    }
    projectsGetCount += 1;
    if (projectsGetCount >= 3) {
      projects[0].active_task = null;
      projects[0].task_notice = {
        notice_id: "notice-bg-1",
        project_id: "project-1",
        job_id: "job-bg-1",
        kind: "create_subtitles",
        status: "error",
        message: "Background subtitle run failed.",
        created_at: new Date().toISOString(),
        finished_at: new Date().toISOString()
      };
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(projects)
    });
  });

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Videos" })).toBeVisible();
  await expect(page.getByTestId("project-card-active-task-project-1")).toBeVisible();
  await expect(page.getByTestId("project-card-active-task-project-1")).toContainText(
    "Creating subtitles"
  );
  await expect(page.getByTestId("project-card-active-task-project-1")).toContainText(
    "Loading AI model"
  );

  await page.getByTestId("project-card-project-2").click();
  await page.waitForURL("**/workbench/project-2");
  await expect(page.getByTestId("workbench")).toBeVisible();

  await expect(page.getByText("Task failed: Background subtitle run failed.")).toBeVisible();
  await page.getByTestId("title-bar-home").click();
  await expect(page.getByRole("heading", { name: "Videos" })).toBeVisible();
  await expect(page.getByTestId("project-card-task-notice-project-1")).toContainText(
    "Background subtitle run failed."
  );

  await page
    .getByTestId("project-card-task-notice-project-1")
    .getByRole("button", { name: "Dismiss task notice" })
    .click();
  await expect(page.getByTestId("project-card-task-notice-project-1")).toHaveCount(0);
});
