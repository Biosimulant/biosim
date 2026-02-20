# SimUI Frontend (clean scaffold)

This is a minimal, clean Vite + React + TypeScript frontend that builds to a single `dist/app.js` file consumed by the Python `biosim.simui` package.

- React 18, Vite 5, TS 5
- Single-file JS bundle: `dist/app.js` (CSS inlined)
- Typed API client in `src/lib/api.ts`
- Config/mount-path resolver in `src/lib/config.ts`
- Simple provider in `src/app/providers.tsx`

## Scripts

- `npm run dev` — local dev server
- `npm run build` — production bundle to `dist/app.js`
- `npm run preview` — preview the production bundle

## Structure

- `src/app` — app-wide providers
- `src/components` — reusable UI
- `src/hooks` — custom hooks
- `src/lib` — API, utilities
- `src/styles` — global styles

## Building into Python package

The Python wrapper expects `dist/app.js`. From repo root:

```
python -m biosim.simui.build
```

That script installs deps and runs the Vite build, copying `dist/app.js` into `src/biosim/simui/static/app.js`.
