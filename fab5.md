# fab5.md — Make RankJee Smart · Fast · Easy · Mobile-First

Goal: platform already solves a real problem (parents find verified home tutors;
students prep for exams; tutors earn). This plan makes the *experience* of that
solution fast, obvious, and mobile-native — without rewriting anything that works.

Status: EXECUTED 2026-08-02 (first pass). Remaining items marked DEFERRED below.

## Results (after pass 1)

| page | queries before → after |
|------|------------------------|
| superadmin /admin/ | **77 → 12** (cached aggregates, 90s TTL) |
| tutor dashboard | **29 → 23** (conditional aggregates) |
| student dashboard | **29 → 26** (merged demo counts) |
| lms home | 23 → 21 (merged submission/attendance counts) |

Shipped: dashboard aggregate caching (`cached_stat`, dashboard/services.py) ·
demo/engagement/paid-order conditional aggregates (dashboard/views.py) ·
LMS submission + attendance aggregates (lms/services.py) · self-hosted Alpine.js
(static/js/alpine.min.js) · lazy images on tutor/course cards · 5 CMS tables got
overflow-x-auto · 16px mobile input font (iOS zoom fix) · sticky mobile
"Request a free demo" CTA on tutor detail · parent "Today's priorities" now
actionable links (was plain text) · desktop nav capped at 4 + "More" dropdown
for student/VIP/admin roles · student mobile tab bar 7 → 5 tabs (Learn +
Class log moved to dashboard quick links) · tutor search results now rank by
accepted-demo responsiveness after featured/rating · fixed stale office test
assertion (pre-existing failure, label renamed in an earlier redesign).

DEFERRED (next pass): daily digest notifications (F4.3), empty-state
prefills (F4.4), search-first tutor discovery on `/` (F2.3), 360px
device-audit screenshots (F3.1 — code-level fixes shipped blind).

---

## Guiding rule

Every phase must answer: **does a parent/student/tutor reach their goal in fewer
taps and less waiting?** If a task doesn't cut taps or milliseconds, it's out.

---

## Phase F1 — FAST (measure first, then fix) — highest ROI

**Problem:** 2,783-line `dashboard/views.py`, multi-section dashboards firing dozens
of queries per load; Alpine.js from CDN (extra DNS+TLS on every first visit,
breaks offline); no per-view caching of expensive aggregates.

