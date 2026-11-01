# Why the TEST email went to Spam — read-only diagnosis (2026-10-31)

No email was sent for this diagnosis; no DNS record, mailbox label, contact or filter was changed. Checked from the Pi with public DNS and the locally built copy of the same message (fictional-recipient `.eml`, identical body and headers apart from To/Reply-To).

## Confirmed

| Item | Evidence | Result |
|---|---|---|
| Delivery | Owner: one TEST received at the owner's Gmail, first in Spam, marked "Not spam" (now INBOX + CATEGORY_UPDATES) | The other recipient's delivery is **not confirmed** |
| SMTP | `hip test-edition send` | Resend accepted both recipients (`250`), 1 attempt each, no resend |
| SPF | owner's Gmail headers: `spf=pass`; DNS `send.read.starhub.vip` TXT `v=spf1 ip4:52.3.252.119 ip4:44.222.39.36 ip4:199.249.231.0/24 ~all`, MX `feedback.forge.rmta.net` | pass; envelope domain `send.read.starhub.vip` is in the same organisational domain as From `read.starhub.vip` (relaxed alignment) |
| DKIM | owner's Gmail headers: `dkim=pass` for `read.starhub.vip` (plus the provider's own signature); DNS `resend._domainkey.read.starhub.vip` present | pass, aligned with From |
| DMARC | `_dmarc.read.starhub.vip` and `_dmarc.starhub.vip`: **NXDOMAIN** at the authoritative Cloudflare nameserver (jakub.ns.cloudflare.com) and at 8.8.8.8 / 1.1.1.1 | **no DMARC policy published** for the sending subdomain or the root. Gmail can therefore only evaluate DMARC as "none"; it was not failing, there was nothing to pass |
| From domain | `read.starhub.vip`: no MX, no A record; root `starhub.vip`: no MX | the From domain cannot receive mail (replies go to the configured Reply-To) |
| Message | 90,897 bytes; `text/plain` + `text/html`; 7 links (archive.org ×4, `5fa1bd38.website-test-7i3.pages.dev` ×3); no images, no tracking pixels or redirect links; Reply-To set; **no `List-Unsubscribe` header** | — |

## Candidate factors (not established causes)

Gmail did not state its reason, so none of these is proven to have caused this placement:
1. **New sending subdomain with no reputation** (first message ever from `read.starhub.vip`).
2. **No DMARC policy** on the subdomain or root.
3. **Links to a shared `pages.dev` preview host**, different from the From domain (preview only; production links would be `starhub.vip`).
4. **No `List-Unsubscribe` header** (now added for future messages: `<mailto:REPLY_TO?subject=暂停>`, matching the footer text; commit fbfc362).
5. Long text (~90 KB) with a "【测试】" subject.
6. From domain without MX/A.

Not checked (no access with a sending-only key): Resend's per-message delivery events / Deliverability Insights. SMTP `accepted` ≠ provider `delivered` ≠ Gmail Inbox.

## Owner decisions (not done here)

- Publish a monitoring DMARC record for the sending subdomain, e.g. `_dmarc.read.starhub.vip TXT "v=DMARC1; p=none; rua=mailto:<an address you read>"`. Start at `p=none`; do not jump to quarantine/reject; do not change the root domain's records without checking other mail services first.
- Optionally give `read.starhub.vip` an MX (or keep replies on Reply-To only).
- Recipients may add the sender to contacts; that is a recipient choice, not a fix for sender authentication.
- Keep volume low and regular; no list buying, no warm-up blasts, no dedicated IP. No further TEST is authorised by this diagnosis.

References: https://support.google.com/mail/answer/16457426 · https://support.google.com/mail/answer/180707 · https://resend.com/guides/email/deliverability/why-emails-go-to-spam
