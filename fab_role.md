# fab_role.md — Role-by-Role Dashboard Workflow Deep Dive

Goal: each role opens `/admin/` and knows in 3 seconds: **what happened, what to do
next, and one tap to do it.** This plan audits every role's dashboard as a *workflow*
(not a stats page) and lists concrete fixes.

Status: PLAN — waiting for confirmation before executing.

Principle carried over from fab5.md: a dashboard is a to-do list with numbers
attached, not a report. Every number that implies work must be a link to the place
where that work is done.

---

## The one shared defect (fix once, reuse everywhere)

Three different "what should I do next" implementations exist today:

| Role | Context key | Format |
|------|------------|--------|
| Tutor/Faculty | `priority_items` | ✅ dict: label + url + tone (good) |
| Parent | `parent_next_actions` | ✅ dict (fixed in fab5 pass 1) |
| City Admin | `city_next_actions` | ❌ plain strings — advice, not actions |
| Global Admin | `global_next_actions` | ❌ plain strings |
| Student | none | ❌ has "Today's Focus" columns but no ranked list |
| VIP | none | ❌ pure stats, zero actions |

**R0. Shared priority component** — new `templates/dashboard/partials/_priority_list.jinja`
(label / url / tone / optional count), replace the duplicated markup in
`role_tutor.jinja` + `role_parent.jinja`, and convert city/global string lists to
the dict format with real URLs. One visual language for "do this next" across
every role.

---

## R1. STUDENT (`index.jinja`) — "what do I study right now?"

Current: Today's Focus (pending assignments / last test / quick links), My Courses,
Recent Grades, exam history, tutor discovery, activity feed, server order. Long page,
good pieces, but no single resume point.

