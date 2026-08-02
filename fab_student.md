# fab_student.md — Student Profile → Personalized, Calm Dashboard

Status: PLAN — waiting for confirmation before executing.

User's ask, restated:
1. Student tells us **class level, subjects, city, location** at join.
2. Dashboard shows **only content related to their profile** — today it's overwhelming.
3. KEEP as-is: **Pending Assignments · Last Test · Quick Links** (Today's Focus row is good).
4. Student can: **book a home tutor · buy website courses · buy a monthly academic
   course (e.g. Class 10) · buy a mock-test package**.
5. **Top of dashboard: exams/offers picked from their profile.**

---

## S1. Profile fields (the data everything else keys on)

Add to `CustomUser` (same pattern as phone/city — DB-blank, form-required for students):

| Field | Type | Notes |
|-------|------|-------|
| `class_level` | PositiveSmallInt, null | 1–12; null for non-students |
| `subjects` | CharField(200), blank | comma list: "Maths, Science" |
| `area` | CharField(80), blank | locality within city (optional) |

- **Migration** — shown first, applied only after confirmation (additive, prod-safe
  same as 0019; will need the same fake-check on prod since city collided before).
- **Where collected:** student onboarding step (`StudentParentOnboardingForm`,
  student role only) — NOT the signup form (already 6 fields; keep join friction low).
  Class level = dropdown 1–12, subjects = text with datalist suggestions, area = optional.
- Editable later from profile page.
- Existing students with empty class_level: dashboard shows a one-line "Set your class
  to personalize this page →" prompt instead of the personalized strip (no hard gate).

## S2. Dashboard: keep the good, group the commerce, demote the noise

Current student dashboard ≈ 9 sections stacked. Target layout:

```
1. [KEEP] Continue learning hero (already shipped)
2. [NEW]  FOR YOU strip — offers/exams matched to profile (see S3)
3. [KEEP] TODAY'S FOCUS — Pending assignments | Last test | Quick links (untouched)
4. [KEEP] My courses + Recent grades (LMS work)
5. [NEW]  ONE "Get help & upgrade" row (3 cards, replaces scattered commerce):
          🧑‍🏫 Book home tutor   → tutors filtered by MY city + MY subjects
          📚 Courses for me     → catalog filtered by MY class/subjects
          📝 Mock-test package  → Exam Pro plans page
6. [DEMOTE] collapsed/bottom: leaderboard, referral, server-order, activity feed,
          exam history table (kept but under a toggle or lower)
```

Rules: nothing deleted — only grouped and reordered. Sections 1–4 fill the first
screen; commerce is one row, not four scattered panels.

## S3. "For you" matching logic (no new models — keyword match MVP)

- **Courses:** `core.Course` has free-text `title`/`level` only — match active courses
  where title/level icontains "Class {class_level}" OR any of the student's subjects.
  Cap 4 cards. Zero matches → show top sellers (never an empty strip).
- **Tutors:** existing `public_tutor_queryset` already filters city + subject —
  call it with `user.city` + first subject instead of hardcoded PILOT_CITY.
- **Mock tests / Exam Pro:** link the plans page; if an exam landing matches their
  class (e.g. class 10 → board exam landing) show that too.
- Strip cached per (class_level, subjects, city) for 5 min — no per-request scans.

## S4. Monthly academic course (Class 10 monthly OR one-time) — DECISION NEEDED

Today the catalog supports **one-time purchase only** (`CourseOrder`). Monthly
recurring per-course does NOT exist (only Exam Pro subscriptions in `payments`).
Two options:

- **Option A (fast, no new billing):** add `Course.allow_monthly` +
  `monthly_price_inr` fields; "monthly" purchase = a CourseOrder that grants 30 days
  (reuse the enrollment + a valid-until date). Manual renew via reminder notification.
- **Option B (proper, slower):** real recurring subscription per course via Razorpay
  subscriptions — new models, webhooks, more risk.

Recommendation: **Option A** for MVP; upgrade to B if renewals prove demand.
→ Will ask before building either; S1–S3 don't depend on it.

## Execution order

| Step | What | Migration? |
|------|------|-----------|
| 1 | S1 fields + onboarding form + profile edit | YES — show & wait |
| 2 | S3 matching service (`dashboard/services.py::student_recommendations`) | no |
| 3 | S2 template reorder + For-you strip + commerce row | no |
| 4 | S4 monthly course | decide first |

Per step: tests + smoke as demo_student + CSS rebuild + dev.txt.
