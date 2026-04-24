import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const PUBLIC_ROUTES = ["/", "/login", "/apply"];

for (const path of PUBLIC_ROUTES) {
  test(`axe-core: ${path} has no critical accessibility issues`, async ({
    page,
  }) => {
    await page.goto(path);
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    const critical = results.violations.filter(
      (v) => v.impact === "critical" || v.impact === "serious",
    );
    expect(critical, JSON.stringify(critical, null, 2)).toEqual([]);
  });
}

test("security headers present on root", async ({ request }) => {
  const response = await request.get("/");
  expect(response.status()).toBeLessThan(500);
  const headers = response.headers();
  expect(headers["x-content-type-options"]).toBe("nosniff");
  expect(headers["x-frame-options"]).toBe("DENY");
  expect(headers["referrer-policy"]).toBeTruthy();
  expect(headers["strict-transport-security"]).toContain("max-age=");
});
