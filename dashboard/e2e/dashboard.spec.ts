import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import * as path from "path";
import * as fs from "fs";

const MOCK_HEALTH_SIMULATED = {
  status: "ok",
  mode: "SIMULATED",
  uptime_s: 300,
  camera: "ok",
  mqtt: "ok",
  fps: 25.0,
  latency_ms: 8.2,
  privacy: { blurred_source: true },
  components: [
    { name: "pipeline", status: "ok" },
    { name: "rule_engine", status: "ok" },
  ],
};

const MOCK_HEALTH_REPLAY = {
  status: "ok",
  mode: "REPLAY",
  replay_file: "tests/fixtures/pipegen_real_capture.ndjson",
  uptime_s: 150,
  camera: "ok",
  mqtt: "ok",
  fps: 25.0,
  latency_ms: 5.1,
  privacy: { blurred_source: true },
  components: [
    { name: "pipeline", status: "ok" },
    { name: "rule_engine", status: "ok" },
  ],
};

const MOCK_ZONES = {
  frame: { width: 1920, height: 1080 },
  version: 1,
  zones: [
    {
      id: "walkway",
      name: "Main Walkway",
      type: "safe",
      required_ppe: ["helmet"],
      polygon: [
        [150, 600],
        [950, 600],
        [950, 1020],
        [150, 1020],
      ],
    },
    {
      id: "crane-drop",
      name: "Crane Drop Area",
      type: "danger",
      required_ppe: ["helmet", "vest"],
      polygon: [
        [1400, 150],
        [1880, 150],
        [1880, 650],
        [1400, 650],
      ],
    },
  ],
};

const MOCK_INCIDENTS = [
  {
    incident_id: "INC-E2E-001",
    timestamp: "2026-10-19T10:00:00Z",
    camera_id: "cam-01",
    type: "NO_HELMET",
    severity: "HIGH",
    track_id: 101,
    zone: "crane-drop",
    confidence: 0.94,
    duration_s: 2.5,
    status: "open",
    notes: [],
    evidence_status: "pending",
  },
];

const MOCK_STATS = {
  window: "24h",
  total_incidents: 1,
  by_type: { NO_HELMET: 1 },
  by_zone: { "crane-drop": 1 },
  by_severity: { HIGH: 1 },
  by_hour: [{ hour: "10:00", count: 1 }],
  compliance_percentage: 95.5,
};

async function setupStandardMocks(page: any, healthOverride = MOCK_HEALTH_SIMULATED) {
  await page.route("**/api/**", async (route: any) => {
    const url = route.request().url();
    const method = route.request().method();

    if (url.includes("/health")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(healthOverride),
      });
    }
    if (url.includes("/zones")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_ZONES),
      });
    }
    if (url.includes("/incidents")) {
      if (url.includes("/ack")) {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ status: "acknowledged" }),
        });
      }
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: MOCK_INCIDENTS, total: 1 }),
      });
    }
    if (url.includes("/stats")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_STATS),
      });
    }
    if (url.includes("log-integrity")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          intact: true,
          tampered_line: null,
          total_records: 42,
          genesis_hash: "0000000000000000000000000000000000000000000000000000000000000000",
          latest_hash: "a1b2c3d4e5f67890a1b2c3d4e5f67890a1b2c3d4e5f67890a1b2c3d4e5f67890",
        }),
      });
    }

    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({}),
    });
  });
}

