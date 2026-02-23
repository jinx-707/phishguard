"""
Generate PhishGuard Extension Icons
Person 3: Client Security Engineer
"""
import base64
from pathlib import Path


def create_icon_svg(size: int) -> str:
    """Create SVG icon for PhishGuard"""
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#4A90E2;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#357ABD;stop-opacity:1" />
    </linearGradient>
  </defs>
  
  <!-- Background circle -->
  <circle cx="{size/2}" cy="{size/2}" r="{size/2-2}" fill="url(#grad)" stroke="#2C5F8D" stroke-width="2"/>
  
  <!-- Shield shape -->
  <path d="M {size/2} {size*0.2} 
           L {size*0.7} {size*0.35} 
           L {size*0.7} {size*0.6} 
           Q {size*0.7} {size*0.75} {size/2} {size*0.8}
           Q {size*0.3} {size*0.75} {size*0.3} {size*0.6}
           L {size*0.3} {size*0.35} Z" 
        fill="white" opacity="0.9"/>
  
  <!-- Checkmark -->
  <path d="M {size*0.4} {size*0.5} 
           L {size*0.47} {size*0.6} 
           L {size*0.62} {size*0.42}" 
        stroke="#4A90E2" stroke-width="{size*0.08}" 
        stroke-linecap="round" stroke-linejoin="round" fill="none"/>
</svg>'''


def svg_to_png_base64(svg_content: str, size: int) -> str:
    """Convert SVG to base64 encoded data URL"""
    # For simplicity, return SVG as data URL
    # In production, use cairosvg or similar to convert to PNG
    svg_b64 = base64.b64encode(svg_content.encode()).decode()
    return f"data:image/svg+xml;base64,{svg_b64}"


def create_icons():
    """Create all required icon sizes"""
    icons_dir = Path(__file__).parent
    
    sizes = [16, 48, 128]
    
    for size in sizes:
        svg_content = create_icon_svg(size)
        
        # Save SVG file
        svg_path = icons_dir / f"icon{size}.svg"
        with open(svg_path, 'w') as f:
            f.write(svg_content)
        
        print(f"Created {svg_path}")
    
    # Create README
    readme_content = """# PhishGuard Extension Icons

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
"""
    
    readme_path = icons_dir / "README.md"
    with open(readme_path, 'w') as f:
        f.write(readme_content)
    
    print(f"Created {readme_path}")
    print("\nIcons created successfully!")
    print("Note: SVG format created. For production, convert to PNG.")


if __name__ == "__main__":
    create_icons()
