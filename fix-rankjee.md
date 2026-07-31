# fix-rankjee.md — Unifying Tutors, Faculty, Courses, LMS, Learning & Exams

Status: **IMPLEMENTED.** Phases 0–4 (§6) are all built, tested, and running locally — see
`dev.txt` for the detailed changelog of each phase and `test_user.txt` for click-through demo
accounts. Phase 5 (§4.6, retiring `tutor_study`) was explicitly declined — `tutor_study` stays
permanent as the lightweight 1:1 home-tutoring tool, `lms` stays the batch/course tool. None of
this is migrated on production yet — run `migrate` there before relying on any of it live.

---

## 1. TL;DR — why this feels confusing

You don't have one teaching system with three views into it. You have **four separate,
disconnected systems** that all independently reinvent "a teacher with some students and
some content," built at different times:

| # | System | "Teacher" concept | "Class of students" concept | Gate (who can teach) |
|---|---|---|---|---|
| 1 | `lms/` — classroom (just fixed) | `LmsCourse.owner` | `LmsCourseEnrollment` | `is_staff` (Django flag) |
| 2 | `tutor_study/` — tutor's study hub at `/study/` | `tutor` FK on every model | **none** — only 1:1 via `hometutor.TutorEngagement` | `role == 'TUTOR'` |
| 3 | `hometutor/` — marketplace (discovery, booking, billing) | `TutorProfile` | `TutorEngagement` (1 tutor ↔ 1 student) | `role == 'TUTOR'` |
| 4 | `core.Course` — paid catalog at `/courses/` | **none** | **none** | n/a — it's a sales page + checkout, nobody "owns" or delivers it |

Plus `assessment/` (exams) and `learning/` (videos) are both **global, unscoped content** —
any test/video applies to any user, with no notion of "this is part of my batch's
curriculum." They only connect to the above via one-off FKs (`LmsAssignment.concept_video`,
`Question.source_video`), not a real pipeline.

And `role` on `CustomUser` is currently doing **three unrelated jobs** at once:
1. What you picked at signup (STUDENT / PARENT / TUTOR) — marketing identity.
2. Which ops dashboard you see (CITY_ADMIN / GLOBAL_ADMIN) — internal permission tier.
3. Informally implies "are you a teacher" — but the LMS work this session correctly did
   **not** use `role` for that (it uses `is_staff`/`is_superuser` instead), which is safer
   but means `role=TUTOR` and LMS "Faculty" are *not currently the same permission* at all.
   A marketplace Tutor today has **zero** access to `/admin/lms/` unless someone also
   flips `is_staff=True` on their account manually.

There is also **no real Parent↔Student data link**. "Parent" is just a role label; parents
only touch a student's data today via the hometutor booking flow (`requester` on
`DemoRequest`/`TutorLeadRequest`), not a durable relationship.

---

## 2. Full current-state inventory

```
users/            CustomUser.role: STUDENT | PARENT | TUTOR | VIP_USER | CITY_ADMIN | GLOBAL_ADMIN | FACULTY(new, label-only)
                  is_staff / is_superuser: Django flags, used ONLY by lms (as of this session)
                  No ParentStudentLink model. No is_lms_faculty flag.

hometutor/        TutorProfile (marketplace listing, owned by a TUTOR user)
                  DemoRequest -> TutorEngagement (1 tutor : 1 student, mutual-confirmed, paid)
                  SessionAttendance, EngagementReview, EngagementChatMessage, disputes

tutor_study/      StudyTopic / StudyMaterial / StudyAssignment / AssignmentSubmission
                  All keyed on `tutor = FK(user)` directly — NO batch/course container.
                  Visibility for students = "do you have an ACTIVE TutorEngagement with this tutor".
                  Teacher UI at /study/tutor/ (also mirrored into /admin/study/ via dashboard.views).
                  Gate: role == 'TUTOR'.

lms/              LmsCourse(owner=staff user) -> LmsCourseEnrollment -> LmsAssignment -> LmsSubmission
                  Just refactored this session for faculty/admin isolation.
                  Gate: is_staff (faculty, own courses only) / is_superuser (admin, sees all).
                  Mounted at /admin/lms/.

core.Course       Paid curriculum catalog at /courses/ (AI Automation Engineering Pro, etc.)
(core app)        price_inr, curriculum (JSON marketing copy, not real lessons), Razorpay checkout.
                  CoursePurchase = "user bought access" — but access to WHAT? Nothing operational
                  happens after purchase. No owner/teacher, no linked batch, no auto-enrollment
                  anywhere. This is the exact "confusion" you flagged: courses aren't assigned to
                  a tutor, so a paying customer has nowhere to actually go post-purchase.

assessment/       Skill / Question / UserAttempt — global exam engine. Any user can attempt any
                  skill test. Not scoped to a class, batch, or course. No "my batch's average
                  score" concept.

learning/         ConceptVideo — global recorded-lecture library, tagged by Skill/concept_tag.
                  Cross-linked into lms.LmsAssignment.concept_video and assessment.Question.source_video.
                  This one's fine as shared content — it doesn't need per-tutor ownership.

dashboard/        The `/admin/` ops hub. Hosts: CITY_ADMIN / GLOBAL_ADMIN analytics dashboards
                  (tutor quality, disputes, marketplace health — this is your "Office" tier,
                  already built, just not wired into LMS), CMS (skills/videos/questions/tasks),
                  and the /admin/study/ chrome wrapper around tutor_study.
```

