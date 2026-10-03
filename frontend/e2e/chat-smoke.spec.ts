import { expect, test } from "@playwright/test";

const EMAIL = process.env.E2E_EMAIL;
const PASSWORD = process.env.E2E_PASSWORD;
const SYMBOL = process.env.E2E_SYMBOL ?? "AAPL";

test.skip(!EMAIL || !PASSWORD, "Set E2E_EMAIL and E2E_PASSWORD (a Firebase test account) to run the smoke test.");

test("select asset → send → live agents → sections → feedback → follow-up", async ({ page }) => {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(EMAIL!);
  await page.locator('input[type="password"]').first().fill(PASSWORD!);
  await page.locator('button[type="submit"]').click();
  await page.waitForURL(/\/(dashboard|onboarding)/);

  await page.goto("/chat");
  const composer = page.getByTestId("composer");
  await expect(composer).toBeVisible();

  // Send stays disabled (with a hint) until both an asset and a prompt exist.
  await expect(page.getByTestId("send-button")).toBeDisabled();
  await expect(page.locator("#composer-hint")).toContainText("Select an asset");

  // Asset combobox: type, pick via keyboard.
  await page.getByTestId("asset-search").fill(SYMBOL);
  const option = page.getByRole("option").filter({ hasText: SYMBOL }).first();
  await expect(option).toBeVisible();
  await page.getByTestId("asset-search").press("ArrowDown");
  await page.getByTestId("asset-search").press("ArrowUp");
  await page.getByTestId("asset-search").press("Enter");
  await expect(page.getByTestId("asset-chip")).toContainText(SYMBOL);

  // Enter sends; the orchestration panel appears immediately (no blank screen).
  const prompt = page.getByTestId("prompt-input");
  await prompt.fill("How risky is this right now and how should I hedge a long position?");
  const sentAt = Date.now();
  await prompt.press("Enter");
  await expect(page.getByTestId("user-message").last()).toBeVisible();
  const panel = page.getByTestId("orchestration-panel").last();
  await expect(panel).toBeVisible({ timeout: 2_000 });
  expect(Date.now() - sentAt).toBeLessThan(2_000);
  await expect(page.locator('[data-testid^="agent-"][data-status="running"], [data-testid^="agent-"][data-status="done"]').first()).toBeVisible({
    timeout: 10_000,
  });
  await expect(page.getByTestId("stop-button")).toBeVisible();

  // Final result: panel collapses, sections render in order.
  const turn = page.getByTestId("assistant-turn").last();
  await expect(turn).toHaveAttribute("data-status", "complete", { timeout: 180_000 });
  await expect(panel).toHaveAttribute("data-state", "collapsed");
  const titles = await turn.locator("section h3").allInnerTexts();
  const order = ["ASSET SNAPSHOT", "REAL-TIME SOURCES", "HISTORICAL ANALYSIS", "LIVE CHART", "SUGGESTIONS", "RISK & TRUST"];
  expect(titles.map((t) => t.trim().toUpperCase())).toEqual(order);
  await expect(turn.getByTestId("suggestion-card").first()).toBeVisible();
  await expect(turn.getByTestId("gauge-risk")).toBeVisible();
  await expect(turn.getByTestId("gauge-trust")).toBeVisible();

  // The agent log can be re-expanded.
  await page.getByTestId("orchestration-summary").last().click();
  await expect(panel.locator('[data-testid="agent-audit"]')).toBeVisible();

  // Feedback submits and persists.
  await turn.getByTestId("feedback-up").click();
  await turn.getByRole("button", { name: "Accurate" }).click();
  await turn.getByTestId("feedback-submit").click();
  await expect(turn.getByTestId("feedback-saved")).toBeVisible();

  // Follow-up in the same thread keeps the asset and context.
  await expect(page).toHaveURL(/\?thread=/);
  await prompt.fill("What if I hold it for 6 months instead?");
  await prompt.press("Enter");
  const followUp = page.getByTestId("assistant-turn").last();
  await expect(followUp).toHaveAttribute("data-status", "complete", { timeout: 180_000 });

  // Thread survives a refresh and shows in the sidebar.
  await page.reload();
  await expect(page.getByTestId("assistant-turn")).toHaveCount(2, { timeout: 20_000 });
});
