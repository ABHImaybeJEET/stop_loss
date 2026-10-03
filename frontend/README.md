# StopLoss Intelligence Terminal: Frontend

Next.js 14 (App Router, TypeScript, Tailwind, recharts, lucide-react, Firebase Auth/Firestore).

## Run it

```bash
# 1. Backend (from repo root): live data + LangGraph agents on 127.0.0.1:8000
cd backend && uv sync && uv run stop-loss-api

# 2. Frontend
cd frontend && npm install && npm run dev   # http://localhost:3000
```

`frontend/.env.local` (never committed):

```
NEXT_PUBLIC_FIREBASE_API_KEY=...            # Firebase web config (public by design)
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=...
NEXT_PUBLIC_FIREBASE_PROJECT_ID=...
NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=...
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=...
NEXT_PUBLIC_FIREBASE_APP_ID=...
BACKEND_URL=http://127.0.0.1:8000           # server-side only
BACKEND_INTERNAL_TOKEN=                     # = API_INTERNAL_TOKEN in the root .env
```

Set `OPENAI_API_KEY` in the root `.env` for LLM-written narratives. Without it, the agents still run on real data and produce deterministic, evidence-only text ("rules mode").

## `/chat`: Asset analysis terminal

1. Pick an asset (live Yahoo search), write a prompt, press **Enter**.
2. The orchestration panel streams all 8 agents (queued → running → done/error) with live step text and timers, then collapses to a summary bar. Click it to re-open the agent log.
3. Sections render in this order, progressively as data arrives: **Asset Snapshot → Real-time Sources → Historical Analysis → Live Chart → Suggestions → Risk & Trust → Feedback**.
4. Follow-ups stay in the same thread (agents keep memory). Switching assets inserts a "Now analyzing" divider.

Every figure in generated text is checked against the evidence catalog. `[E#]` chips link to the source, and the full audit trail sits inside the Risk & Trust panel.

## Architecture

```
app/chat/page.tsx                    thin shell (auth guard + Suspense)
components/chat/                     ChatTerminal (container), Composer, AssetCombobox,
                                     MessageList, UserMessage, AssistantTurn,
                                     OrchestrationPanel, AgentRow, sections/*,
                                     AssetLiveChart, RiskTrustPanel, ScoreGauge,
                                     FeedbackBar, ThreadSidebar, EvidenceText
components/ui/primitives.tsx         Card, SectionCard, Button, Badge, Skeleton, Input
lib/chat/types.ts                    normalized UI types (the contract)
adapters/backendToUi.ts              zod-validated snake_case → UI mapping (only place
                                     that knows the backend wire format)
lib/chat/useChatStream.ts            run lifecycle: SSE reducer, stop/cancel, retry,
                                     auto-resume, re-attach after reload
lib/chat/useThreads.ts               Firestore + localStorage thread persistence
lib/server/backend.ts                Firebase ID-token verification + backend proxying
app/api/{chat,chat/runs/*,market/*,assets/search,feedback}/route.ts
```

## Firestore rules

Threads live under the signed-in user. Minimum rules:

```
match /users/{uid}/{document=**} {
  allow read, write: if request.auth != null && request.auth.uid == uid;
}
```

If writes are denied, threads are kept in localStorage on that device and the sidebar says so.

## Checks

```bash
npm run typecheck && npm run lint && npm run build
E2E_EMAIL=... E2E_PASSWORD=... npm run test:e2e   # real stack; skipped without credentials
```

Install the browser once with `npx playwright install chromium`.