---

## 3. Root causes (in priority order)

1. **Two teacher stacks, two different gates.** `lms` (is_staff-gated) and `tutor_study`
   (role=TUTOR-gated) were built independently and never merged. A person can be "faculty"
   in one and invisible in the other.
2. **`core.Course` has no delivery mechanism.** It's a storefront with no classroom behind
   it. This is literally your "courses also have to assign to tutor" complaint.
3. **`role` is overloaded** — signup identity + ops permission tier + informal teaching flag,
   three concerns jammed into one field.
4. **No Parent↔Student relational model** — Parent is a label, not a link.
5. **Exams/videos are global**, never rolled up to "this batch's curriculum / this batch's
   results."

---

## 4. Target architecture (proposed — needs your sign-off)

### 4.1 One educator identity, `is_lms_faculty` decoupled from `is_staff`

Keep `TUTOR` as the single role for anyone who teaches — whether 1:1 (hometutor
marketplace) or batch/course (LMS). Add a new boolean `CustomUser.is_lms_faculty`
(separate from Django's `is_staff`, which should mean "can log into `/sd/`" — an
unrelated, ops-only concept). `is_lms_faculty=True` is what actually gates `/admin/lms/`
ownership going forward. It's auto-granted the moment a TUTOR is assigned an `LmsCourse`,
or set manually by an admin. This fixes two problems at once:
- A marketplace Tutor can be granted LMS access without also getting Django `/sd/` admin access.
- An "Office" ops person with `is_staff=True` (for `/sd/`) is no longer mistaken for
  "Faculty" in the LMS permission model (today they would be, per what I built this session
  — worth revisiting once this lands).

### 4.2 "Office user" — you already built it, it's just not connected

`CITY_ADMIN` / `GLOBAL_ADMIN` already exist as real, wired-up roles with their own ops
dashboards (`dashboard/views.py`: tutor quality, disputes, marketplace analytics by
region/platform). That *is* your Office tier. Today they have **zero** visibility into
`/admin/lms/`, `/courses/`, or exam data. Proposal: grant them **read-only oversight**
across LMS courses / catalog courses / exam results (support & QA use case), without
making them an owner of anything.

### 4.3 Real Parent ↔ Student link

New `ParentStudentLink` model (`parent` FK, `student` FK, relationship label,
`is_verified`). Linked via invite code or email match at onboarding. Once linked, a
Parent gets read-only visibility into: exam results, LMS marks/submissions, learning
progress — and keeps using hometutor booking as today (already works via `requester`).

### 4.4 Bridge `core.Course` (catalog) → `LmsCourse` (delivery)

Add `LmsCourse.catalog_course` (nullable FK → `core.Course`). Flow:
1. Admin creates/edits the sales page (`core.Course`) — unchanged, already works.
2. Admin assigns a Tutor to deliver it: creates an `LmsCourse` with
   `catalog_course=<the core.Course>, owner=<tutor>`. This is literally "assign the
   course to a tutor" — the thing you said felt missing.
