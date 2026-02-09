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

test("project hub card interactions", async ({ page }) => {
  await page.addInitScript(initMocks);

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
    latest_export: null
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
      const title = String(path).split(/[/\\]/).pop() || "Untitled project";
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
    const title = String(relinkPath).split(/[/\\]/).pop() || "Relinked project";
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
    if (request.method() === "GET") {
      const projectId = url.split("/projects/")[1]?.split("/")[0];
      const project = projects.find((entry) => entry.project_id === projectId);
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

    await route.continue();
  });

  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Project Hub" })).toBeVisible();
  await expect(page.getByRole("button", { name: "New project" })).toBeVisible();

  await page.getByText("good.mp4").click();
  await page.waitForURL("**/workbench/project-1");
  await expect(page.getByTestId("workbench")).toBeVisible();
  await expect(page.getByText("good.mp4")).toBeVisible();
  await page.getByRole("button", { name: "Back" }).click();
  await expect(page.getByRole("heading", { name: "Project Hub" })).toBeVisible();

  await page.getByText("missing.mp4").click();
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
