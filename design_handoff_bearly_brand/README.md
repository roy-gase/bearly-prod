# Handoff: Bearly brand mark + chat avatar

## Overview
Visual identity for **Bearly**, a personal-finance AI agent app. This bundle contains the approved logo
("Stash", direction 2a), an in-app bear character avatar, and an animated version of that avatar for the
chat composer (idle / listening / thinking states). Four rejected logo directions are included in the same
file as turn 1 for context only — **do not build them**.

## About the Design Files
The files here are **design references authored in HTML**. They are prototypes that show intended look and
motion — not production code to lift wholesale. The task is to **recreate these designs in the app's existing
environment** (React / React Native / SwiftUI / Vue — whatever the codebase already uses), following its
established component patterns, tokens, and icon conventions. If no environment exists yet, pick the
framework that fits the product and implement there.

The SVG markup itself IS production-usable: the mark and avatars are built entirely from circles, ellipses and
two-point arcs, so the paths can be copied verbatim into an icon component. Everything else (page chrome,
option cards, id badges, mono captions) is presentation scaffolding for review and should be discarded.

## Fidelity
**High fidelity.** Colors, geometry, type, and animation timings are final. Recreate pixel-accurately.
The one open item is the wordmark typeface — see "Typography".

## Screens / Views

### 1. Logo lockup — "Stash" (option 2a, approved)
- **Purpose**: primary brand lockup for marketing, splash, app header.
- **Layout**: horizontal flex row, `align-items: center`, `gap: 20px`. Mark left, wordmark right.
- **Mark**: SVG, `viewBox="0 0 100 100"`, rendered at 88×88 in the mock; scales freely, legible to 16px.
  Geometry (fill values exact):
  - ear L: `circle cx=26 cy=26 r=12` — #8B5E34
  - ear R: `circle cx=74 cy=26 r=12` — #8B5E34
  - head: `circle cx=50 cy=55 r=30` — #8B5E34
  - muzzle: `ellipse cx=50 cy=66 rx=15 ry=11.5` — #F6E7CE
  - eye L: `circle cx=38 cy=50 r=3.4` — #241A12
  - eye R: `circle cx=62 cy=50 r=3.4` — #241A12
  - nose: `circle cx=50 cy=61 r=4.2` — #241A12
  Note: an earlier revision had a three-ellipse coin stack behind the bear. It was **removed**. Do not reinstate.
- **Wordmark**: "Bearly" — 42px, letter-spacing −0.03em, color #1A1611. "Bear" at weight 500, "ly" at weight 700
  (single text node, two spans).