3. On a successful `CoursePurchase`, auto-create an `LmsCourseEnrollment` for the buyer
   into the matching `LmsCourse` (signal on `CoursePurchase` creation).
4. **Open question:** if a catalog course has multiple delivery batches (different
   cohorts/start dates/tutors), how do we route a new buyer to the right one? See §7.

### 4.5 One assignment screen: video + test + written work

Already working: `LmsAssignment.concept_video` → a `learning.ConceptVideo`. New:
add `LmsAssignment.skill` (FK → `assessment.Skill`) so Faculty can attach a graded
skill-test as part of an assignment; `UserAttempt` filtered by that skill + course
roster gives per-batch exam results. Net result — one screen where Faculty picks any
combination of: ▸ recorded video ▸ skill test ▸ written/file submission, exactly
matching "assign recorded videos, take test, give assignment" as one flow.

### 4.6 Retire the duplicate: merge `tutor_study` into `lms` (last, optional, riskiest)

Once §4.1–4.5 land, a Tutor's 1:1 student (via `TutorEngagement`) can just be an
`LmsCourse` with exactly one enrolled student, auto-created from the engagement. At that
point `tutor_study` (StudyTopic/StudyMaterial/StudyAssignment/AssignmentSubmission) is
redundant with `lms` and could be retired, with `/study/` kept as a redirect for
bookmarks. **This is the biggest, riskiest change** (touches live student-facing URLs) —
recommend doing it last, as its own project, only once the rest is stable. It may also
turn out you'd rather keep `tutor_study` permanently as the lightweight 1:1 tool and
`lms` as the batch tool — see §7.

---

## 5. Proposed final role model

| Role | Django flags | Purpose | Visibility |
|---|---|---|---|
| **STUDENT** | none | learner | own enrollments/attempts/submissions |
| **PARENT** | none | linked via `ParentStudentLink` | read-only child progress + hometutor booking (as today) |
| **TUTOR** (Faculty *is* Tutor) | `is_lms_faculty` (new, opt-in) | teach 1:1 (hometutor) and/or own `LmsCourse` batches | only their own students/batches |
| **CITY_ADMIN / GLOBAL_ADMIN** ("Office") | `is_staff` (for `/sd/` only) | regional/platform ops, support, QA | read-only oversight, not ownership |
| **SUPERADMIN** | `is_superuser` | full control | everything |

---

## 6. Phased execution plan

- **Phase 0 — ✅ DONE this session:** `LmsCourse.owner`, faculty/admin isolation across
  `/admin/lms/`, `/sd/`, home page stats. (See `dev.txt` for detail.)
- **Phase 1 (small):** `is_lms_faculty` flag decoupled from `is_staff`; auto-grant to a
  TUTOR when given an `LmsCourse`; read-only LMS/course oversight for CITY_ADMIN/GLOBAL_ADMIN.
- **Phase 2 (medium):** `ParentStudentLink` model + parent read-only views.
- **Phase 3 (medium):** `core.Course` ↔ `LmsCourse` bridge + auto-enroll on purchase —
  this is the concrete "assign a course to a tutor" fix.
- **Phase 4 (medium):** `assessment.Skill` link on `LmsAssignment` + course-scoped exam
  results rollup.
- **Phase 5 (large, optional, last):** retire `tutor_study` into `lms`.

Each phase gets its own migration file shown to you before running, per your workflow rules.

---

## 7. Open questions — need your answer before I implement anything

1. Is "Faculty" the **same person/account** as a marketplace "Tutor" (recommended — one
   `TUTOR` role, `is_lms_faculty` just toggles whether they also run batches), or should
   Faculty be a completely separate account type that never touches home tutoring?
2. For Phase 3 — when one paid `core.Course` has **multiple** delivery batches (different
   tutors/cohorts/start dates), how should a new buyer be routed? (a) auto-enroll into a
   single "default/open" batch, (b) admin manually places every buyer, (c) round-robin
   across open batches.
3. Do you actually want Phase 5 (retiring `tutor_study`) at all, or should it stay
   permanently as the lightweight 1:1 home-tutoring tool while `lms` stays the
   batch/course tool? (Lower risk if we never merge them.)
4. Which phase should I start on next — Phase 1 (role/office cleanup) or Phase 3
   (course→tutor assignment, since that's the concrete pain point you named)?
