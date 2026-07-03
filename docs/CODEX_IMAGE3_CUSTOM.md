# Codex Image3 Custom Maintenance Guide

Last updated: 2026-07-03

This document is the source of truth for the `image3.mewinyou.shop` custom build. If Codex receives only this document and repository access, it should understand what the custom behavior is, where it lives, how to update it, and how to verify it.

## Repository State

- GitHub fork: `git@github.com:CarminBack/chatgpt2api.git`
- Current custom branch: `main`
- Image3 custom code baseline before this document was added: `e8c993c`
- Old image2 version backup branch: `image2-before-image3-custom`
- Existing older feature branch, not modified during image3 upload: `feature/sub2api-image-billing`
- Upstream project: `basketikun/chatgpt2api`

Recommended local remotes:

```bash
git remote add upstream git@github.com:basketikun/chatgpt2api.git
git remote -v
```

## Server Layout

Default server connection: SSH profile `oracle`.

Production/test deployment paths:

- image3 source: `/opt/chatgpt2api-image3-src`
- image3 compose/runtime config: `/opt/chatgpt2api-image3`
- image3 container: `chatgpt2api-image3`
- image3 public domain: `https://image3.mewinyou.shop`
- image3 exposed port: `4003 -> 80`
- token2/sub2api service: `token2.mewinyou.shop` proxies to `sub2api`
- token2 database container: `sub2api-postgres`

Do not touch image2 unless the user explicitly asks.

## Runtime Configuration

Runtime secrets are not committed to Git. They live in `/opt/chatgpt2api-image3/config.json` or environment variables on the server.

Important runtime config keys:

```json
{
  "sub2api_billing_enabled": true,
  "sub2api_billing_dsn": "postgresql://<user>:<password>@sub2api-postgres:5432/sub2api",
  "sub2api_billing_allowed_group_names": [],
  "sub2api_billing_allowed_group_ids": [12],
  "image_price_per_request": 0.1
}
```

Environment variable alternatives:

- `SUB2API_BILLING_DSN`
- `SUB2API_BILLING_ALLOWED_GROUP_NAMES`
- `SUB2API_BILLING_ALLOWED_GROUP_IDS`

Current production policy:

- Only token2 keys from `group_id=12` are accepted as image3 user keys.
- `group_id=12` is the current priced `image2` group.
- Local image3 admin key is still allowed for maintenance.

## Custom Behavior Summary

Image3 supports token2/sub2api API key login and image billing.

Authentication:

- Local legacy admin key still works.
- Local image3 user keys still work if configured.
- If a Bearer token is not local and `sub2api_billing_enabled=true`, image3 validates it against token2/sub2api `api_keys`.
- Non-whitelisted token2 groups are rejected during authentication.
- Current whitelist is `group_id=12`.

Billing:

- Applies to:
  - `POST /v1/images/generations`
  - `POST /v1/images/edits`
  - `POST /api/image-tasks/generations`
  - `POST /api/image-tasks/edits`
- Billing happens before sending the image request upstream.
- If upstream returns an error or the task fails, billing is refunded.
- Duplicate image task submission with the same `client_task_id` returns the existing task and does not double charge.

Price formula:

```text
unit_price = size_price * group_image_rate_multiplier * user_group_rate_multiplier
total = unit_price * n
```

Size tier mapping:

- Max image side `<= 1024`: `groups.image_price_1k`
- Max image side `<= 2048`: `groups.image_price_2k`
- Max image side `> 2048`: `groups.image_price_4k`
- Missing or auto size defaults to 1K tier.
- If a group price is empty, fallback to `image_price_per_request`.

Current expected prices for user 1 with image2 group multiplier `0.4`:

- 1K: `0.1 * 1.0 * 0.4 = 0.04`
- 2K: `0.2 * 1.0 * 0.4 = 0.08`
- 4K: `0.4 * 1.0 * 0.4 = 0.16`

Balance and usage updates:

- Before debit, image3 checks both `users.balance` and the key's remaining quota
  (`api_keys.quota - api_keys.quota_used`). If either is lower than the charge
  amount, the image request is rejected before it reaches the upstream image
  service.
- Debits `users.balance`.
- Increments `api_keys.quota_used`.
- Increments `api_keys.usage_5h`, `usage_1d`, `usage_7d`.
- Sets `api_keys.last_used_at`.
- Refunds reverse balance and usage counters, clamped at zero.
- Writes all debit/refund events to `custom_image_billing_logs`.
- Admins can view all `custom_image_billing_logs` in image3 at `/billing`.
  Normal token2 users can also open `/billing`, but the API force-filters their
  results to the current authenticated `sub2api_key_id`. This is the
  authoritative image3 billing ledger. It is intentionally separate from token2
  native `usage_logs` so token2 upgrades do not depend on image3 display
  records.

Image management:

