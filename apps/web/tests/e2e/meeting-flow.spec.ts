import fs from "fs";
import path from "path";

import { expect, test } from "@playwright/test";

const API_BASE_URL = process.env.E2E_API_BASE_URL ?? "http://127.0.0.1:8000";
const GUEST_TOKEN_KEY = "meeting-notes:guest-token";

test("meeting flow: create -> upload -> indexed -> chat -> verify -> refresh history", async ({
  page,
  request,
}) => {
  const sessionRes = await request.post(`${API_BASE_URL}/sessions/guest`);
  if (!sessionRes.ok()) {
    throw new Error(
      `session create failed: ${sessionRes.status()} ${await sessionRes.text()}`,
    );
  }
  const session = (await sessionRes.json()) as { token: string };
  const authHeader = { Authorization: `Bearer ${session.token}` };

  const meetingRes = await request.post(`${API_BASE_URL}/meetings?title=E2E Meeting`, {
    headers: authHeader,
  });
  if (!meetingRes.ok()) {
    throw new Error(
      `meeting create failed: ${meetingRes.status()} ${await meetingRes.text()}`,
    );
  }
  const meeting = (await meetingRes.json()) as { id: string };

  const uploadPath = path.resolve(__dirname, "../../../../sample-upload.md");
  const uploadRes = await request.post(`${API_BASE_URL}/meetings/${meeting.id}/documents/upload`, {
    headers: authHeader,
    multipart: {
      doc_type: "notes",
      files: {
        name: "sample-upload.md",
        mimeType: "text/markdown",
        buffer: fs.readFileSync(uploadPath),
      },
    },
  });
  if (!uploadRes.ok()) {
    throw new Error(`upload failed: ${uploadRes.status()} ${await uploadRes.text()}`);
  }

  let indexed = false;
  for (let i = 0; i < 25; i += 1) {
    const docsRes = await request.get(`${API_BASE_URL}/meetings/${meeting.id}/documents`, {
      headers: authHeader,
    });
    if (!docsRes.ok()) {
      throw new Error(`documents list failed: ${docsRes.status()} ${await docsRes.text()}`);
    }
    const docs = (await docsRes.json()) as Array<{ status: string }>;
    if (docs.some((doc) => doc.status === "indexed")) {
      indexed = true;
      break;
    }
    await page.waitForTimeout(2000);
  }
  expect(indexed).toBeTruthy();

  await page.addInitScript(([key, token]) => {
    window.localStorage.setItem(key, token);
  }, [GUEST_TOKEN_KEY, session.token]);

  await page.goto(`/meetings/${meeting.id}`);

  const composer = page.locator(
    'textarea[placeholder="Ask a question about this meeting..."]:visible',
  );
  await expect(composer).toHaveCount(1);
  await expect(composer).toBeVisible();
  await composer.fill("What happened in this meeting?");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("What happened in this meeting?")).toBeVisible();

  // Ensure the backend persisted this turn before refresh assertions.
  let historyPersisted = false;
  for (let i = 0; i < 20; i += 1) {
    const historyRes = await request.get(`${API_BASE_URL}/meetings/${meeting.id}/chat/history`, {
      headers: authHeader,
    });
    if (!historyRes.ok()) {
      throw new Error(`chat history failed: ${historyRes.status()} ${await historyRes.text()}`);
    }
    const turns = (await historyRes.json()) as Array<{ question?: string }>;
    if (turns.some((turn) => turn.question === "What happened in this meeting?")) {
      historyPersisted = true;
      break;
    }
    await page.waitForTimeout(500);
  }
  expect(historyPersisted).toBeTruthy();

  const runVerifyButton = page.getByRole("button", { name: "Run Verify" }).first();
  await expect(runVerifyButton).toBeVisible();
  await runVerifyButton.click();

  await page.reload({ waitUntil: "networkidle" });
  const reloadedQuestion = page
    .locator("div")
    .filter({ hasText: "What happened in this meeting?" })
    .first();
  await expect(reloadedQuestion).toBeVisible({ timeout: 15000 });
});
