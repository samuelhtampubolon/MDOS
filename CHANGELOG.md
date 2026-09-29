# Changelog

All notable changes to MDOS are recorded here. The format follows Keep a Changelog; versions follow semantic
versioning.

## [Unreleased]

## [0.1.0] - 2026-09-29

First MVP: the Research Lab in full, with working slices of the Strategy Simulator and the Journey Designer connected
in a closed loop.

### Added

- **Research Lab:** projects from a business question; research design workflow (problem framing, design,
  questionnaire, sampling, fieldwork, QA) with an adoption gate and rollback; construct library with English and
  Indonesian items; hypothesis canvas with evidence-based verdicts approved by people; bilingual questionnaire with
  XLSForm, Markdown and codebook exports; sample size calculator; CSV and Excel import with profiling; nine data quality
  checks; cleaning plans with approval, versioning, checksums and restore; 15 analysis methods with assumption checks
  (descriptives, cross-tabs, correlation, OLS and logistic regression, reliability, mediation, moderation, Van
  Westendorp, Gabor-Granger, willingness to pay, segmentation with personas, text themes, sentiment, voice of the
  customer); evidence register and lineage graph; insights and recommendations with evidence and causal-language
  gates; reports with citations in Markdown and HTML.
- **Strategy Simulator:** evidence-backed market model with labeled assumptions; scenarios for price, budget, segment
  mix and competitor moves; profit bridge, sensitivity, Monte Carlo risk, price curves limited to tested prices, media
  optimizer, positioning map and a decision log with approval.
- **Journey Designer:** tourism and generic journey templates, touchpoints, emotion curve, friction heatmap, ranked pain
  points, interventions with low, mid and high simulations, and A/B tests whose results become experimental evidence.
- **Agents:** 26 executable agents covering 47 of the 50 agents in the specification, a 10-field output contract, tool
  allowlists, supervisor workflows with retry, cancel and rollback, and optional Claude drafting with offline
  fallback, untrusted-data wrapping and numeric grounding.
- **Platform:** organizations, roles and tenant isolation; desktop mode (loopback only) and cloud mode (accounts);
  audit log and approvals inbox; rate limits, upload limits, security headers and allowed hosts; Alembic migrations;
  light and dark themes with an accessible, color-blind-safe chart palette.
- **Delivery:** desktop executable build (PyInstaller) for Windows, macOS and Linux; Docker image and docker-compose
  with PostgreSQL; CI with tests on SQLite and PostgreSQL, a migration drift check, Playwright end-to-end tests and a
  Docker smoke test.
- **Demo:** one-click Lake Toba project on synthetic data that runs the whole loop through the agents.
- **Docs:** synthesis, interview, assumptions, scope, architecture, agent architecture, design system, backlog, test
  strategy, threat model, deployment, observability, pricing and go-to-market hypotheses, section catalog and methods
  reference.
