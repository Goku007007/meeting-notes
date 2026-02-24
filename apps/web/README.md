# meeting-notes web

Next.js frontend for the meeting-notes project.

## Tech

- Next.js (App Router, TypeScript)
- Tailwind CSS
- shadcn/ui
- TanStack Query
- sonner

## Prerequisites

- Node 20+
- Backend API running at `http://127.0.0.1:8000`

## Environment

Create `apps/web/.env.local`:

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

## Install and Run

```bash
cd apps/web
npm install
npm run dev -- --port 3010
```

Open: `http://localhost:3010`

## Build

```bash
npm run build
npm start
```

## Current UX

- Desktop shell with left meetings rail + center chat + right artifacts rail
- Mobile meetings drawer and workspace tabs
- Attachment-based chat composer
- Polling document status during indexing
- Verify panel for structured artifacts
- Guest token auth (auto session creation)
- DB-backed per-meeting chat history persistence across refresh/device
- Citation drawer with server chunk inspection

## E2E (Playwright)

```bash
cd apps/web
npm i -D @playwright/test
npx playwright install
npx playwright test
```

## Key Source Paths

- Routing: `src/app/(app)/...`
- Shell: `src/components/shell/`
- Workspace: `src/components/layout/MeetingWorkspace.tsx`
- Chat: `src/components/chat/`
- Documents: `src/components/documents/`
- Verify: `src/components/verify/`
- Query hooks: `src/lib/queries/`
- API client: `src/lib/api.ts`
