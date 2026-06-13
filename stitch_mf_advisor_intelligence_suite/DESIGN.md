---
name: Echelon Financial
colors:
  surface: '#101415'
  surface-dim: '#101415'
  surface-bright: '#363a3b'
  surface-container-lowest: '#0b0f10'
  surface-container-low: '#191c1e'
  surface-container: '#1d2022'
  surface-container-high: '#272a2c'
  surface-container-highest: '#323537'
  on-surface: '#e0e3e5'
  on-surface-variant: '#c5c6cd'
  inverse-surface: '#e0e3e5'
  inverse-on-surface: '#2d3133'
  outline: '#8f9097'
  outline-variant: '#44474d'
  surface-tint: '#b9c7e4'
  primary: '#b9c7e4'
  on-primary: '#233148'
  primary-container: '#0a192f'
  on-primary-container: '#74829d'
  inverse-primary: '#515f78'
  secondary: '#b7c8e1'
  on-secondary: '#213145'
  secondary-container: '#3a4a5f'
  on-secondary-container: '#a9bad3'
  tertiary: '#4edea3'
  on-tertiary: '#003824'
  tertiary-container: '#001e11'
  on-tertiary-container: '#009466'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#d6e3ff'
  primary-fixed-dim: '#b9c7e4'
  on-primary-fixed: '#0d1c32'
  on-primary-fixed-variant: '#39475f'
  secondary-fixed: '#d3e4fe'
  secondary-fixed-dim: '#b7c8e1'
  on-secondary-fixed: '#0b1c30'
  on-secondary-fixed-variant: '#38485d'
  tertiary-fixed: '#6ffbbe'
  tertiary-fixed-dim: '#4edea3'
  on-tertiary-fixed: '#002113'
  on-tertiary-fixed-variant: '#005236'
  background: '#101415'
  on-background: '#e0e3e5'
  surface-variant: '#323537'
typography:
  display-lg:
    fontFamily: Geist
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Geist
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-lg-mobile:
    fontFamily: Geist
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  title-md:
    fontFamily: Geist
    fontSize: 20px
    fontWeight: '500'
    lineHeight: 28px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-caps:
    fontFamily: Geist
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
  mono-data:
    fontFamily: Geist
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
    letterSpacing: -0.01em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  base: 4px
  xs: 8px
  sm: 16px
  md: 24px
  lg: 40px
  xl: 64px
  gutter: 24px
  margin-desktop: 48px
  margin-mobile: 20px
---

## Brand & Style
The design system is engineered for a financial intelligence suite that demands precision, authority, and uncompromising trust. The brand personality is "Quiet Excellence"—sophisticated but highly functional. The target audience consists of analysts, fund managers, and high-net-worth individuals who require clarity over clutter.

The visual style is **Sophisticated Corporate Modernism** with **Strategic Glassmorphism**. It balances the stability of traditional finance with the innovative feel of modern fintech. By utilizing heavy whitespace and refined, low-opacity layers, the UI evokes a sense of deep focus and high-end exclusivity.

## Colors
This design system utilizes a dark-mode default to reduce eye strain during prolonged data analysis. 

- **Primary (#0A192F):** Deep Navy serves as the foundational "Canvas" color, providing a stable, professional backdrop.
- **Secondary (#64748B):** Slate Gray is used for secondary text, borders, and inactive states to maintain a low-friction visual hierarchy.
- **Tertiary/Accent (#10B981):** Emerald Green is the "Trust" color, reserved strictly for positive growth, success states, and primary calls to action.
- **Neutral (#F8FAFC):** Soft Ivory provides high-readability text and high-contrast highlights without the harshness of pure white.

## Typography
The typography system prioritizes clarity and high-density data legibility. **Geist** is used for headlines and labels to provide a technical, modern edge. **Inter** handles body copy and long-form data to ensure maximum readability across all devices.

Numerical data should utilize the `mono-data` role to ensure tabular alignment in financial reports. Use `label-caps` for metadata, category tags, and table headers to create a distinct separation between content and structure.

## Layout & Spacing
The layout follows a **Fluid Grid** model with strict 8px increments to maintain mathematical precision. 

- **Desktop:** 12-column grid with 24px gutters. Content is centered with a max-width of 1440px to ensure data doesn't become over-extended.
- **Tablet:** 8-column grid with 16px gutters and 32px side margins.
- **Mobile:** 4-column grid with 16px gutters and 20px side margins.

Margins are intentionally generous to create a premium, "breathable" feel, contrasting with the dense information often found in financial tools.

## Elevation & Depth
Depth is created through **Glassmorphic Tiers** rather than heavy shadows. 

1.  **Level 0 (Canvas):** The base background (#0A192F).
2.  **Level 1 (Panels):** A semi-transparent layer (rgba(255, 255, 255, 0.03)) with a 12px backdrop-blur. 
3.  **Level 2 (Modals/Popovers):** Higher opacity (rgba(255, 255, 255, 0.08)) with a 20px backdrop-blur and a 1px solid border (rgba(255, 255, 255, 0.1)) to define edges.

Shadows are used sparingly and should be "Ambient"—low opacity (15%), deep navy tint, and very large blur radius (32px+) to simulate natural light hitting a translucent surface.

## Shapes
The shape language is **Soft (0.25rem/4px base)**. This provides a professional, geometric look that feels more modern than sharp 90-degree corners but avoids the "playful" nature of highly rounded shapes. 

- Use `rounded-sm` (2px) for small interactive elements like checkboxes.
- Use `rounded-md` (4px) for standard buttons and input fields.
- Use `rounded-lg` (8px) for cards, modals, and container panels.

## Components
- **Buttons:** Primary buttons use the Emerald Green (#10B981) with Soft Ivory text. Secondary buttons are "Ghost" style: transparent background with a 1px Slate Gray border that brightens on hover.
- **Input Fields:** Dark background (primary color), 1px Slate Gray border, and Soft Ivory text. On focus, the border transitions to Emerald Green with a subtle outer glow.
- **Cards:** Utilize the Level 1 Glassmorphic style. Borders are 1px solid with 10% opacity white. Content inside should have 24px padding.
- **Chips/Status:** For financial status (e.g., "Market Open"), use small, pill-shaped indicators with a subtle pulse animation for real-time data points.
- **Data Tables:** Row separators use 1px solid #64748B at 20% opacity. Alternate row striping is discouraged; instead, use hover highlights to guide the eye.
- **Progress Indicators:** Use thin (2px) Emerald Green lines for loading states to maintain the minimal aesthetic.