- Token2/image3 user keys can open the image management page.
- Admin users can see and manage all stored images.
- Normal users only see images whose `image_index.json` record has `owner_id` equal to their authenticated subject id, for example `sub2api:<api_key_id>`.
- New images save `owner_id` and `owner_name` into the image storage index.
- Existing images without owner metadata are not shown to normal users unless they are backfilled.
- Users can download, delete, and tag only their own images. Admin-only global storage tools remain admin-only.
- The image management page shows: `默认图片储存 7 天，请尽快保存到本地。`

## Token2 Database Dependencies

The custom billing code directly reads/writes token2 PostgreSQL tables. If token2/sub2api updates its schema, verify these fields still exist.

Required tables and columns:

```text
api_keys:
  id, user_id, key, group_id, status, deleted_at,
  quota, quota_used, last_used_at,
  usage_5h, usage_1d, usage_7d,
  window_5h_start, window_1d_start, window_7d_start,
  updated_at

users:
  id, email, status, balance, updated_at

groups:
  id, name, status, deleted_at,
  allow_image_generation,
  image_price_1k, image_price_2k, image_price_4k,
  image_rate_multiplier

user_group_rate_multipliers:
  user_id, group_id, rate_multiplier

custom_image_billing_logs:
  created automatically by image3 if missing
```

If token2 GitHub updates include DB migrations touching these tables, test image3 billing before deploying token2 production.

## Code Map

Primary custom files:

- `services/sub2api_billing_service.py`
  - token2 key validation
  - group whitelist enforcement
  - size tier price calculation
  - group image multiplier
  - user group multiplier
  - balance debit/refund
  - key usage sync
  - billing logs
- `api/support.py`
  - Bearer token extraction
  - local auth fallback
  - token2/sub2api identity creation
- `api/ai.py`
  - direct image generation/edit billing wrapper
- `services/image_task_service.py`
  - async image task billing/refund
  - attaches image owner metadata for task-generated images
- `api/image_tasks.py`
  - converts billing errors to HTTP responses
- `services/config.py`
  - runtime config getters for token2 billing and group whitelist
- `services/image_storage_service.py`
  - stores `owner_id` / `owner_name` for new images
  - filters image index items by owner for normal users
- `services/image_service.py`
  - applies owner filtering for list/delete/download/storage stats
- `api/system.py`
  - image management APIs use `require_identity`; admin gets all images, user gets own images
  - exposes admin-only `/api/billing/image-logs` for the image3 billing ledger
- `web/src/app/billing/page.tsx`
  - billing ledger page backed by `custom_image_billing_logs`; admins see all
    rows, normal users see only the current token2 key
- `web/src/app/image-manager/page.tsx`
  - allows both admin and user roles
  - hides admin-only storage cleanup/compression controls from normal users
  - displays the 7-day local-save notice
- `web/src/components/top-nav.tsx`
  - exposes image management navigation for normal users

Keep future custom logic concentrated in `services/sub2api_billing_service.py` where possible.

## Error Semantics

- Invalid or non-whitelisted token2 key should return `401` through the normal auth path.
- Billing failure after authentication, such as insufficient user balance, insufficient key quota, or disabled image generation group, should return `402`.
- Upstream image failure after successful debit should trigger refund.

## Build And Deploy Image3

Build on the server:

```bash
ssh oracle
cd /opt/chatgpt2api-image3-src
sudo docker build \
  --build-arg BUILDPLATFORM=linux/arm64 \
  --build-arg TARGETPLATFORM=linux/arm64 \
  --build-arg TARGETARCH=arm64 \
  -t chatgpt2api:image3-custom-$(date +%Y%m%d%H%M%S) \
  -t chatgpt2api:image3-custom .
```

Switch image3 compose:

```bash
cd /opt/chatgpt2api-image3
sudo cp docker-compose.yml docker-compose.yml.bak.$(date +%Y%m%d%H%M%S)
sudo sed -i 's#image: chatgpt2api:.*#image: chatgpt2api:image3-custom#' docker-compose.yml
sudo docker compose up -d
```

Verify:

```bash
curl -sS -o /tmp/image3-health.out -w '%{http_code}\n' \
  'https://image3.mewinyou.shop/health?format=json'

sudo docker ps --format '{{.Names}} {{.Image}} {{.Status}}' | grep chatgpt2api-image3
sudo docker logs --since 3m chatgpt2api-image3 2>&1 | grep -Ei 'traceback|exception|error' || true
```

## Validation Checklist

Run these after any custom billing/auth/deploy change.

Compile:

```bash
python3 -m compileall api services
```

Check runtime config inside container:

```bash
sudo docker exec chatgpt2api-image3 sh -lc 'cd /app && uv run python - <<PY
from services.config import config
print({
  "enabled": config.sub2api_billing_enabled,
  "allowed_names": config.sub2api_billing_allowed_group_names,
  "allowed_ids": config.sub2api_billing_allowed_group_ids,
  "has_dsn": bool(config.sub2api_billing_dsn),
})
PY'
```

