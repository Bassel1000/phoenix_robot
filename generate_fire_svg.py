import os
import re

def create_svgs():
    with open('assets/phoenix_from_rgba.svg', 'r', encoding='utf-8') as f:
        content = f.read()

    path_matches = re.findall(r'(<path[^>]*d="[^"]*"[^>]*>)', content)
    valid_paths_grad = []
    valid_paths_mono = []
    
    for p in path_matches:
        d_search = re.search(r'd="([^"]*)"', p)
        if d_search and len(d_search.group(1)) > 10:
            p_grad = re.sub(r'fill="[^"]*"', 'fill="url(#fireGrad)"', p)
            valid_paths_grad.append(p_grad)
            p_mono = re.sub(r'fill="[^"]*"', 'fill="currentColor"', p)
            valid_paths_mono.append(p_mono)

    print(f"Extracted {len(valid_paths_grad)} valid paths.")

    # 1. Animated Fire SVG
    svg_fire = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="62 -35 900 900" width="100%" height="100%">
  <defs>
    <!-- Core Molten Flame Gradient matching theme.md -->
    <linearGradient id="fireGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#FDE047">
        <animate attributeName="stop-color" values="#FDE047;#FEF08A;#FDE047" dur="2.8s" repeatCount="indefinite" />
      </stop>
      <stop offset="22%" stop-color="#FB923C">
        <animate attributeName="stop-color" values="#FB923C;#FDBA74;#FB923C" dur="2.8s" repeatCount="indefinite" />
      </stop>
      <stop offset="55%" stop-color="#F97316">
        <animate attributeName="stop-color" values="#F97316;#EA580C;#F97316" dur="2.8s" repeatCount="indefinite" />
      </stop>
      <stop offset="85%" stop-color="#EF4444">
        <animate attributeName="stop-color" values="#EF4444;#DC2626;#EF4444" dur="2.8s" repeatCount="indefinite" />
      </stop>
      <stop offset="100%" stop-color="#7E1B2A" />
    </linearGradient>

    <!-- Radial Core Heat Glow -->
    <radialGradient id="emberAura" cx="50%" cy="45%" r="45%">
      <stop offset="0%" stop-color="#F97316" stop-opacity="0.38">
        <animate attributeName="stop-opacity" values="0.25;0.48;0.25" dur="2.2s" repeatCount="indefinite" />
      </stop>
      <stop offset="50%" stop-color="#EF4444" stop-opacity="0.18">
        <animate attributeName="stop-opacity" values="0.12;0.28;0.12" dur="2.2s" repeatCount="indefinite" />
      </stop>
      <stop offset="100%" stop-color="#0B0D14" stop-opacity="0" />
    </radialGradient>

    <style>
      .phoenix-silhouette {{
        transform-origin: 512px 415px;
        animation: phoenixPulse 2.8s ease-in-out infinite alternate;
        filter: drop-shadow(0 0 10px rgba(249, 115, 22, 0.75)) drop-shadow(0 0 25px rgba(239, 68, 68, 0.45));
      }}
      @keyframes phoenixPulse {{
        0% {{
          transform: scale(0.985);
          filter: drop-shadow(0 0 8px rgba(249, 115, 22, 0.6)) drop-shadow(0 0 18px rgba(239, 68, 68, 0.35));
        }}
        50% {{
          transform: scale(1.02);
          filter: drop-shadow(0 0 18px rgba(253, 224, 71, 0.95)) drop-shadow(0 0 35px rgba(249, 115, 22, 0.75)) drop-shadow(0 0 55px rgba(239, 68, 68, 0.5));
        }}
        100% {{
          transform: scale(0.985);
          filter: drop-shadow(0 0 8px rgba(249, 115, 22, 0.6)) drop-shadow(0 0 18px rgba(239, 68, 68, 0.35));
        }}
      }}
    </style>
  </defs>

  <!-- Ambient Flame Aura in Background -->
  <circle cx="512" cy="380" r="320" fill="url(#emberAura)" />

  <!-- The Vector Phoenix Silhouette (Pure Original Geometry, 100% Transparent Background) -->
  <g class="phoenix-silhouette">
    {''.join(valid_paths_grad)}
  </g>
</svg>
'''

    # 2. Clean Vector Silhouette SVG (monochrome / scalable)
    svg_vector = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="62 -35 900 900" width="100%" height="100%">
  <g fill="currentColor">
    {''.join(valid_paths_mono)}
  </g>
</svg>
'''

    files = [
        ('assets/phoenix_logo_fire.svg', svg_fire),
        ('Phoenix_Web_Command_Center/images/phoenix_logo_fire.svg', svg_fire),
        ('assets/phoenix_logo_vector.svg', svg_vector),
        ('Phoenix_Web_Command_Center/images/phoenix_logo_vector.svg', svg_vector)
    ]
    for path, data in files:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(data)
        print(f"Wrote {path} ({len(data)} bytes)")

if __name__ == '__main__':
    create_svgs()
