# 18. Interface brief: Quiet Ledger

This brief applies the three UI/UX prompts supplied on 29 September 2026 (Anti-Slop UI/UX Fixer v2, the Anti-Slop
UI/UX Repair Protocol and the UI/UX Refinement Master Prompt) together with the earlier Strict UI/UX constraints (no
`box-shadow`, no `linear-gradient`, flat hover states, no scale transforms, strict tokens).

Each prompt asks twelve questions before any change. The owner asked for the work to go ahead, so the answers below
were taken from the repository, the product specification and the owner's earlier instructions. Every answer is
marked **Confirm**: reply with a different answer and the design will be adjusted.

## 1. Discovery answers (Confirm)

| # | Question (merged across the three prompts) | Answer |
|---|---|---|
| 1 | Product, purpose and the one action that matters | Marketing Decision OS: turn a business question into evidence, scenarios and journey fixes. On every screen the primary action is the **next step** of the loop (design, analyze, approve, simulate, test). |
| 2 | Primary users and their skill | Marketers, researchers and SME owners in Indonesia. Comfortable with spreadsheets, not with statistics jargon. Often on laptops, sometimes on phones between meetings. |
| 3 | Taste reference and feeling | Linear (hierarchy, density, borders instead of shadows) and Stripe Dashboard (numbers first, tables that read well). Feeling: calm, credible, precise. |
| 4 | Visual references | None supplied. Principles are taken from the two products above, not their visuals. |
| 5 | Locked brand assets and colors | The existing validated palette (docs/09-design-system.md): warm paper neutrals and one blue accent (`#1c5cab` light, `#256abf` dark). The GitHub pages use the owner's preferred DeepSeek style (clean, blue, numbered sections). |
| 6 | Typography | IBM Plex Sans for the interface, IBM Plex Mono for evidence codes, IDs and code. Bundled with the app (works offline, allowed by the Content Security Policy). Two weights on screen: 400 and 600. |
| 7 | Component library and new packages | Keep the in-house primitives in `src/components/ui`; no UI library. Only new packages: the two Plex font packages (static font files, no scripts, OFL licence). |
| 8 | Must keep / must kill | Keep: sidebar plus tabs navigation, color-blind-safe charts with table views, approvals and evidence flows. Kill: shadows, the gradient, cards around every block, cards inside cards, repeated success pills, sparkle icons on buttons, duplicated numbers. |
| 9 | States that matter most | 1) first run and empty project, 2) loading (skeletons), 3) errors (not found, server unreachable, locked desktop link). |
| 10 | Density and devices | Balanced to data-dense on desktop (analysis tool); fully usable at 390 px wide. Light, dark and system themes. |
| 11 | Motion and accessibility | Minimal motion: one 120 ms color transition for hover and focus, one 160 ms entrance for toasts and the mobile menu. Reduced motion respected. WCAG 2.2 AA contrast, visible 2 px focus ring, full keyboard path. |
| 12 | Process | Whole product, owner away: brief, then implementation, then up to three screenshot critique cycles at desktop and mobile widths with Playwright. |

## 2. Diagnosis of the interface before this pass

**Top visual problems**

1. Every block sits in a bordered card with a shadow; Strategy nests stat boxes inside the scenario card.
2. The accent blue is everywhere (nav, banners, callouts, chips, buttons, badges), so nothing is emphasized.
3. Green "Succeeded" pills repeat on every agent step, and 21 green tiles fill the research workflow.
4. System fonts with bold on tabs, labels, badges and titles at once: many weights compete.
5. Mixed label styles (uppercase tracked labels next to sentence case) and several radii (6, 8, 10, 14 px).

**Top UX problems**

1. The research dashboard leads with an agent log instead of what to do next and what is already known.
2. Home offers two competing starts (create a project, load the demo) and hides returning users' projects below the fold.
3. A broken project link spins "Loading" for seconds (404 responses were retried) and the switcher shows the wrong project.
4. Journey stage columns run off the right edge; charts in a row are stretched to equal heights, leaving empty space.
5. On phones, the four key numbers stack in one tall column and tab rows are cut off without a hint that they scroll.

**Redundant or unnecessary elements**

1. Strategy repeats customers and profit in the funnel and again in the stat row.
2. The static "How the lab keeps research defensible" panel takes half the dashboard width.
3. The sidebar subtitle "Research · Strategy · Journey" repeats the navigation.
4. Success pills and sparkle icons that carry no information.
5. The Home banner says "Offline mode. Offline mode: ..." (duplicated copy).

## 3. Five directions

