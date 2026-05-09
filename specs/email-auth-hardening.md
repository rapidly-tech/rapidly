# Email authentication hardening — SPF / DKIM / DMARC for rapidly.tech

**Status:** action required in Cloudflare DNS.
**Severity (industry norm for bug bounties):** low-to-medium. Spoofing is real but it's a config gap, not a code exploit, and any receiver doing full DMARC enforcement already treats our mail as suspicious.
**Discoverability:** high. `mxtoolbox`, `dmarcian`, `dig` all surface it in seconds.

## What a researcher demonstrated
They sent a mail with `From: md@rapidly.tech` from a mail server that is not authorised to send for us. Because our published policy is permissive, it landed in an inbox without being rejected. Screenshot is on `/home/admin1/Downloads/preview.webp`.

## Current state (verified with `dig` on 2026-04-18)

```
rapidly.tech TXT  → v=spf1 include:_spf.google.com ~all
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ SOFT FAIL
rapidly.tech MX   → Google Workspace (aspmx.l.google.com et al)
google._domainkey.rapidly.tech TXT → v=DKIM1; k=rsa; p=<...>   ✅ DKIM is already correct
_dmarc.rapidly.tech TXT → v=DMARC1; p=none; rua=mailto:...cloudflare.net
                                    ^^^^^^^ MONITOR ONLY
```

## What's wrong

1. **SPF ends in `~all`.** The tilde is "soft fail": a receiver *may* accept mail that fails SPF. Change to `-all` (hard fail) so unauthenticated mail is visibly refused.
2. **DMARC is `p=none`.** That only requests reports; receivers will still deliver spoofed mail. Move to `p=quarantine` (junk folder for failing mail) and then `p=reject` once we've confirmed legit mail isn't breaking.
3. **DKIM is fine.** `google._domainkey` is already published. No change.

## Exact DNS changes to apply in Cloudflare

DNS lives at **Cloudflare** (confirmed: `terraform/` does not manage DNS; the DMARC `rua` destination is at `dmarc-reports.cloudflare.net`). These need to be edited in the Cloudflare dashboard, not in this repo.

### 1. Tighten SPF

Find the existing TXT record on `rapidly.tech`:

```
v=spf1 include:_spf.google.com ~all
```

Replace with:

```
v=spf1 include:_spf.google.com -all
```

Only change: `~all` → `-all`.

### 2. Move DMARC to quarantine (then later reject)

Find the TXT record on `_dmarc.rapidly.tech`:

```
v=DMARC1; p=none; rua=mailto:e936f6363bda421d84426b29c57f6333@dmarc-reports.cloudflare.net
```

Replace with (Step A — quarantine with inline reports):

```
v=DMARC1; p=quarantine; pct=100; rua=mailto:e936f6363bda421d84426b29c57f6333@dmarc-reports.cloudflare.net; ruf=mailto:e936f6363bda421d84426b29c57f6333@dmarc-reports.cloudflare.net; adkim=s; aspf=s; fo=1
```

Field-by-field:
- `p=quarantine` — receivers put failing mail in junk instead of delivering.
- `pct=100` — apply the policy to 100% of mail (not sampling).
- `rua=` — aggregate reports (daily summary of pass/fail counts per sender). Already configured via Cloudflare.
- `ruf=` — forensic per-failure reports. Optional but useful during the rollout to see real failures.
- `adkim=s` / `aspf=s` — strict alignment. "s" requires the From domain to exactly match the signing domain, not a subdomain.
- `fo=1` — request a forensic report on any single alignment failure.

### 3. Watch Cloudflare DMARC reports for 1–2 weeks

Cloudflare dashboard → Email → DMARC Management will show which senders are passing, which are failing, and why. Legitimate senders to expect:
- Google Workspace direct mail (should pass out of the box).
- Any transactional mail provider we use — Mailgun, Postmark, SendGrid, etc. If any appear in the fail bucket, they need their own SPF `include:` entry added and their DKIM key published.

### 4. Once reports are clean, escalate to p=reject

Change `p=quarantine` to `p=reject`:

```
v=DMARC1; p=reject; pct=100; rua=mailto:e936f6363bda421d84426b29c57f6333@dmarc-reports.cloudflare.net; ruf=mailto:e936f6363bda421d84426b29c57f6333@dmarc-reports.cloudflare.net; adkim=s; aspf=s; fo=1
```

At this point any unauthenticated mail claiming to be from `@rapidly.tech` is refused outright — the researcher's spoof attempt would never reach an inbox.

## Verification

After the records propagate (usually <5 min on Cloudflare):

```bash
dig +short TXT rapidly.tech | grep spf1
#   Expect: "v=spf1 include:_spf.google.com -all"

dig +short TXT _dmarc.rapidly.tech
#   Expect (after Step A): starts with v=DMARC1; p=quarantine
#   Expect (after Step B): starts with v=DMARC1; p=reject
```

Then reproduce the researcher's test:
1. Use a local mail sender (`swaks --from spoof@rapidly.tech --to your-personal-gmail@gmail.com --server smtp.example.com`) where the sending server is not authorised for our SPF.
2. Post-Step A: the mail lands in Spam / Junk.
3. Post-Step B: the mail bounces outright with an SMTP 550 or equivalent.

## Responding to the researcher

- Thank them, confirm the finding, and reference industry pricing: SPF/DMARC gap reports typically pay in the low to low-mid band ($50–$500 depending on program).
- Promise a timeline for the fix (quarantine within 24h, reject within 2 weeks after monitoring).
- Do **not** pay out as critical — it's a config gap, not a code exploit, discoverable with public tooling.

## Why this lives in the repo

DNS is at Cloudflare, not in Terraform, but the runbook belongs to the project so the next engineer who hits the same researcher report has the exact records to change and the reasoning behind the choice. When we do migrate DNS into Terraform (or Cloudflare's Terraform provider), copy these records from this doc verbatim.

## Future work

- Move Cloudflare DNS into Terraform (`cloudflare_record` resources) so changes are reviewable.
- Add a CI job that runs `dig +short TXT rapidly.tech` and fails if the SPF ends in `~all` or DMARC contains `p=none`. Cheap regression guard.
- Publish a BIMI record once DMARC is at `p=reject` for 30+ days — shows our logo next to authenticated mail in Gmail/Yahoo.