Check non-whitelisted token2 key is rejected:

```bash
KEY=$(sudo docker exec sub2api-postgres psql -U sub2api -d sub2api -t -A -c \
  "SELECT k.key FROM api_keys k JOIN groups g ON g.id=k.group_id WHERE k.deleted_at IS NULL AND k.status='active' AND g.id <> 12 ORDER BY k.id LIMIT 1;")
curl -sS -o /tmp/image3-non-image2-key.out -w '%{http_code}\n' \
  -H "Authorization: Bearer $KEY" \
  'https://image3.mewinyou.shop/v1/models'
```

Expected: `401`.

Check image2 key price calculation without real generation:

```bash
KEY='<token2 image2 group key>'
sudo docker exec -e TEST_KEY="$KEY" chatgpt2api-image3 sh -lc 'cd /app && uv run python - <<PY
import os
from services.sub2api_billing_service import sub2api_billing_service
identity, _, a1 = sub2api_billing_service.image_charge_amount(os.environ["TEST_KEY"], image_count=1, size="1024x1024")
_, _, a2 = sub2api_billing_service.image_charge_amount(os.environ["TEST_KEY"], image_count=1, size="2048x2048")
_, _, a4 = sub2api_billing_service.image_charge_amount(os.environ["TEST_KEY"], image_count=1, size="4096x4096")
print({
  "group_id": identity.group_id,
  "group": identity.group_name,
  "group_multiplier": str(identity.image_rate_multiplier),
  "user_multiplier": str(identity.user_group_rate_multiplier),
  "1k": str(a1),
  "2k": str(a2),
  "4k": str(a4),
})
PY'
```

Expected for user 1 image2 multiplier `0.4`: `1k=0.04`, `2k=0.08`, `4k=0.16`.

Check billing logs after a real test generation:

```bash
sudo docker exec sub2api-postgres psql -U sub2api -d sub2api -c "
SELECT id, created_at, action, status, user_id, api_key_id, amount,
       balance_before, balance_after, mode, model, left(prompt_preview, 50) AS prompt, error
FROM custom_image_billing_logs
ORDER BY id DESC
LIMIT 10;"
```

Check key usage sync:

```bash
sudo docker exec sub2api-postgres psql -U sub2api -d sub2api -c "
SELECT k.id, k.group_id, g.name AS group_name, k.quota, k.quota_used,
       k.usage_5h, k.usage_1d, k.usage_7d, k.last_used_at, u.balance
FROM api_keys k
JOIN users u ON u.id = k.user_id
LEFT JOIN groups g ON g.id = k.group_id
WHERE k.id = <key_id>;"
```

Check image management owner filtering:

```bash
TOKEN='<token2 image2 group key>'
curl -sS -H "Authorization: Bearer $TOKEN" \
  'https://image3.mewinyou.shop/api/images' | jq '.items | length'
```

Expected:

- Token2 users receive `200`.
- The returned list only contains their own owner-tagged images.
- A non-owner image path sent to `/api/images/delete`, `/api/images/download`, or `/api/images/tags` should return no access or `404`.

Backfill existing images when needed:

- Existing `image_index.json` records created before owner tracking do not have `owner_id`.
- To make old images visible to users, backfill only images that can be confidently matched to token2 billing logs.
- Use image created time near `custom_image_billing_logs.created_at`, and map to owner id `sub2api:<api_key_id>`.
- Do not bulk assign unowned historical images to users without a clear match.

## Updating From Upstream

Goal: keep upstream changes while preserving image3 custom behavior.

Recommended flow:

```bash
git fetch upstream
git checkout main
git pull origin main
git rebase upstream/main
```

If conflicts occur, protect these custom integration points:

- `services/sub2api_billing_service.py`
- `api/support.py`
- `api/ai.py`
- `services/image_task_service.py`
- `api/image_tasks.py`
- `services/config.py`

After resolving conflicts:

```bash
python3 -m compileall api services
git status
git commit --no-edit  # if rebase asks for it
```

Then build a test image on the server first. Do not replace production image3 until the validation checklist passes.

## Documentation Maintenance Rule

Update this document in the same commit whenever any of these change:

- token2 authentication behavior
- allowed group policy
- billing formula
- DB tables or fields used by billing
- refund behavior
- key usage sync behavior
- image owner/index behavior
- image management permissions
- deployment paths, image tags, container names, or compose process
- validation commands
- runtime config keys
- branch strategy or GitHub repository layout

If the document and code disagree, treat the code as temporarily authoritative, fix this document immediately, and include the doc fix in the same PR/commit.

## Safety Notes

- Never commit real `sub2api_billing_dsn`.
- Never commit real token2 keys.
- Never commit production admin keys.
- Before changing token2/sub2api itself, back up `sub2api-postgres`.
- If token2 updates with database migrations, verify schema compatibility before deploying production token2.
- Keep image2 production separate; image3 custom work must not modify image2 unless explicitly requested.