- **App icon**: 46×46, `border-radius: 12px` (i.e. 26% of side — use the platform's own mask on iOS/Android),
  background #F6E7CE, mark inset to ~74% of the tile at 34×34, nose omitted at this size.
- **Single-color / monochrome**: ears + head only (drop muzzle, eyes, nose), `fill: currentColor`, 22×22 next to a
  15px/700 wordmark. This is the favicon / dark-UI / embossed variant.
- **Clearspace**: minimum one ear-diameter (24 units of the 100 viewBox) on all sides.

### 2. Character avatar (static, in-app)
- **Purpose**: profile/identity for the agent in lists, message rows, onboarding illustrations, empty states.
- **Layout**: circular badge, `clip-path: circle(50%)` — anything drawn past the circle must be clipped, the
  shoulders deliberately overflow the viewBox.
- **Geometry**: SVG `viewBox="0 0 120 120"`, rendered 112×112.
  - badge bg: `circle cx=60 cy=60 r=60` — #F6E7CE (avatar) / #F0D9B5 (composer variant, for contrast against the pill)
  - shoulders: `ellipse cx=60 cy=122 rx=34 ry=26` — #7A4F2A
  - ear L: `circle cx=27 cy=38 r=14` #8B5E34 + inner `r=6.5` #C89A6B
  - ear R: `circle cx=93 cy=38 r=14` #8B5E34 + inner `r=6.5` #C89A6B
  - head: `circle cx=60 cy=64 r=33` — #8B5E34
  - muzzle: `ellipse cx=60 cy=79 rx=19 ry=14` — #F0D9B5
  - brows: `path M40 51 Q46 47 52 50` and `M68 50 Q74 47 80 51`, stroke #5E3D1F, width 2.6, round caps
  - eyes: `circle cx=46/74 cy=61 r=4.4` #241A12, each with a highlight `circle r=1.5` at (+1.3, −1.3) in #FFFDF9
  - nose: `ellipse cx=60 cy=72 rx=5.6 ry=4.4` — #241A12
  - mouth: `path M53 81 Q60 87 67 81`, stroke #241A12, width 2.8, round caps
  - blush: `ellipse cx=36/84 cy=70 rx=6 ry=4.6` — #C4703C at 45% opacity
- **Reduced variant (≤40px)**: drop brows, eye highlights, blush, and inner ears; keep ears, head, muzzle, eyes, nose.

### 3. Animated chat avatar (composer)
- **Purpose**: sits beside the chat input so the agent feels present and conversational.
- **Large state (132×132 wrapper)**: avatar at 124×124 plus a "listening" ring — an absolutely positioned
  `inset: 0` div, `border-radius: 50%`, `border: 2px solid #C89A6B`, pulsing outward.
- **Composer pill**: flex row, `gap: 12px`, background #F8F2E7, border 1px #E7DCC7, `border-radius: 999px`,
  padding `9px 18px 9px 10px`; 40px avatar at left; placeholder "Ask Bearly where your money went…" at
  14px / #6B6252.
- **Thinking state**: 40px inverted avatar (#8B5E34 badge, #F0D9B5 bear) beside a bubble — background #F0E5D2,
  `border-radius: 14px 14px 14px 4px`, padding `12px 14px`, three 6px #8B5E34 dots.

## Interactions & Behavior
Animation is pure CSS on nested SVG groups. Every animated group needs `transform-box: fill-box` plus its own
`transform-origin`; the loops are deliberately co-prime-ish so the character never reads as a short GIF loop.

| Name | Keyframes | Duration / easing | Applied to | Origin |
|---|---|---|---|---|
| `bl-sway` | rotate −1.8° → +1.8°, translateY 0 → −2px at 50% | 4.2s ease-in-out infinite | whole bust group | 50% 90% |
| `bl-breathe` | scale 1 → 1.04 at 50% | 3.4s ease-in-out infinite | head + face group | 50% 80% |
| `bl-blink` | scaleY 1, hold to 90%, 0.08 at 94%, back to 1 | 5.6s ease-in-out infinite | eyes group | 50% 50% |
| `bl-ear` | rotate 0 → −9° at 90% → +5° at 95% → 0 | 6s ease-in-out infinite (right ear +0.35s delay) | each ear group | 80% 90% / 20% 90% |
| `bl-brow` | translateY 0 → −3px at 80% | 5.2s ease-in-out infinite | brows group | 50% 50% |
| `bl-ring` | scale 1 / opacity .4 → scale 1.35 / opacity 0 | 2.6s ease-out infinite | listening ring | center |
| `bl-dot` | translateY 0 → −4px, opacity .35 → 1 | 1.1s ease-in-out infinite, dots delayed 0 / .18s / .36s | typing dots | center |

State mapping for the composer:
- **idle** — sway + breathe + blink + ear twitch + brow raise. No ring.
- **listening** (input focused or mic active) — as idle, plus `bl-ring`.
- **thinking / streaming** — inverted avatar + typing-dot bubble; keep blink at a faster 4.4s, drop the brow raise.
- **reduced motion** — under `@media (prefers-reduced-motion: reduce)` disable all of the above and render the
  static avatar; keep the typing dots as a non-motion indicator (e.g. opacity fade) or a text label.

Hover/press states were not specified for the avatar; if it becomes a button, use a 1.03 scale on press and a
2px #C89A6B focus ring at 2px offset.

## State Management
Minimal. One enum drives the avatar: `avatarState: 'idle' | 'listening' | 'thinking'`.
- `idle → listening` on composer focus / voice capture start
- `listening → thinking` on submit
- `thinking → idle` when the response finishes streaming
No data fetching belongs to these components.

## Design Tokens
Colors
- bear fur: #8B5E34 · fur shadow / shoulders: #7A4F2A · inner ear: #C89A6B
- muzzle light: #F6E7CE · muzzle mid: #F0D9B5 · bubble fill: #F0E5D2
- ink (features): #241A12 · brow: #5E3D1F · blush: #C4703C @ 45%
- text primary: #1A1611 · text secondary: #6B6252 · text on dark: #B3A68B
- page bg: #F3EEE6 · card / surface: #FFFDF9 · composer bg: #F8F2E7
- hairlines: #E3DACB (card), #EFE7D9 (inner divider), #E7DCC7 (composer)
- link: #8F5A1E, hover #1A1611
- accent gold (used in rejected directions only, retain as a secondary if useful): #F0B843
All small text was tuned to clear 4.5:1 against its own surface — preserve those pairings.

Spacing: 6 · 9 · 12 · 14 · 18 · 20 · 22 · 26 · 28 · 32 (px)
Radius: 4 (bubble tail) · 12 (app icon tile) · 14 (bubble) · 16 · 20 (card) · 999 (pill) · 50% (avatar)
Type scale: 42 (lockup) · 30 (H1) · 17 · 15 · 14 (body/UI) · 12.5 · 11.5 · 11 · 10.5 (mono eyebrow)
Shadows: none anywhere. The system is flat with hairline borders.

## Typography
- Wordmark + UI: **Space Grotesk** (400 / 500 / 700), Google Fonts. Lockup uses 500 for "Bear" + 700 for "ly",
  letter-spacing −0.03em.
- Mono labels and captions: **DM Mono** (400 / 500), letter-spacing .08–.14em when uppercased.
- **Baloo 2** appears only in the rejected directions 1b / 1e — not part of the approved system.
- Open item: Space Grotesk is a stand-in for a licensed brand face. If the team licenses a custom wordmark,
  the mark geometry is unaffected.

## Assets
No raster assets, no icon fonts, no third-party illustrations. Every graphic is inline SVG defined in this
README and in the HTML file. Fonts load from Google Fonts (`fonts.googleapis.com` / `fonts.gstatic.com`) —
self-host them in production.

## Exported assets (`assets/`)
Source SVGs (authoritative — prefer these; they are the same geometry documented above):
- `bearly-mark.svg` — full-color mark, transparent background
- `bearly-mark-mono.svg` — single-color silhouette (ears + head), #1A1611; recolor freely
- `bearly-icon.svg` — app-icon tile, #F6E7CE ground, 26% corner radius
- `bearly-avatar.svg` — circular character avatar

PNG rasters, all square and transparent except the icon/avatar grounds:
- mark: 1024 / 512 / 256
- mark-mono: 512 / 64
- icon: 1024 (store) / 512 / 192 (Android) / 180 (iOS) / 32 / 16 (favicon)
- avatar: 1024 / 256 / 80

## Files
- `Bearly Logo Options.dc.html` — the full design file. Turn 2 (top of the page) is the approved work:
  option **2a** = final logo, option **2b** = character avatar + animated composer states. Turn 1 below it is
  the original five-direction exploration (1a Coin Bear, 1b Bear Bank, 1c Stash — the chosen direction before
  coin removal, 1d Penny Nose, 1e Cheeks Full), kept for reference only.
- Keyframes `bl-sway`, `bl-breathe`, `bl-blink`, `bl-ear`, `bl-brow`, `bl-dot`, `bl-ring` are defined in the
  `<style>` block at the top of that file.

## Suggested implementation order
1. `BearMark` — the logo SVG, props: `size`, `variant: 'full' | 'mono' | 'icon'`.
2. `BearAvatar` — static character, props: `size`, `detail: 'full' | 'reduced'`, `inverted`.
3. `BearAvatarLive` — wraps `BearAvatar` with the keyframe groups and the `avatarState` enum + reduced-motion guard.
4. Composer integration: pill, placeholder, thinking bubble.
