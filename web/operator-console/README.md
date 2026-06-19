# web/operator-console

Operator-facing console for The Line. React + WebGL. The headline view is a
live floor-by-floor heatmap covering all onboarded modules.

Tracks [KAN-26](https://dib-test1.atlassian.net/browse/KAN-26). Active P1
bug: [KAN-49](https://dib-test1.atlassian.net/browse/KAN-49) — heatmap
freezes on Modules 12-14.

## Stack

- Vite + React 18 + TypeScript
- WebGL via `regl`
- Live data over WebSocket (GraphQL subscriptions)
- Auth via NEOM SSO (OIDC)

## Run

```bash
npm install
npm run dev       # localhost:5173
```

Set `VITE_API_BASE=https://twin-api.dev.neom.internal` in `.env.local`.

## Layout

```
src/
  api/                  GraphQL client + subscription wiring
  components/
    Heatmap.tsx         WebGL floor-by-floor heatmap (this is where KAN-49 lives)
    ModuleStrip.tsx     Top-of-screen module status strip
    AlertDrawer.tsx     Side drawer for active anomaly alerts
    PodTimeline.tsx     Pod corridor timeline (KAN-27)
  hooks/
    useLiveTelemetry.ts WS subscription helper
  routes/
    Dashboard.tsx       Composes the above
public/                 Static assets
```
