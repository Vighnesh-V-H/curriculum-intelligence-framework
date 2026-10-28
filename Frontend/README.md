# Curriculum Intelligence Frontend

Next.js (App Router) frontend for the AI-Powered Curriculum Intelligence &
Verification Framework.

## Development

```bash
npm install
cp .env.example .env.local
npm run dev
```

The app runs at `http://localhost:3000` and calls the FastAPI backend at
`NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).

## Pages

- `/login` — sign in with username or email and a password.
- `/dashboard` — displays the authenticated user, roles, and account status.

Authentication uses the backend-issued JWT stored in `localStorage`. All
authorization decisions are enforced by the FastAPI API; the frontend only
controls navigation and presentation.

## Scripts

- `npm run dev` — start the development server.
- `npm run build` — production build.
- `npm run lint` — run ESLint.