| # | Fix | Why |
|---|-----|-----|
| R1.1 | **"Continue learning" hero button** — the view already computes `learning_path` with the next unlocked set (`next_set`); surface "Continue: {skill} · Set {n}" as the FIRST element on the page. Falls back to "Take your first test". | The single most common student intent (resume) currently requires scanning the skill path section far below. Zero new queries. |
| R1.2 | **Section order by action value** — pending assignments → continue learning → grades; push tutor-discovery cards + server-order + leaderboard widgets below the fold (they're browse-mode, not do-mode). | Page currently mixes "do" and "browse" content. |
| R1.3 | **Preview-mode banner** — when `student_preview_mode` is on (demo data shown to empty accounts), label it clearly ("Sample data — request your first demo to see yours"). | Real user seeing demo_student's data unlabeled = confusion/trust risk. |
| R1.4 | Streak card gets a micro-goal: "Take 1 test today to keep your {n}-day streak". Links to assessment. | Streak is displayed but not actionable. |

## R2. PARENT (`role_parent.jinja`) — "is my child okay, and do I owe anything?"

Current: KPIs, priorities (actionable since fab5), booking funnel, spend, attendance
rate, demo/engagement lists, child LMS course names, family-hub link.

| # | Fix | Why |
|---|-----|-----|
| R2.1 | **Child snapshot card on the dashboard itself** — linked child's streak, last test score, pending-assignment count, last attendance chip. Data already exists via `users/services.py::student_progress_summary` (used on /users/family/) — call it for the first approved link. | Parent's #1 question ("is my child studying?") currently needs a hop to /users/family/. |
| R2.2 | **Direct pay deep link** — pending-payment priority should link to the specific engagement's pay URL (`/hometutor/payments/pay/<id>/`) when there's exactly 1 pending, else to my-requests list. | "Pay" is the platform's revenue moment; every extra hop loses money. |
| R2.3 | **Empty state** — parent with zero links AND zero demos gets one clear split CTA: "Find a tutor" / "Link your child". Today they see empty funnel widgets. | First-session parents currently land on a wall of zeros. |

## R3. TUTOR / FACULTY (`role_tutor.jinja`) — "grade, reply, get paid"

Strongest dashboard already (priorities, unified roster, today's sessions, LMS
teaching block). Remaining friction:

| # | Fix | Why |
|---|-----|-----|
| R3.1 | **"Request payout" CTA** on the earnings row when `tutor_current_balance > 0` and no pending payout — links to the payout request flow. | Balance is shown but the action to collect it lives elsewhere; earning money is why tutors stay. |
| R3.2 | **Inline demo accept/decline** — the 5 `latest_pending_demos` rows get Accept (opens inbox at that demo) / Decline buttons instead of view-only rows. Minimum: deep-link each row to `tutor_demos` anchored at that demo. | Reply speed drives the marketplace (fab5 ranking now rewards it) — cut the hop. |
| R3.3 | **Grading queue counts per course** in the LMS teaching block ("Batch A: 3 to grade") instead of one global number. Data: one `values('assignment__course').annotate(Count)` query. | Faculty with 2+ courses can't see where the backlog is. |

## R4. CITY ADMIN (`role_city_admin.jinja`) — "keep my city's queues at zero"

Current: city-scoped KPIs, funnel rates, pending tutor verifications + disputes
lists, withdrawal count, string next-actions.

| # | Fix | Why |
|---|-----|-----|
| R4.1 | **Actionable priorities** (R0 format): verification SLA breach → /sd/ tutor list filtered PENDING; stale disputes → /sd/ dispute list; low paid-rate → funnel section anchor. | Strings like "Clear aged tutor verification queue" name the work but don't take you there. |
| R4.2 | **Queue rows deep-link** — each pending tutor row → its /sd/ change page; each dispute row → its /sd/ page. | Rows are currently display-only; the fix is one `href` per row. |
| R4.3 | **LMS enrollment shortcut** — Office can already enroll students (`can_manage_enrollment`); add a "LMS courses · assign students" quick link + count of `purchases_missing_lms_enrollment`. | Office has the LMS power but no path to it from their own dashboard. |
| R4.4 | **No-state guard** — CITY_ADMIN with `state` unset sees all-zeros with no explanation; show "No state assigned — ask a superadmin to set your state" banner instead. | Silent zeros look like a bug and generate support pings. |

## R5. GLOBAL ADMIN (`role_global_admin.jinja`) — "governance queues + funnel health"

| # | Fix | Why |
|---|-----|-----|
| R5.1 | Actionable priorities (R0 format) — same conversion as R4.1, global scope. | Same string problem. |
| R5.2 | Queue rows (verifications / disputes / withdrawals) deep-link to /sd/ pages. | Same display-only problem. |
| R5.3 | LMS delivery gap row: `purchases_missing_lms_enrollment` count + link (paid students not yet in a batch = revenue already collected but product not delivered — the worst queue to be blind to). | Currently only superadmin's action center shows this. |

## R6. VIP COORDINATOR (`vip_smart.jinja`) — "onboard people, publish content"

Current: raw platform counts + recent users/attempts. No workflow at all.

| # | Fix | Why |
|---|-----|-----|
| R6.1 | **Quick actions row** at top: Create student/tutor account · Write blog post · My referral link (copy button). These are the only 3 things a VIP does. | Actions exist as separate URLs; dashboard doesn't point to them. |
| R6.2 | **My impact panel** — users they referred (`referred_by=me`) with signup date + active-recently flag, replacing the anonymous platform-wide `recent_users` list. | A coordinator should see THEIR funnel, not everyone's. |
| R6.3 | Drop platform-wide totals (total users, all attempts) or collapse to one line. | Vanity numbers for this role; they can't act on them. |

## R7. SUPERADMIN (`admin_dashboard_v2.jinja`) — already strong

Action Center + revenue/growth + LMS quick setup shipped over past sessions;
fab5 added caching. Only item this pass:

| # | Fix | Why |
|---|-----|-----|
| R7.1 | Action-center rows show a "→ fix it" link consistently (most have; audit the newer LMS rows). | Consistency with R0 principle. |

---

## Execution order

| Step | Scope | Risk |
|------|-------|------|
| 1 | R0 shared partial + convert city/global strings to dicts | Low — template + context shape |
| 2 | R4 + R5 (office roles: links, LMS shortcut, no-state guard) | Low — read paths only |
| 3 | R1 student (hero resume, section order, preview banner) | Low-med — template reorder |
| 4 | R2 parent (child snapshot, pay deep link, empty state) | Low-med — one service call reuse |
| 5 | R3 tutor (payout CTA, demo deep links, per-course grading) | Low-med — 1 new query |
| 6 | R6 VIP rework | Low — isolated view |
| 7 | R7 audit | Trivial |

Per step: run affected app tests + smoke-render as the demo account for that role
(test_user.txt), rebuild CSS at the end, update dev.txt.

No migrations anticipated. No permission changes — every fix reuses existing
gates (`_staff_only`, `is_lms_office`, `can_manage_enrollment` untouched).
