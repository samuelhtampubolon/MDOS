# 15. Pricing and go-to-market hypotheses

Everything here is a **hypothesis to test**, not a decision. Numbers are starting points for experiments, chosen from
the interview answers (Q01 first segment, Q09 business model) and typical tool budgets in Indonesia. Please confirm or
correct Q01 and Q09 in [`01-pre-build-interview.md`](01-pre-build-interview.md).

## 1. Who pays first

| Segment | Job to be done | Current spend | Why MDOS wins |
|---|---|---|---|
| **University researchers** (lecturers, master's and doctoral students) | Design a defensible survey study, run the statistics, write it up | SPSS, SmartPLS, AMOS licenses (often institutional), Google Forms, paid statistics consultants | One tool from research question to hypotheses, bilingual instrument, assumption-checked statistics and a cited report |
| **Independent research consultants and small agencies** | Deliver client studies faster with a credible method | Consultant time, survey tools, statistics software | Faster design and analysis, client-ready reports with an evidence register, strategy and journey follow-ons to sell |
| **Tourism organizations and SMEs** (second segment, often reached through consultants) | Decide price, channel and experience changes | Ad budgets, occasional agency studies | Scenario simulation on their own evidence; journey fixes turned into tests |

## 2. Packaging and price hypotheses (Indonesian rupiah)

| Plan | Contents | Price hypothesis | What would falsify it |
|---|---|---|---|
| **Desktop Free** | Single user on one computer, full Research Lab, demo project, offline drafting | Rp 0 | Fewer than 30% of downloads create a real project within two weeks |
| **Professional (cloud)** | One seat, unlimited projects, Strategy and Journey modules, Claude drafting with a monthly allowance | Rp 249.000 to Rp 399.000 per month (annual discount 20%) | Van Westendorp "too expensive" point below Rp 200.000 among target researchers, or trial-to-paid below 5% |
| **Team / Consultant** | Five seats, shared projects, client-ready report branding, priority support | Rp 1.500.000 to Rp 2.500.000 per month | Consultants prefer per-project pricing (test both) |
| **University** | Faculty-wide seats, teaching mode with sample datasets, SSO later | Rp 25.000.000 to Rp 60.000.000 per faculty per year | Procurement cycle longer than 6 months with no departmental budget path |
| **AI credits** | Top-ups for heavy Claude use (design drafts, report narratives) | Rp 50.000 per pack, priced at 3x the underlying model cost | Credit purchases under 10% of paying users (then fold into plans) |
| **Guided study** (service plus software) | A consultant-led study for a tourism organization using MDOS | Rp 15.000.000 to Rp 40.000.000 per study | Clients value the report but not the software (then position as a consultant tool only) |

Unit cost check before launch: measure tokens per workflow from `agent_runs.result.llm_calls` in a pilot and set the
monthly allowance so drafting costs stay below 15% of the Professional price.

## 3. How to test the prices (with MDOS itself)

1. **Van Westendorp and Gabor-Granger survey** of 150 or more target users (researchers and consultants), built and
   analyzed in MDOS: create a project "Pricing MDOS Professional", use the questionnaire's price module, and run the
   price analyses. Report the acceptable range and the price with the highest revenue index.
2. **Fake-door test** on the website: show two price points to random halves of visitors; measure clicks on "Start
   trial". Size it with the A/B calculator in the Research plan.
3. **Concierge pilots**: 5 pilot users (Q12) for 6 weeks; record time to report, insights accepted, and willingness to
   pay at the end.
4. **Decision rule**: choose the price inside the acceptable range that maximizes expected revenue from the
   Gabor-Granger curve, then confirm with the fake-door conversion.

## 4. Go-to-market hypotheses

| Hypothesis | Test | Success signal |
|---|---|---|
| Methods workshops convert researchers better than ads | Run 3 free online workshops ("From research question to defensible evidence") with universities in Medan, Jakarta and Yogyakarta | 20% of attendees create a project; 5% start a paid trial |
| Consultants bring SME and tourism clients | Partner program: consultants get a Team plan discount and co-branded reports | 3 consultants deliver a paid client study in the first quarter |
| The Lake Toba case is a credible proof point | Publish the demo walk-through and one real tourism study (with permission) | Inbound demo requests from tourism organizations |
| Bahasa Indonesia content matters for reach | Publish tutorials in Indonesian on YouTube and Instagram | Tutorial viewers convert at a higher rate than English content |
| Desktop Free drives word of mouth in campuses | Track referrals by campus email domain | Campuses with 10+ active users |

Channels in priority order: university partnerships and workshops; research methods communities (for example
lecturer associations and postgraduate groups); consultant partnerships; LinkedIn and Instagram content; tourism
associations and destination authorities for the second segment.

## 5. Positioning

* One line: **"From business question to defensible marketing evidence."**
* Against survey tools: MDOS designs the study and analyzes it with visible assumptions, not just the form.
* Against statistics packages: MDOS starts from the decision, writes the report with citations, and carries evidence
  into strategy and journey decisions.
* Against generic AI writing tools: numbers come from code, causal claims need experiments, and people approve.

## 6. Risks

* Price sensitivity among students; mitigate with the free desktop tier and university plans.
* Trust in AI among academics; mitigate with transparent methods, assumption checks and the methods appendix.
* Long university procurement; mitigate with departmental and individual plans first.
* Personal data rules (UU PDP); mitigate with the desktop option, pseudonymization and a data processing agreement.
