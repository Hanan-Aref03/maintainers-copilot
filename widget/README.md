# Maintainer's Copilot Widget

This folder contains the embeddable React widget used by the demo app.

## Development

```powershell
cd widget
npm install
npm run dev
```

## Production Build

```powershell
cd widget
npm run build
```

The production bundle is served from `widget/dist/widget.js` and is loaded by the API at:

```text
/widgets/widget.js?widget_id=<public_id>
```

The runtime configuration is injected through `window.__COPILOT_WIDGET_CONFIG__` before the bundle runs.
