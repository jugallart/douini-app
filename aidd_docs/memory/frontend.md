# Frontend

## Web (web/)

React 19 + Vite 6 + react-router 7 + TanStack Query 5 + Tailwind CSS 3.4.

### Running

```bash
npm run dev:web    # Vite at :5173, proxies /api → localhost:8000
```

### Structure

```
web/src/
  main.tsx, router.tsx, index.css
  lib/          queryClient, tokenStore (localStorage)
  hooks/        useAuth, useProfile, usePlan, useGarmin
  components/
    ui/         Button, Input, Card, Alert, Spinner
    layout/     AuthLayout, AppShell
    plan/       WeekGrid, SessionCard, PaceTable, FeedbackDialog
    dashboard/  WeekView, ProgressBar, GarminBanner
  pages/
    auth/       Login, Signup, VerifyEmail, ForgotPassword, ResetPassword
    Dashboard, Plan, Profile, Pantheon, Settings, Wizard, NotFound
```

### Router

- Public: /login, /signup, /verify-email, /forgot-password, /reset-password
- Protected (requires token): /, /plan, /wizard, /profile, /pantheon, /settings
- Auth guard: no token → /login. Profile incomplete → /wizard.

### Wizard

4 steps: experience → target distance/time → sessions/week + days → recap. Submit: PUT /profile + POST /plans/generate → redirect /.

## Mobile (mobile/)

Expo SDK 53 + expo-router 4 + TanStack Query 5 + expo-secure-store.

### Running

```bash
npm run dev:mobile    # Expo dev server
```

### Structure

```
mobile/
  app/
    _layout.tsx           Root: QueryClientProvider, auth check, splash
    (auth)/               Stack: login, signup, verify-email
    (app)/                Tabs: Dashboard, Plan, Profile
      plan/{index,[id]}.tsx
    wizard/index.tsx
  components/             SessionCard, WeekList, PaceTable
  lib/                    queryClient, tokenStore (expo-secure-store)
```

## Shared package (@douini/shared)

TypeScript types + API client consumed by both web and mobile.

- `api/client.ts`: `apiFetch<T>` with JWT injection, 401→refresh+retry once, `TokenStorage` interface (injectable), `configureClient(storage)`.
- `types/`: mirror Pydantic schemas (auth, profile, plan, session, garmin, race).
- `api/`: one module per domain (auth, plans, profile, sessions, garmin, race_results).

### Typecheck

```bash
npm run build:shared    # tsc packages/shared
npx tsc --noEmit -p web/tsconfig.app.json
npx tsc --noEmit -p mobile/tsconfig.json
```
