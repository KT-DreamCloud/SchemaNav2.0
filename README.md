# schemaNav2.0

Local OpenAPI editor branded as **schemaNav2.0** — a personal Swagger Editor–style clone.

## Features

- Split view: Monaco editor + live Swagger UI preview
- Left sidebar: YAML view history (recently viewed specs, reopen anytime)
- Multiple spec tabs (rename, close, dirty indicator)
- Autosave to `localStorage` (`schemanav2.specs`)
- Open / Save-Export local `.yaml` / `.json` files
- YAML ↔ JSON conversion and Format/prettify
- Light / dark theme
- No backend, no cloud codegen calls

## Run

```bash
cd schemaNav2.0
npm install
npm run dev
```

Open the URL Vite prints (usually `http://localhost:5173`).

## Build

```bash
npm run build
npm run preview
```

## Notes

- Specs stay in your browser until you export them.
- Double-click a tab title to rename it.
- Validation uses local structural checks (openapi/swagger, info, paths) so the app stays fully offline.
