# Frontend Plan and Current Architecture (Next.js)

This file captures the current frontend state after the guest-mode/auth and chat-history upgrades.

Backend contract reference: `backendap.md`

## 1) Stack

- Next.js (TypeScript, App Router)
- Tailwind CSS
- shadcn/ui
- TanStack Query
- lucide-react
- sonner (toasts)
- Playwright (E2E scaffold)

## 2) Implemented Architecture

## 2.1 Routing

- `src/app/layout.tsx`
  - root HTML/body + providers (React Query + Toaster)
- `src/app/(app)/layout.tsx`
  - app shell wrapper (`AppShell`)
- `src/app/(app)/page.tsx`
  - home screen
- `src/app/(app)/meetings/[meetingId]/page.tsx`
  - meeting workspace

## 2.2 Shell UX

Desktop:
- Left rail: meetings list + create meeting + home
- Center: workspace (chat-focused)
- Right rail: artifacts tabs (`Verify`, `Tasks`, `Issues`, `Docs`)

Mobile:
- top nav + meetings drawer
- workspace tabs (`Chat`, `Verify`, `Docs`)

## 2.3 Data Layer

React Query keys in use:
- `['meetings']`
- `['meeting', meetingId]`
- `['meeting-documents', meetingId]`
- `['verify', meetingId]`
- `['chat-history', meetingId]`
- `['chunk-detail', chunkId]`

Polling:
- `useMeetingDocuments(meetingId)` polls every 2s while any doc is `pending|processing`
- polling stops when all docs are terminal

## 2.4 Guest Auth Mode

- Frontend lazily creates a guest session token via `POST /sessions/guest`
- token stored in localStorage key: `meeting-notes:guest-token`
- all API calls include `Authorization: Bearer <token>`
- stale token recovery: one automatic token refresh/retry on `401`

## 2.5 Chat UX (Current)

- Composer with attachments (`Attach` + `Send`)
- Message thread + citation chips
- Citation drawer now fetches real chunk text (`GET /chunks/{chunk_id}`)
- No-citation warning callout under assistant messages
- Loading animation (`Thinking...`) and smooth transitions
- Auto-scroll to latest message
- Chat history is DB-backed via `GET /meetings/{id}/chat/history` (survives refresh/device)

## 3) Meeting Readiness State

Derived from meeting documents:

```ts
type MeetingIndexState =
  | "EMPTY"
  | "NOT_INDEXED"
  | "PARTIALLY_INDEXED"
  | "INDEXED"
  | "FAILED_ONLY";
```

Behavior:
- Verify enabled for `PARTIALLY_INDEXED` and `INDEXED`
- Chat blocked only for `NOT_INDEXED`
- Banners shown for indexing/partial/failed states

## 4) Current Component Map

```text
src/components/
  chat/
    AttachmentChips.tsx
    ChatPanel.tsx
    CitationDrawer.tsx
    Composer.tsx
  documents/
    DocumentStatusBadge.tsx
    DocumentUploadForm.tsx
    DocumentsPanel.tsx
    DocumentsTable.tsx
    ReindexButton.tsx
  layout/
    MeetingWorkspace.tsx
  shell/
    AppShell.tsx
    ArtifactsRail.tsx
    MeetingsRail.tsx
    MobileMeetingsDrawer.tsx
    TopNav.tsx
  verify/
    EvidenceDrawer.tsx
    IssuesPanel.tsx
    TasksPanel.tsx
    VerifyPanel.tsx
```

## 5) Error and Edge States

- API errors normalized via `ApiError { message, status }`
- Not indexed yet -> explicit indexing messaging
- Failed docs -> reindex action
- Empty verify/tasks/issues -> explicit empty states
- No citations -> warning callout

## 6) What Is Working End-to-End

- Guest session token creation + scoped API calls
- Create/select meetings
- Upload files (single/multi)
- Observe indexing status polling
- Reindex failed docs
- Chat against indexed notes
- Verify extraction (summary, decisions, action items, issues)
- Refresh page and retain chat history from backend
- Open citation and inspect source chunk text

## 7) E2E Test Scaffold

- Config: `apps/web/playwright.config.ts`
- Spec: `apps/web/tests/e2e/meeting-flow.spec.ts`

Scenario covered:
- create session
- create meeting
- upload file
- poll to indexed
- chat
- verify
- refresh and confirm history visibility

## 8) Next Frontend Steps

1. Add chat feedback UI controls (`thumbs up/down`) wired to `POST /meetings/{id}/chat/feedback`
2. Replace custom mobile tab buttons with shadcn Tabs for accessibility parity
3. Add route-level `loading.tsx` / `error.tsx` for `(app)` and meeting pages
4. Add optimistic UI for uploads + richer progress states
5. Introduce shared motion tokens (duration/easing) for consistent transitions

## 9) Local Run (Frontend)

```bash
cd apps/web
npm install
npm run dev -- --port 3010
```

```bash
# apps/web/.env.local
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

Playwright:

```bash
cd apps/web
npm i -D @playwright/test
npx playwright install
npx playwright test
```
