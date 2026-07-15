# Facebook App Review — what to submit

Testing proved the webhook approach works end-to-end. The remaining blocker is
**App Review**: to read buyers' comments and send Messenger replies for *real
customers* (anyone who isn't an admin/developer/tester of the app), Facebook
requires Advanced Access — granted only through review.

This is the **achievable** kind of review (standard Pages/Messenger permissions),
not the Live Video API catch-22 we avoided.

---

## Permissions to get approved

| Permission | Why we need it | Access needed |
|---|---|---|
| `pages_read_user_content` | Read viewers' comments on the Page's live/post to find the winning buyer | **Advanced (review)** |
| `pages_messaging` | Send the buyer one Messenger reply with their order summary | **Advanced (review)** |
| `pages_read_engagement` | Resolve the Page, read the Page's own content | Standard (already "ready for testing") |
| `pages_manage_metadata` | Subscribe the Page to comment webhooks | Standard (already "ready for testing") |
| `pages_show_list` | List/select the Page | Standard (already "ready for testing") |

The two **Advanced** ones are the submission.

---

## Prerequisites (start these first — they take time)

1. **Business Verification.** Meta requires it for these Page permissions.
   App Dashboard → **Business verification** / **Verification**. Needs business
   documents (registration, address, etc.). This can take several days on its
   own, so start it before anything else.
2. **App basics completed:** app icon, category, a **Privacy Policy URL**, and a
   **Data Deletion** URL or instructions. Review is rejected without these.
3. **A working demo** the reviewer can follow (our app is functional — good).

---

## Step 1 — Add the use case that exposes `pages_read_user_content`

The **Messenger** use case doesn't include it. Add a Page-content use case:

- App Dashboard → **Use cases** → **Add use case** (or "Add more to this use
  case" won't have it — you need a *new* use case).
- Pick the one that covers **reading Page content / managing your Page's posts
  and comments** (wording varies; look for one listing `pages_read_user_content`).
- Once added, `pages_read_user_content` becomes requestable.

---

## Step 2 — Request Advanced Access

In the use case's **Permissions and Features** (or App Review), request
**Advanced Access** for `pages_read_user_content` and `pages_messaging`. Each
needs a usage description + a demo video (below).

---

## Step 3 — Usage descriptions (paste + adapt)

**`pages_read_user_content`:**
> Fad Fashiown is a live-selling tool for a clothing seller. During a Facebook
> Live on the seller's Page, our app reads viewers' comments to detect which
> viewer "won" an item (their comment matches the seller's buyer keywords, e.g.
> "mine"). We record the winning buyer so the seller can print a shipping label.
> We only read comments on Pages the user manages and has explicitly connected.

**`pages_messaging`:**
> When a viewer wins an item, our app sends them one consolidated Messenger
> message — a private reply to their own comment — containing their order summary
> and total, so they receive payment and shipping instructions. Messages are only
> sent in direct response to the user's own comment on the seller's Page. If a
> buyer wins several items, they are combined into a single message.

---

## Step 4 — Demo screencast (required)

Record a short screen video with narration showing each permission in use
end-to-end:

1. Log into Fad Fashiown; show **Settings → Facebook** connected to the Page
   ("Connected as: …").
2. On the Page, have a **test user** comment on a live/post (e.g. "mine").
3. Show that comment appearing in the app's **Facebook Live** panel
   → demonstrates `pages_read_user_content`.
4. Enter a price and save; show the app sending the **Messenger reply** to that
   commenter (and the message arriving in Messenger)
   → demonstrates `pages_messaging`.
5. Narrate what each step does and why the permission is needed.

Upload the video in the review submission. Test users are created under
App Dashboard → **App roles → Test users** (they work without review).

---

## Step 5 — Submit and wait

Typical turnaround **1–5 business days**. The reviewer may request changes;
respond and resubmit. Approved → the permissions work for all users (real
customers), and the auto-messenger goes live.

---

## What works *before* approval (so you can keep testing)

In **Development mode**, these permissions work for people with a **role** on the
app (admin/developer/tester) on **Pages they manage** — once the permission is
added via Step 1. So you can fully test with your own account + test users before
review is granted; you just can't use it with *real* customers until approved.

---

## One thing to confirm with the client

This whole path assumes Fad Fashiown lives are broadcast from a **Facebook Page**
(not a personal profile). Personal-profile lives cannot be read via the API at
all — no permission or review changes that. Confirm the client runs lives from
their business **Page** before investing in the review.