1. **Measure, don't guess** — DONE (2026-08-02, test-client script, local SQLite).
   Baseline (queries / local render):

   | page | queries | time |
   |------|---------|------|
   | home (anon) | 1 | 9ms |
   | tutor search (anon) | 3 | 13ms |
   | courses list (anon) | 0 | 14ms |
   | **superadmin /admin/** | **77** | 78ms |
   | **student dashboard** | **29** | 43ms |
   | parent dashboard | 18 | 25ms |
   | **tutor dashboard** | **29** | 39ms |
   | faculty dashboard | 11 | 23ms |
   | office dashboard | 17 | 22ms |
   | **lms home (faculty)** | **23** | 36ms |
   | **lms home (student)** | **21** | 42ms |
   | lms courses (admin) | 10 | 31ms |
   | family hub (parent) | 3 | 10ms |
   | assessment index (student) | 7 | 13ms |

   Public pages already fast. Targets: superadmin (77), student/tutor (29),
   LMS home (21–23).
2. **Kill N+1s found in step 1** — `select_related`/`prefetch_related` fixes only
   where the numbers say so (dashboard has 40 already; verify coverage, don't
   sprinkle blindly).
3. **Cache expensive dashboard aggregates** — `revenue_summary`, `growth_summary`,
   `action_center` counts etc. in `dashboard/services.py`: `cache.get_or_set`
   with 60–120s TTL. Admin sees near-live numbers; DB stops recomputing per load.
4. **Self-host Alpine.js** — vendored into `static/js/` (one file, pinned
   version). Removes the only remaining third-party CDN dependency.
5. **Defer + lazy-load images** — `loading="lazy"` on tutor cards, course cards,
   video thumbnails; explicit width/height to stop layout shift (CLS).
6. **HTMX for below-the-fold dashboard sections** — the superadmin Command Center
   renders everything server-side in one request; move heavy secondary panels
   (trend charts, activity feed) to `hx-get` on load so first paint is instant.

**Exit metric:** every money page ≤ 15 queries and < 300 ms local render.

---

## Phase F2 — EASY FLOW (fewest taps to goal, per role)

**Problem:** feature-rich but hunt-heavy. Each role's #1 job should be one tap
from landing.

1. **"Next best action" card, top of every role dashboard** — reuse the existing
   `action_center()` / "Today's priorities" pattern (already built for
   admin/tutor) and extend to STUDENT and PARENT:
   - Student: "Continue: <pending assignment / retest weak skill>" — one button.
   - Parent: "Your demo with <tutor> is tomorrow 5pm — Confirm / Reschedule".
2. **Cut nav to 4 items per role** — audit `base.jinja` nav branches; anything
   beyond 4 top-level links moves under a "More" disclosure. Mobile bottom bar
   already caps at 4 — make desktop match so the mental model is identical.
3. **Search-first tutor discovery on `/`** — one big search box (subject +
   pincode) above the fold; filters appear *after* first results, not before.
   A parent should see matching tutors in 2 interactions.
4. **Kill dead-end pages** — every page must have exactly one primary CTA.
   Audit: empty-state pages (no courses, no assignments, no demos) must show
   "do this next", never a blank table.
5. **Breadcrumbs are done** (previous pass) — no rework, just verify new pages
   keep them.

**Exit metric:** parent lands on `/` → sees a matched tutor list in ≤ 2
interactions; student lands logged-in → resumes work in 1 tap.

---

## Phase F3 — MOBILE-FIRST (audit + fix, page by page)

**Problem:** bottom nav exists, but inner pages (admin tables, LMS rosters,
courses list, grading views) are desktop tables that overflow on 360 px.

1. **Device audit** — walk every money page at 360×740 (Chrome devtools),
   screenshot, log failures into this file. Suspects: courses.jinja per-course
   reassign row, skill roster table, students score table, admin action tables.
2. **Tables → stacked cards under `md:`** — pattern: `hidden md:table` +
   mobile card list. One shared partial `partials/_responsive_row.jinja` so we
   don't hand-roll it per page.
3. **Touch targets ≥ 44 px** — buttons/links in dense admin rows get
   `py-2.5 px-4 min-h-[44px]` on mobile.
4. **Forms** — correct `inputmode`/`type` (tel, email, numeric for pincode/marks),
   16 px min font-size on inputs (stops iOS zoom), submit buttons full-width
   on mobile.
5. **Sticky primary CTA on long mobile pages** — assignment detail (Submit),
   tutor detail (Request demo), checkout (Pay): fixed bottom button above the
   tab bar on mobile.

**Exit metric:** zero horizontal scroll on any money page at 360 px; all primary
actions thumb-reachable.

---

## Phase F4 — SMART (make the platform feel intelligent, no ML needed)

1. **Smart tutor matching order** — rank `/hometutor/` results by
   (verified, distance, rating, response speed) instead of raw list. Data all
   exists (`PincodeGeo`, reviews, demo response timestamps).
2. **Weak-area → next-step loop tightening** — after a failed test, the results
   page should link *directly* to the mapped video AND the retest, one screen,
   no hunting (verify current wiring, close gaps).
3. **Digest notifications instead of drips** — one daily notification per role
   ("2 assignments due, 1 graded") instead of N separate rows. Reuses existing
   Notification model + Celery beat.
4. **Empty-state intelligence** — new tutor with no listing → prefilled listing
   draft from their signup data; new student with no attempt → suggested first
   test by class level.

---

## Explicitly NOT doing (avoid scope creep)

- No app rewrites, no framework changes, no design-system overhaul.
- No new roles, no new payment flows, no ML/AI infra.
- No touching `/sd/` Django admin styling.
- Migrations: none expected except possibly an index or two in F1 —
  will show file + wait per DB safety rule.

---

## Execution order & checkpoints

| Order | Phase | Why first |
|-------|-------|-----------|
| 1 | F1 Fast | Speed compounds — every later phase tested on a fast base |
| 2 | F3 Mobile | Most users are mobile in India; visible wins |
| 3 | F2 Flow | Needs F3's mobile patterns in place |
| 4 | F4 Smart | Cherry on top; each item independently shippable |

After each phase: run full test suite (110 green today), rebuild `app.css`,
update `dev.txt`, commit.