| # | Direction | Palette (max 3 hues) | Type | Radius and density | Layout sketch | Empty and error feel | Fit | Risk |
|---|---|---|---|---|---|---|---|---|
| 1 | **Quiet Ledger** (chosen) | Warm paper `#f9f9f7`, ink `#0b0b0b`, blue `#1c5cab` | IBM Plex Sans + Plex Mono | 8 px everywhere, pills only for status; balanced to dense | Left-aligned pages, sections separated by space and hairlines, cards only for discrete objects (a project, an insight, a scenario) | One sentence, one primary action, left-aligned in a narrow column | Credible and calm for decisions; honors the no-shadow, no-gradient rule | Can feel austere; relies on typography doing the hierarchy |
| 2 | Editorial Warm | Cream `#fbf8f2`, ink `#1b1b1b`, terracotta `#b4532a` | Newsreader + Source Sans 3 | 4 px, airy | Reports as journal pages, wide margins | Illustrative, reflective copy | Great for reports | Too airy for tables; terracotta collides with warning and negative colors |
| 3 | Dense Tool | Near black `#0e0f11`, gray, amber `#f0a500` | IBM Plex Mono throughout | 2 px, compact 13 px | Terminal-like grids, tables first | Terse system messages | Fast for analysts | Intimidating for SME marketers; poor first run |
| 4 | Clinical Lab | White, slate `#475569`, teal `#0f766e` | Geist + Geist Mono | 6 px, balanced | Crisp dashboard panels | Neutral and technical | Modern and tidy | Generic SaaS look; teal fights the "good" green |
| 5 | Nusantara Craft | Warm sand, ink, indigo `#283593` | Plus Jakarta Sans + JetBrains Mono | 10 px, balanced | Local identity touches in headers | Warm, local voice | Speaks to Indonesian users | Decorative motifs break the restraint rules; the typeface is common in template UIs |

## 4. Quiet Ledger tokens

* **Color:** one surface system (page, surface 1 to 3), one ink scale, one accent. The accent does three jobs only:
  the primary action, the current selection and the focus ring. Status colors (good, warning, serious, critical)
  appear only with an icon and a label. Chart colors keep the validated palette.
* **Type scale (about 1.2):** 12, 13, 14 (body), 16, 20, 24, 28 px. Weights 400 and 600. Numbers use tabular
  figures. Reading text (insights, reports) is capped at 72 characters per line.
* **Spacing:** 4 px base: 4, 8, 12, 16, 24, 32, 48. Sections are 24 or 32 px apart.
* **Shape and depth:** radius 8 px for every control and surface, 999 px only for status pills and counts. Depth
  comes from a 1 px border and a surface step; no shadows, no gradients.
* **Motion:** 120 ms ease-out on color, background and border for hover and focus; 160 ms for toast and menu
  entrance; nothing scales or bounces.
* **Focus:** 2 px accent outline with 2 px offset on every interactive element.

## 5. Acceptance checks

1. No `box-shadow`, `linear-gradient` or `scale(` in the app styles (checked by `grep`), and one surface radius token.
2. Every module has designed loading, empty and error states; a broken project link shows an error in under a second.
3. At 390 px wide there is no horizontal page scroll, key numbers sit two per row and tab rows show that they scroll.
4. Keyboard focus is visible on every control; body text contrast is at least 4.5:1 in light and dark themes.
5. The accent appears only on the primary action, the current selection and focus.

## 6. Critique loop log

Screenshots were taken with Playwright at 1440 px (light and dark) and 390 px, on the demo project, an empty project
with a worst-case long name, a broken project link and the locked desktop screen.

| Cycle | Largest problems found | Fixes |
|---|---|---|
| Before | Cards and shadows everywhere, sprinkled accent, 21 green tiles, repeated success pills, duplicated strategy numbers, stage columns cut off, a broken link spinning "Loading", "Offline mode. Offline mode" | Tokens, fonts, flat surfaces; dashboard led by the next step; unique strategy metrics; stage scroller with a hint; no retries on 4xx; copy fixed at the source |
| 1 | Touchpoint tags reused the new monospace code style and overlapped; extra space under the Home header | `chip` became a wrapping tag, monospace only with `.code`; stacks own the header spacing |
| 2 | Two primary buttons on an empty project; heatmap rows with no data | One primary action (the next step); empty stages become a one-line note |
| 3 | 104 to 200 px of sideways scroll on phones: the project picker kept its full width and three list-and-detail pages never stacked | Picker shrinks with the screen; `.grid-sidebar` stacks under 900 px; an end-to-end test now fails on any sideways scroll |

**Answers to the critique questions after cycle 3**

* Squint test: the next step, the key numbers and the page title read first on every module.
* Swap test: warm paper, Plex type, borders instead of shadows and evidence codes in monospace are specific to MDOS.
* Font test: IBM Plex Sans for the interface, Plex Mono for evidence codes and IDs.
* Accent test: the accent marks the primary action, the current selection and focus; status colors carry an icon.
* State test: a new project shows one next step and one primary button; a broken link explains itself with a way back.
* Focus test: every control shows a 2 px accent ring with a 2 px offset.

## 7. What changed

* **Interface:** IBM Plex type, one 8 px radius, flat surfaces, two weights, neutral callouts, quieter badges and
  evidence codes with a strength dot, a stepped heatmap legend, key numbers in a hairline grid.
* **Experience:** Home lists projects first for returning users and gives first-time users one start; the research
  dashboard leads with the next step and a progress checklist, and agent logs fold away; strategy shows each number
  once; journey stages scroll with a hint; insights can be copied with their evidence; skeletons, not-found and
  server-down states; phones get stacked layouts, wrapping tabs and two numbers per row.
* **Removed:** shadows, the gradient, the translucent blurred top bar, sparkle icons on buttons, per-step success
  pills, the sidebar subtitle, the duplicated strategy numbers and the always-open "defensible research" panel.
* **Remaining limitations:** reports keep their own print layout; the journey scroller relies on the native
  scrollbar; the demo text is English with Indonesian quotes and there is no full Bahasa Indonesia interface yet.
