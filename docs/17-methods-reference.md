# 17. Methods reference

What each analysis answers, what it needs, which assumptions it checks and how results are worded. All statistics
are computed in `backend/mdos/analytics` with numpy, scipy, statsmodels and scikit-learn, and validated against those
libraries or closed-form results in `backend/tests/test_analytics.py`. Agents choose and explain methods; they never
compute the numbers.

Every result carries: the sample size, the assumption checks (OK, warning, violated or not testable), warnings,
limitations and evidence candidates. A violated check changes how the result is reported; it is never hidden.

## Describe

| Method | Answers | Inputs | Checks | Reports |
|---|---|---|---|---|
| Descriptive statistics | What does the sample look like? | Any variables | Skewness, sample representativeness, confidence intervals for means | Mean, SD, median, range, 95% t-interval; frequencies with Wilson intervals |
| Cross-tab and chi-square | Are two categorical variables associated? | Row and column variables | Independent observations, expected cell counts (switches to Fisher's exact test for sparse 2 by 2 tables) | Chi-square or Fisher p, Cramér's V with a size label, adjusted residuals showing which cells drive it |
| Correlation matrix | Which numeric variables move together? | Two or more variables; Pearson or Spearman | Sample size, linearity, distribution shape (Shapiro-Wilk), multiple comparisons | Coefficients with Holm-adjusted p-values |

## Relationships

| Method | Answers | Inputs | Checks | Reports |
|---|---|---|---|---|
| Linear regression (OLS) | Which factors are associated with a continuous outcome, controlling for others? | Outcome, predictors, optional categorical terms | Sample size (Green 1991 rule), multicollinearity (VIF), linearity (Ramsey RESET), independence (Durbin-Watson), normality of residuals (Jarque-Bera), heteroscedasticity (Breusch-Pagan, robust HC3 errors when needed), influential cases (Cook's distance) | b, 95% CI, standardized beta, p, R², adjusted R², F, partial f² |
| Logistic regression | Which factors are associated with a yes/no outcome? | Binary outcome, predictors | Events per variable, multicollinearity (VIF), convergence and separation, linearity of the logit | Odds ratios with 95% CI, pseudo R², AUC, accuracy |
| Mediation (PROCESS Model 4) | Does X relate to Y through M? | X, M, Y, covariates | Sample size, residual normality, causal order X to M to Y (stated, not tested), no unmeasured confounding (stated) | Paths a, b, c, c', indirect effect with a seeded percentile bootstrap CI (5,000 resamples by default), Sobel test, proportion mediated |
| Moderation (PROCESS Model 1) | Does the X to Y relationship depend on W? | X, W, Y, covariates | Sample size for interactions, mean centering, reliability of X and W | Interaction term, simple slopes at the mean and ±1 SD of W, Johnson-Neyman region |

Wording: survey and observational results use associational language ("is associated with", "is higher among").
Causal verbs are blocked by the quality gate unless the cited evidence comes from an experiment.

## Measurement

| Method | Answers | Inputs | Checks | Reports |
|---|---|---|---|---|
| Reliability (Cronbach's alpha) | Do the items measure one thing consistently? | Two or more items | Unidimensionality, tau-equivalence, reverse-coded items, item-total correlations | Alpha and standardized alpha with labels (for example "good" at 0.80 or more), alpha if item deleted, mean inter-item correlation |

Construct scores (item means, requiring a minimum number of answered items) are added as a new dataset version, not
overwritten in place.

## Pricing

| Method | Answers | Inputs | Checks | Reports |
|---|---|---|---|---|
| Van Westendorp price sensitivity | Which price range do customers find acceptable? | Too cheap, cheap, expensive, too expensive prices | Sample size, logical consistency of the four answers (inconsistent respondents excluded and counted), offer understood, representative sample | Point of marginal cheapness, point of marginal expensiveness, optimal and indifference price points, acceptance at a target price with a Wilson interval |
| Gabor-Granger | How does purchase intent fall as the price rises? | Yes/no purchase intent at 3 or more prices | Sample size per price, monotone demand, price order effects | Demand curve with Wilson intervals, revenue index, revenue-maximizing tested price, arc elasticities |
| Willingness to pay at a price | What share would pay this price, overall and by group? | Yes/no question, price, optional group | Sample size, representative sample | Share with a Wilson interval, overall and per group (run a cross-tab for a formal test of the group difference) |

Stated willingness to pay usually overstates real purchasing (hypothetical bias); Research QA and the report say so
and recommend a behavioral test.

## Segments

| Method | Answers | Inputs | Checks | Reports |
|---|---|---|---|---|
| Segmentation (k-means) and personas | Which distinct customer groups exist, for a stated purpose? | Objective and variable rationale (required), clustering variables, optional profile and text columns | Objective and rationale present, variable scaling (standardized), separation (silhouette), stability across random starts (adjusted Rand index), segment size, cluster shape | Number of segments (chosen by silhouette and stability when not given), profiles as z-scores, sizes, personas with needs and example quotes |

## Text

| Method | Answers | Inputs | Checks | Reports |
|---|---|---|---|---|
| Text themes | What do people talk about? | Open-text column | Corpus size, language mix, theme labels need review | Themes from TF-IDF plus NMF (seeded), prevalence, keywords, verbatim examples; English and Indonesian stopwords |
| Sentiment | How positive or negative are the texts, overall and by group? | Text column, optional group | Lexicon coverage, sarcasm and context, human validation recommended | Positive, neutral and negative shares with Wilson intervals, mean compound score with CI, top terms, examples |
| Voice of the customer (journey) | Where in the journey do customers struggle? | Review text, template, optional rating | Stage coverage, keyword mapping ambiguity, review sample bias, agreement with star ratings | Emotion by stage, friction heatmap (stage by theme), ranked pain points with quotes |

The bilingual sentiment lexicon handles negation ("tidak bagus", "not worth"), intensifiers before and after words
("sangat", "banget"), contrast ("tapi", "but") and multi-word expressions ("worth it", "kurang informasi").

## Planning tools

| Tool | Formula |
|---|---|
| Sample size for a share | n = z² p(1 − p) / e², with finite population correction n / (1 + (n − 1) / N) |
| Sample size for a mean | n = (z σ / e)², with the same correction |
| Margin of error | e = z √(p(1 − p) / n), corrected for finite populations |
| A/B test sample size | Two-sided two-proportion test at the chosen alpha and power |
| A/B test result | Two-proportion z-test with the difference, its 95% interval and the relative lift; saved as experimental evidence |

## Strategy simulation

The market model runs Budget to Reach to Engagement to Leads to Conversion to Revenue to Profit per channel and
segment. Reach saturates with a Poisson exposure model, reach = N(1 − e^(−impressions / N)) for a channel audience of N; price response comes from the Gabor-Granger curve
scaled by each segment's willingness-to-pay multiplier (or an elasticity when no curve exists); competitor prices act
through cross-price elasticities; word of mouth adds referred customers. Analyses: one-at-a-time sensitivity (±10 to
30%), Monte Carlo over the uncertain assumptions (ranges by confidence, seeded), a price curve limited to the tested
prices, and a greedy marginal media allocator. All outputs are simulations of stated assumptions, not forecasts.

## Deferred methods (Phase 2)

PLS-SEM (with bootstrapping, HTMT and Fornell-Larcker), choice-based conjoint, MaxDiff, exploratory and confirmatory
factor analysis, latent class segmentation, time-series forecasting, and experiment analysis for continuous metrics.
