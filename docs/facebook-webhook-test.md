# Facebook Live comment webhook — test setup

**Goal of this test:** confirm that Facebook Live *comments* are delivered to our
app through the **Page `feed` webhook**. If they are, we can read live comments
using only `pages_read_engagement` + `pages_manage_metadata` and **avoid the Live
Video API** (which is gated behind App Review — that's the `#10` error we hit).

This test runs **locally + ngrok**. It does **not** touch the production Railway
deployment.

---

## What you need first

- The **Fad Fashiown Live** Facebook app (App ID `1310436367513365`).
- A **Page Access Token** for your Page (short-lived from the Graph API Explorer
  is fine for this test).
- **ngrok** installed (`brew install ngrok`, then `ngrok config add-authtoken …`
  once, using the token from your free ngrok account).

---

## Step 1 — Get your App Secret

Facebook signs every webhook POST; the app verifies that signature with the App
Secret so it can trust the request.

1. developers.facebook.com → your app → **App settings → Basic**.
2. Copy the **App Secret** (click *Show*).

Keep it handy — it goes in an env var, never in the code or the browser.

---

## Step 2 — Run the app locally with the webhook env vars

From the project root:

```bash
FB_WEBHOOK_VERIFY_TOKEN='fadfash-verify-2026' \
FB_APP_SECRET='<your app secret from Step 1>' \
venv/bin/python app.py
```

- `FB_WEBHOOK_VERIFY_TOKEN` — any secret string you choose (must match what you
  type into Facebook in Step 4). `fadfash-verify-2026` is fine.
- `FB_APP_SECRET` — the value from Step 1.

The app serves on `http://localhost:5000`.

> If you skip `FB_APP_SECRET`, the webhook still works but **skips** signature
> verification — okay for a quick local test, not for production.

---

## Step 3 — Expose it publicly with ngrok

In a second terminal:

```bash
ngrok http 5000
```

ngrok prints a public HTTPS URL, e.g. `https://a1b2c3d4.ngrok-free.app`.
Your webhook callback URL is that URL **+ `/webhooks/facebook`**:

```
https://a1b2c3d4.ngrok-free.app/webhooks/facebook
```

Leave both terminals running. (Each `ngrok http 5000` gives a **new** URL, so if
you restart ngrok you must update the callback URL in Step 4.)

---

## Step 4 — Register the webhook in the Facebook app

1. developers.facebook.com → your app → **Webhooks** (left sidebar; may appear as
   a product you add, or under **Messenger → Webhooks**).
2. Choose the **Page** object → **Subscribe to this object** / **Edit
   subscription**.
3. Fill in:
   - **Callback URL:** your ngrok URL + `/webhooks/facebook` (from Step 3)
   - **Verify Token:** the exact `FB_WEBHOOK_VERIFY_TOKEN` from Step 2
     (`fadfash-verify-2026`)
4. Click **Verify and Save**.
   - Facebook immediately calls `GET /webhooks/facebook` with a challenge; our app
     echoes it back. If the token matches, it saves. ✅
   - If it fails: the token doesn't match, the app isn't running, or the ngrok URL
     is stale.
5. In the field list for the **Page** object, subscribe to the **`feed`** field
   (tick it / click **Subscribe**).

---

## Step 5 — Subscribe your Page to the app

Facebook also needs to know *this specific Page* should send its events to the app.
Our app does this for you:

1. In the running app → **Settings → Facebook** → paste your Page Access Token →
   **Save**.
2. You should see **"Connected as: <your Page> — comment webhooks subscribed."**
   - If it says *"subscription not confirmed"*, the token may lack
     `pages_manage_metadata`, or the app-level webhook (Step 4) isn't set up yet.
3. Also turn on **Enable Facebook auto-messaging** and Save (the webhook only
   surfaces comments for a client who has this on).

---

## Step 6 — Run the actual test

1. In the app, open the **Facebook Live** page (left sidebar). Keep it open — it
   connects to your live-comment feed.
2. On Facebook, start a **short Live** on your Page (60 seconds is enough — use
   **Live Producer** at `facebook.com/live/producer`; you can keep it unlisted).
3. From another account (or a phone), **post a comment** on that live.
4. Watch the **Facebook Live Comments** panel in the app.

### Reading the result
- ✅ **The comment appears in the panel** → live comments *do* flow through the
  `feed` webhook. The webhook path works, and we'll rebuild detection around it
  and retire the polling consumer. (You'll also see the request in the ngrok
  terminal and in the app's console log.)
- ❌ **Nothing appears** (but a comment on a normal Page *post* does show) → live
  comments don't come through `feed`, and the Live Video API App Review is the
  only path. We'd regroup on whether that's worth pursuing.

---

## Alternative: validate without going live

Can't broadcast right now? The `feed` webhook fires on comments on **any** Page
content, so you can confirm the whole pipeline without a live:

**Option A — comment on a normal Page post (recommended).** Do Steps 1–5, then:
1. Make any post on your Page.
2. Comment on it **from a personal account** (not *as* the Page — the receiver
   ignores the Page's own comments).
3. The comment should appear in the **Facebook Live Comments** panel. This proves
   the full path: subscription → delivery → signature → receiver → dashboard.

**Option B — Facebook's "Test" button.** App Dashboard → Webhooks → Page →
`feed` → **Test** sends a sample payload to your callback URL. Confirms the
endpoint is reachable and parses (visible in the ngrok log, returns `200`), but
the sample's fake Page ID won't match your account, so it won't reach the
dashboard.

**What this proves:** the webhook plumbing works for feed comments — nearly all
the risk. **What it doesn't:** that *live-video* comments specifically come
through `feed` (vs. a live-only channel). That last bit still needs one real
(even 60-second, unlisted) live — but a live needs **no followers**, so it can be
done anytime.

---

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| "Verify and Save" fails in Step 4 | Verify token mismatch, app not running, or stale ngrok URL. Confirm `curl "https://<ngrok>/webhooks/facebook?hub.mode=subscribe&hub.verify_token=fadfash-verify-2026&hub.challenge=OK"` returns `OK`. |
| Webhook saved, but no comments arrive | Page not subscribed (redo Step 5), auto-messaging toggle off, or `feed` field not ticked in Step 4. |
| Comments on normal posts work, live ones don't | This is the ❌ result above — live comments aren't in `feed`. |
| ngrok URL changed | Restart means a new URL; update the Callback URL in Step 4. |
| 403 on the webhook POST | Signature mismatch — `FB_APP_SECRET` doesn't match the app's real secret. |

---

## Env var reference

| Var | Purpose | Required |
|---|---|---|
| `FB_WEBHOOK_VERIFY_TOKEN` | Must match the Verify Token entered in the FB dashboard (Step 4). | Yes, for the handshake |
| `FB_APP_SECRET` | Verifies each webhook POST is really from Facebook. | Recommended (skipped if unset) |

Neither is needed for normal app operation — only for receiving webhooks.
