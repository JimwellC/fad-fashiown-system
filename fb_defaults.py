# fb_defaults.py
# Shared defaults for the Facebook Auto-Messenger feature.
# Imported by the Settings UI (to prefill the editable template) and later by
# the message scheduler (to render the actual message when a template is blank).

# Placeholders the scheduler substitutes at send time:
#   {buyer_name} — the buyer's Facebook display name
#   {items}      — one line per item: "📦 <item> — ₱<price>"
#   {total}      — "💰 Kabuuan: ₱<total>"  (omitted automatically for single-item orders)
#   {timestamp}  — formatted order date/time
#
# The item lines, the total line, and the single-vs-multiple-item rule are
# generated in code — the seller only edits the surrounding Tagalog wording.
DEFAULT_FB_TEMPLATE = """Hi {buyer_name}! 🎉 Ikaw ang nanalo sa aming live selling!

Narito ang iyong order:
{items}
{total}
📅 {timestamp}

Mag-aabiso kami para sa shipping details. Salamat! 🛍️"""
