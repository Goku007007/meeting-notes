# Frontend Plan and Current Architecture (Next.js)

This document captures the current frontend architecture and the next implementation steps.

Backend contract reference: `backendap.md`

## 1) Stack

- Next.js (TypeScript, App Router)
- Tailwind CSS
- shadcn/ui
- TanStack Query
- lucide-react
- sonner (toasts)

## 2) Implemented Architecture

## 2.1 Routing

- `src/app/layout.tsx`
  - root HTML/body + `Providers`
- `src/app/(app)/layout.tsx`
  - app shell wrapper (`AppShell`)
- `src/app/(app)/page.tsx`
  - home screen
- `src/app/(app)/meetings/[meetingId]/page.tsx`
  - meeting workspace

This route-group approach keeps URLs clean while sharing shell layout.

## 2.2 Shell UX

Desktop:
- Left rail: meetings list + create meeting + home
- Center: workspace (chat-focused)
- Right rail: artifacts tabs (`Verify`, `Tasks`, `Issues`, `Docs`)

Mobile:
- top nav + meetings drawer
- in-workspace tabs (`Chat`, `Verify`, `Docs`)

## 2.3 Data Layer

React Query keys in use:
- `['meetings']`
- `['meeting', meetingId]`
- `['meeting-documents', meetingId]`
- `['verify', meetingId]`

Polling:
- `useMeetingDocuments(meetingId)` polls every 2s while any doc is `pending|processing`
- polling stops when all docs are terminal

## 2.4 Chat UX (Current)

- Composer with attachments (`Attach` + `Send`)
- Message bubbles with citation chips
- Citation drawer
- No-citation callout
- Loading animation (`Thinking...`) and smooth message transitions
- Auto-scroll to latest message
- Chat history persisted per meeting in browser localStorage

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
- No indexed chunks yet -> explicit indexing state messaging
- Failed docs -> reindex action visible
- Empty verify/tasks/issues -> explicit empty-state copy
- No citations -> warning callout under assistant message

## 6) What Is Working End-to-End

- Create meeting
- Upload file(s)
- Observe background indexing status
- Reindex failed docs
- Chat against indexed notes
- Verify extraction (summary, decisions, actions, issues)
- Switch meetings from rail

## 7) Next Frontend Steps

1. Add server-backed chat history endpoint integration (cross-device persistence)
2. Improve citation UX (show quote snippets inline, de-duplicate repeated chunk chips)
3. Add route-level `loading.tsx` / `error.tsx` for app and meeting routes
4. Add document filters/search in docs tab
5. Add subtle animation system consistency (durations/easings centralized)

## 8) Local Run (Frontend)

```bash
cd apps/web
npm install
npm run dev -- --port 3010
```

Set API URL:

```bash
# apps/web/.env.local
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```