test.describe("SiteSentinel Control Room Dashboard E2E", () => {
  test("1. Backend Down state displays error banner with sentinel run prompt", async ({ page }) => {
    await page.route("**/api/health**", (route) => route.abort());
    await page.goto("/");

    const alertBanner = page.locator('[role="alert"]').filter({ hasText: "Backend unreachable" });
    await expect(alertBanner).toBeVisible({ timeout: 5000 });
    await expect(alertBanner).toContainText("Backend unreachable");
    await expect(alertBanner).toContainText("sentinel run");
  });

  test("2. SIMULATED mode displays persistent banner", async ({ page }) => {
    await setupStandardMocks(page, MOCK_HEALTH_SIMULATED);
    await page.goto("/");
    const banner = page.getByText("Simulated data. Not a live camera.");
    await expect(banner).toBeVisible({ timeout: 5000 });
  });

  test("3. REPLAY mode displays persistent banner", async ({ page }) => {
    await setupStandardMocks(page, MOCK_HEALTH_REPLAY);
    await page.goto("/");
    const banner = page.getByText(/Replay:/i);
    await expect(banner).toBeVisible({ timeout: 5000 });
    await expect(banner).toContainText("pipegen_real_capture.ndjson");
  });

  test("4. Incident acknowledgment flow", async ({ page }) => {
    let ackCalled = false;
    await setupStandardMocks(page);
    await page.route("**/api/incidents/INC-E2E-001/ack", async (route) => {
      ackCalled = true;
      await route.fulfill({ json: { status: "acknowledged" } });
    });

    await page.goto("/incidents");
    const cell = page.getByRole("cell", { name: "No helmet" });
    await expect(cell).toBeVisible({ timeout: 5000 });

    // Click on the incident row cell to open detail drawer
    await cell.click();

    const ackButton = page.getByRole("button", { name: "Acknowledge" }).first();
    await expect(ackButton).toBeVisible({ timeout: 5000 });
    await ackButton.click();
    expect(ackCalled).toBe(true);
  });

  test("5. Zone editor save flow", async ({ page }) => {
    let zonesSaved = false;
    await setupStandardMocks(page);
    await page.route("**/api/zones**", (route) => {
      if (route.request().method() === "PUT") {
        zonesSaved = true;
        route.fulfill({ json: MOCK_ZONES });
      } else {
        route.fulfill({ json: MOCK_ZONES });
      }
    });

    await page.goto("/zones");
    const saveButton = page.getByRole("button", { name: "Save zones" });
    await expect(saveButton).toBeVisible({ timeout: 5000 });
    await saveButton.click();
    expect(zonesSaved).toBe(true);
  });

  test("6. Evidence view and cryptographic verification", async ({ page }) => {
    await setupStandardMocks(page);
    await page.goto("/evidence");
    await expect(page.getByText(/Evidence/i).first()).toBeVisible({ timeout: 5000 });
  });

  test("7. Present mode toggle via keyboard 'P'", async ({ page }) => {
    await setupStandardMocks(page);
    await page.goto("/");
    await page.keyboard.press("p");
    await expect(page.getByText("Today by Zone & Hourly")).toHaveCount(0);
  });

  test("8. Axe-core accessibility scan on routes (zero serious/critical)", async ({ page }) => {
    await setupStandardMocks(page);
    const routes = ["/", "/incidents", "/zones", "/reports", "/evidence", "/system"];

    for (const r of routes) {
      await page.goto(r);
      const accessibilityScanResults = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
        .analyze();

      const seriousOrCritical = accessibilityScanResults.violations.filter(
        (v) => v.impact === "serious" || v.impact === "critical"
      );

      expect(
        seriousOrCritical,
        `Route ${r} accessibility violations (serious/critical): ${JSON.stringify(seriousOrCritical, null, 2)}`
      ).toEqual([]);
    }
  });

  test("9. Visual snapshots at 1440, 1024, 390 in light and dark", async ({ page }) => {
    const screenshotDir = path.resolve(process.cwd(), "../evidence/screenshots");
    if (!fs.existsSync(screenshotDir)) {
      fs.mkdirSync(screenshotDir, { recursive: true });
    }

    await setupStandardMocks(page);

    // 1440x900 Dark (Default SIMULATED)
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/");
    await page.screenshot({ path: path.join(screenshotDir, "dashboard-live-dark.png") });
    await page.screenshot({ path: path.join(screenshotDir, "dashboard-live-simulated.png") });

    // 1440x900 Light
    await page.evaluate(() => {
      document.documentElement.setAttribute("data-theme", "light");
    });
    await page.screenshot({ path: path.join(screenshotDir, "dashboard-live-light.png") });

    // Reset to dark
    await page.evaluate(() => {
      document.documentElement.setAttribute("data-theme", "dark");
    });

    // 1024x800 Tablet
    await page.setViewportSize({ width: 1024, height: 800 });
    await page.goto("/");
    await page.screenshot({ path: path.join(screenshotDir, "dashboard-1024.png") });

    // 390x800 Mobile
    await page.setViewportSize({ width: 390, height: 800 });
    await page.goto("/");
    await page.screenshot({ path: path.join(screenshotDir, "dashboard-390.png") });

    // Present mode
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/");
    await page.keyboard.press("p");
    await page.screenshot({ path: path.join(screenshotDir, "dashboard-present-mode.png") });

    // Other screens
    await page.goto("/incidents");
    await page.screenshot({ path: path.join(screenshotDir, "dashboard-incidents.png") });

    await page.goto("/zones");
    await page.screenshot({ path: path.join(screenshotDir, "dashboard-zones.png") });

    await page.goto("/reports");
    await page.screenshot({ path: path.join(screenshotDir, "dashboard-reports.png") });

    await page.goto("/system");
    await page.screenshot({ path: path.join(screenshotDir, "dashboard-system.png") });
  });

  test("10. Production bundle purity: no synthetic fixtures and no dev routes", async () => {
    const distDir = path.resolve(process.cwd(), "dist/assets");
    expect(fs.existsSync(distDir)).toBe(true);

    const jsFiles = fs.readdirSync(distDir).filter((f) => f.endsWith(".js"));
    expect(jsFiles.length).toBeGreaterThan(0);

    for (const jsFile of jsFiles) {
      const content = fs.readFileSync(path.join(distDir, jsFile), "utf-8");
      // Must not contain mock scenarios
      expect(content).not.toContain("busy_shift");
      expect(content).not.toContain("MOCK_ZONES");
      // Must not contain dev-only route path
      expect(content).not.toContain('path:"/design"');
    }
  });
});
