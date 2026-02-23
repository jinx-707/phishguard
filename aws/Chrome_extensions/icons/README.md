# PhishGuard Extension Icons

## Icon Files

- `icon16.svg` - 16x16 toolbar icon
- `icon48.svg` - 48x48 extension management icon  
- `icon128.svg` - 128x128 Chrome Web Store icon

## Design

The PhishGuard icon features:
- Blue gradient background (security/trust)
- White shield (protection)
- Checkmark (verification/safety)

## Usage

These SVG icons are used in the Chrome extension manifest.json.
For production, convert to PNG format using:

```bash
# Using Inkscape
inkscape icon16.svg --export-png=icon16.png -w 16 -h 16
inkscape icon48.svg --export-png=icon48.png -w 48 -h 48
inkscape icon128.svg --export-png=icon128.png -w 128 -h 128
```

## Browser Compatibility

- Chrome/Edge: Supports both SVG and PNG
- Firefox: Supports both SVG and PNG
- Safari: PNG recommended

For maximum compatibility, use PNG format in production.
