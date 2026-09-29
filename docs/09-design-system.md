# 09 · Design System

MDOS is a working tool for marketers and researchers who read numbers all day. The design system favors calm
surfaces, legible data and explicit state over decoration. Everything below is implemented in
`frontend/src/styles/tokens.css` (values), `components.css` and `charts.css` (usage) and
`frontend/src/components/ui` (React components).

## 1. Principles

1. **Numbers first.** Tables and charts carry the content; chrome stays quiet (neutral surfaces, thin borders).
2. **State is never color alone.** Every status (approved, draft, awaiting approval, failed, high severity) is a badge
   with an icon and a word. Every chart has a table view.
3. **Provenance is visible.** Evidence codes (E1, E2), origin badges (user data, external, synthetic demo,
   experiment, model-generated) and "Model-generated wording" badges appear wherever content is shown.
4. **People decide.** Approve and reject controls sit next to the thing being decided, and the Approvals page
   collects every pending gate.
5. **Plain language.** Labels say what happens ("Propose cleaning plan", "Save and re-run"). No jargon without a
   short explanation, no em dashes, sentence case everywhere.

## 2. Tokens

Components use semantic roles only; rebranding means changing values in `tokens.css`.

| Role | Light | Dark | Use |
|---|---|---|---|
| `--page` | `#f9f9f7` | `#0d0d0d` | App background |
| `--surface-1` | `#fcfcfb` | `#1a1a19` | Cards, chart surface |
| `--surface-2` / `-3` | `#f3f2ee` / `#ebe9e3` | `#222220` / `#2c2c2a` | Inset areas, table headers, empty heatmap cells |
| `--text-primary` / `-secondary` / `-muted` | `#0b0b0b` / `#52514e` / `#6b6a65` | `#ffffff` and lighter grays | Body, supporting text, captions |
| `--accent` | `#1c5cab` | `#256abf` | Primary buttons, links, focus |
| `--good`, `--warning`, `--serious`, `--critical` | green, amber, orange, red with `-text` and `-soft` variants | tuned for dark | Status only, never data series |
| `--radius-sm` / `--radius` / `--radius-lg` | 6 / 10 / 14 px | same | Inputs, cards, dialogs |

Typography uses the system font stack (`system-ui`, Segoe UI, Roboto, Helvetica Neue) for fast loading in the
desktop build and good Indonesian diacritic support; numbers use tabular figures in tables (`.num`).

Dark mode is a separate, selected set of values (not an automatic inversion). The theme follows the device by
default and can be set to light or dark in Settings or the top bar.

## 3. Components

| Component | Purpose |
|---|---|
| `PageHeader` | Eyebrow (module), title as a question the page answers, one-sentence description, actions |
| `Card` | Titled section with subtitle and header actions |
| `Tabs` | In-page navigation (module tabs are routes; sub-tabs are state) |
| `Stat` | Label, value, optional delta; used in rows of four |
| `StatusBadge`, `Badge`, `OriginBadge`, `ModelBadge` | State and provenance, always icon plus text |
| `EvidenceChips` | Evidence codes colored by strength; click opens the evidence record |
| `ChecksList` | Assumption checks with OK / warning / violated / not testable |
| `Callout` | Info, warning, critical, good messages (critical uses `role="alert"`) |
| `Modal`, toasts | Focus-trapped dialog closed with Escape; polite live region for toasts |
| `WorkflowPanel`, `AgentRunModal`, `ApprovalCard` | Agent timelines, the 10-field agent contract, human gates |
| `LineageGraph` | Layered evidence graph; click an item to trace its full chain |

Inline controls in rows and toolbars size to their content; form fields in grids fill their column.

## 4. Data visualization

Charts are hand-built SVG with d3 scales (no charting library), so every mark follows the same rules.

**Palette** (validated for color-vision deficiency with the dataviz validator; categorical hues are assigned in a
fixed order and never cycled):

| Slot | Light | Dark |
|---|---|---|
| 1 | `#2a78d6` | `#3987e5` |
| 2 | `#eb6834` | `#d95926` |
| 3 | `#1baf7a` | `#199e70` |
| 4 | `#eda100` | `#c98500` |
| 5 | `#e87ba4` | `#d55181` |
| 6 | `#008300` | `#008300` |
| 7 | `#4a3aa7` | `#9085e9` |
| 8 | `#e34948` | `#e66767` |

The light aqua and yellow slots have low contrast against the light surface, so they always come with direct labels
or the table view. Sequential scales use one blue hue from light to dark; diverging scales use red and blue with a
gray midpoint.

**Rules applied to every chart**

* One y-axis. Two measures of different units become two charts (for example profit by price and revenue by price).
* Bars are at most 24 px thick with 4 px rounded data ends; lines are 2 px; markers are at least 8 px with a surface
  ring; hit areas are larger than marks.
* One tooltip per chart, a legend whenever there are two or more series, selective direct labels.
* Every chart has a **Table** toggle that shows the same numbers.
* Text uses text colors, never the series color.
* Funnels are strips of stat cards (Budget, Reach, Engagement, Leads, Conversion, Revenue, Profit), not a mixed-unit
  chart.

| Chart | Where |
|---|---|
| Bar (with interval whiskers) | Descriptives, WTP by group, reliability items, scenario profit ranking, intervention uplift ranges |
| Line (crosshair tooltip) | Van Westendorp curves, Gabor-Granger demand, price curves |
| Coefficient plot | Regression and logistic results (filled points p < .05) |
| Heatmap (sequential or diverging) | Correlation matrices, friction by stage and theme |
| Stacked shares | Cross-tabs |
| Waterfall | Profit bridge from baseline to scenario |
| Tornado | One-at-a-time sensitivity |
| Histogram | Monte Carlo profit distribution with P10, median and P90 |
| Emotion curve | Mean sentiment by journey stage, dot size by mentions |
| Segment profiles | Z-scores by segment |
| Scatter map | Positioning map |
| Path diagram | Mediation model (a, b, c prime) |

## 5. Accessibility

* Keyboard: every control is a native button, link or input; the lineage graph nodes are focusable and respond to
  Enter and Space; dialogs close with Escape.
* Screen readers: charts expose a text summary (`role="img"` with `aria-label`) and the table view; status badges
  include text; toasts use a polite live region.
* Contrast: text tokens meet WCAG AA on both surfaces; status colors carry icons and labels.
* Language: Indonesian questionnaire text is marked `lang="id"`.

## 6. Content style

* Sentence case for titles and buttons. Questions as page titles ("What happens if we change the price, the media mix
  or the audience?").
* Rupiah formatted the Indonesian way: `Rp 150.000`; compact values as `Rp 11.8M`.
* Say what is simulated versus measured ("Numbers are simulated from the model, not forecasts").
* Associational wording by default ("is associated with"); causal wording only with experimental evidence.
