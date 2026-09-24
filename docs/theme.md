# Phoenix Robot: Product Brand Identity & Design System (Theme Guide)

> **Codename:** Cybernetic Ember & Steel  
> **Brand Vision:** An autonomous emergency response robot combining industrial-grade robotics with advanced AI perception. The design language fuses deep molten ember tones, metallic anodized crimson, aerospace sky-blue accents, and stealth obsidian hardware.

---

## 🎨 Official Color Palette

| Token Name | Hex Code | RGB | HSL | Physical / Digital Application |
| :--- | :--- | :--- | :--- | :--- |
| `--brand-crimson` | `#7E1B2A` | `rgb(126, 27, 42)` | `351°, 65%, 30%` | **Robot Chassis Body** (Anodized metallic deep wine-red), UI Primary Accent |
| `--brand-crimson-glow`| `#991B1E` | `rgb(153, 27, 30)` | `359°, 67%, 36%` | Active hazard borders, emergency alert cards |
| `--accent-sky-blue` | `#0284C7` | `rgb(2, 132, 199)` | `200°, 98%, 39%` | **Wheel Rims & Nozzle Tip** (Anodized metallic blue), telemetry connection badges |
| `--accent-cyan-glow` | `#38BDF8` | `rgb(56, 189, 248)` | `198°, 93%, 60%` | Live MQTT status, active joystick highlights, sensor rings |
| `--fire-yellow` | `#FDE047` | `rgb(253, 224, 71)` | `48°, 96%, 64%` | Phoenix wingtips, primary fire sparkline peak |
| `--fire-amber` | `#FB923C` | `rgb(251, 146, 60)` | `27°, 96%, 61%` | Mid-wing gradient, manual override warning badge |
| `--fire-orange` | `#F97316` | `rgb(249, 115, 22)` | `25°, 95%, 53%` | Phoenix core flame, fire detected HUD banner |
| `--fire-red` | `#EF4444` | `rgb(239, 68, 68)` | `0°, 84%, 60%` | Phoenix tail feathers, critical casualty alerts |
| `--obsidian-bg` | `#0B0D14` | `rgb(11, 13, 20)` | `227°, 29%, 6%` | Main Web HUD background, dark UI backdrop |
| `--obsidian-surface`| `#121420` | `rgb(18, 20, 32)` | `231°, 28%, 10%` | Panel cards, sensor feed wrappers, modal surfaces |
| `--obsidian-glass` | `rgba(18, 20, 32, 0.82)` | - | - | Frosted glass HUD cards with `backdrop-filter: blur(16px)` |
| `--hardware-black` | `#18181B` | `rgb(24, 24, 27)` | `240°, 6%, 10%` | **2020 Aluminum Extrusions, LiDAR arch, Pan-Tilt gimbal bracket** |
| `--hardware-silver`| `#E2E8F0` | `rgb(226, 232, 240)`| `214°, 32%, 91%` | Diaphragm pump body, stainless hardware screws |

---

## 🦅 Brand Assets & Logos

### 1. Vector Silhouette Logo
* **Path:** `assets/phoenix_logo_vector.png` & `assets/phoenix_logo_vector.svg`
* **Characteristics:** High-contrast geometric vector silhouette with upward wings, diamond head, and stylized flame aperture tail feathers. Used for physical decals, laser etching, documentation, and print materials.

### 2. Animated Fire Emblem (Cybernetic Glow)
* **Path:** `assets/phoenix_logo_fire.png` & `assets/phoenix_logo_fire.svg` (active web emblem: `Phoenix_Web_Command_Center/images/phoenix_logo_fire.svg`)
* **Characteristics:** Radiant flame gradient (Yellow $\to$ Amber $\to$ Orange $\to$ Red) with ambient bloom on obsidian space and floating ember particles. Used in the Web Command Center topbar, digital presentation slides, and web hero sections.

### 3. Physical System Overview
* **Path:** `assets/phoenix_robot_physical.png` & `assets/Phoenix_Overview.png`
* **Characteristics:** The physical Phoenix mobile robot displaying the deep crimson body, sky-blue wheel rims, black arch, and onboard LiDAR/pump payloads.

---

## ✨ CSS Design Tokens & Animations

Include these tokens in any Phoenix web interface (`styles.css`):

```css
:root {
  /* Core Brand Colors */
  --brand-crimson: #7e1b2a;
  --brand-crimson-glow: #991b1e;
  --accent-sky-blue: #0284c7;
  --accent-cyan-glow: #38bdf8;
  
  /* Fire Gradient Tokens */
  --fire-yellow: #fde047;
  --fire-amber: #fb923c;
  --fire-orange: #f97316;
  --fire-red: #ef4444;
  --fire-gradient: linear-gradient(135deg, #fde047 0%, #fb923c 35%, #f97316 70%, #ef4444 100%);
  
  /* Obsidian Surfaces & Glass */
  --bg-primary: #0b0d14;
  --bg-surface: #121420;
  --glass-panel: rgba(18, 20, 32, 0.82);
  --glass-border: rgba(249, 115, 22, 0.22);
  --glass-border-active: rgba(249, 115, 22, 0.65);
  
  /* Status Colors */
  --status-ok: #00e5a0;
  --status-warn: #fb923c;
  --status-danger: #ef4444;
  --status-telemetry: #38bdf8;
}

/* Phoenix Breathing Fire Animation */
.phoenix-brand-logo {
  width: 46px;
  height: 46px;
  object-fit: contain;
  filter: drop-shadow(0 0 8px rgba(249, 115, 22, 0.65)) drop-shadow(0 0 16px rgba(239, 68, 68, 0.35));
  animation: phoenixFlameGlow 3s ease-in-out infinite alternate;
}

@keyframes phoenixFlameGlow {
  0% {
    filter: drop-shadow(0 0 6px rgba(249, 115, 22, 0.5)) drop-shadow(0 0 12px rgba(239, 68, 68, 0.25));
    transform: scale(1);
  }
  50% {
    filter: drop-shadow(0 0 12px rgba(253, 224, 71, 0.85)) drop-shadow(0 0 22px rgba(249, 115, 22, 0.7)) drop-shadow(0 0 35px rgba(239, 68, 68, 0.45));
    transform: scale(1.04);
  }
  100% {
    filter: drop-shadow(0 0 8px rgba(249, 115, 22, 0.6)) drop-shadow(0 0 16px rgba(239, 68, 68, 0.3));
    transform: scale(1);
  }
}
```

---

## 🤖 Gazebo & RViz Simulation Material Definitions

To ensure the Gazebo Harmonic and RViz 3D models match the real robot:

```xml
<!-- Chassis: Anodized Deep Metallic Crimson -->
<material>
  <ambient>0.45 0.10 0.15 1.0</ambient>
  <diffuse>0.55 0.12 0.18 1.0</diffuse>
  <specular>0.60 0.30 0.35 1.0</specular>
</material>

<!-- Wheel Rims: Anodized Sky Blue -->
<material>
  <ambient>0.02 0.45 0.75 1.0</ambient>
  <diffuse>0.05 0.55 0.90 1.0</diffuse>
  <specular>0.70 0.85 0.95 1.0</specular>
</material>

<!-- Structural Arch & Extrusions: Industrial Obsidian Black -->
<material>
  <ambient>0.08 0.08 0.08 1.0</ambient>
  <diffuse>0.10 0.10 0.10 1.0</diffuse>
  <specular>0.20 0.20 0.20 1.0</specular>
</material>
```

---
*Created for Project Phoenix — Autonomous Fire-Seeking & Rescue Mobile Robot.*
