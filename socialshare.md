# Social Share Plan (Author Auto-Share)

## Goal
Auto-share blog posts on social media for the logged-in author when a post is published, while keeping the app stable and scalable.

## MVP-First Platform Priority
Start with APIs that are most practical for MVP:

1. LinkedIn (best first target)
2. Facebook Page
3. X (Twitter, based on API tier access)

Phase 2 later: Instagram/WhatsApp (more API constraints).

## Product Flow
When an author publishes a blog post:

1. Author has connected one or more social accounts.
2. System stores OAuth tokens securely per author.
3. Publish action triggers a background share job.
4. Job posts title + excerpt + URL (+ optional image).
5. Each platform result is logged (success/failure).

## Django Architecture

### Models

#### `SocialConnection`
- `user` (FK to auth user)
- `platform` (`linkedin`, `facebook`, `x`)
- `access_token` (encrypted at rest)
- `refresh_token` (nullable)
- `expires_at` (nullable datetime)
- `is_active` (bool)
- `created_at`, `updated_at`

#### `SocialShareLog`
- `user` (FK)
- `blog_post` (FK)
- `platform`
- `status` (`pending`, `success`, `failed`)
- `external_post_id` (nullable)
- `error_message` (nullable text)
- `shared_at` (nullable datetime)
- `created_at`

#### `SocialShareSetting` (optional but recommended)
- `user` (OneToOne)
- `auto_share_enabled` (bool)
- `share_linkedin` (bool)
- `share_facebook` (bool)
- `share_x` (bool)

## Services Layer (`services.py`)

Create service methods:
- `connect_platform(user, platform, auth_code)`
- `refresh_token_if_needed(connection)`
- `build_share_text(post)`
- `share_post_to_platform(connection, post)`
- `share_post_to_enabled_platforms(user, post)`

Keep views thin: views call services, services hold business logic.

## Trigger Strategy
After post publish success:
- enqueue async task (Celery/RQ/Django-Q)
- do not call external social APIs directly inside request-response path

Reason: avoid slow publish UX and API timeout risk.

## UI (Dashboard + Publish UX)

### Dashboard
- Connect/Disconnect buttons for each platform
- Auto-share toggle
- Per-platform enable/disable toggles
- Last share status summary

### Publish page
- Optional checkbox: "Share now"
- Optional preview of generated social text

## Security + SaaS Constraints
- Always filter records by `request.user` (multi-tenant safety)
- Encrypt tokens at rest
- Validate callback/state in OAuth flow
- Handle token refresh and revocation cleanly
- Add retry with backoff for transient API failures
- Log all attempts in `SocialShareLog`

## Platform Notes
- Facebook: typically Page posting (not personal profile)
- LinkedIn: member/org permissions depend on app scopes
- X: paid API tier may be required
- Instagram: business account dependencies via Graph API

## Phased Rollout (Fast to Revenue)

### Phase 1 (2-3 days)
- LinkedIn connect
- Manual "Share now" button
- Basic success/failure logging

### Phase 2
- Auto-share toggle on publish
- Background queue integration
- Retry handling

### Phase 3
- Facebook Page integration
- Better dashboard share logs

### Phase 4
- X integration
- UTM tagging + analytics attribution

## Suggested Share Text Template
`{post.title}\n\n{short_excerpt}\n\nRead more: {post_url}`

Keep copy concise and platform-safe.
