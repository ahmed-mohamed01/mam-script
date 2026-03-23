# MAM Automation Script

Automates MyAnonamouse bonus point management:

1. **Vault first** - tops up Millionaires Vault contribution to 2,000
2. **Then max GB** - buys maximum upload credit with remaining points

Runs via `docker run` and executes, prints results, exits. No persistent container needed.

## Setup (Unraid)

### 1. Pull the image

```bash
docker pull ghcr.io/ahmed-mohamed01/mam-script:latest
```

### 2. Create a User Script

1. Install **User Scripts** plugin (Settings → Plugins) if not already installed
2. Settings → **User Scripts** → **Add New Script** → name it `mam-automation`
3. Click the script name → **Edit Script** → paste contents of `mam-userscript.sh`:

```bash
#!/bin/bash
MAM_ID="your_mam_id_cookie_here"
MAM_USER="your@email.com"
MAM_PASS="your_password_here"

docker run --rm \
  -e MAM_ID="$MAM_ID" \
  -e MAM_USER="$MAM_USER" \
  -e MAM_PASS="$MAM_PASS" \
  ghcr.io/ahmed-mohamed01/mam-script:latest
```

4. Set schedule to **Custom** → `0 6 * * *` (daily at 6 AM UTC), or pick a preset
5. Click **Apply**

### 3. Test it

Click **Run Script** in User Scripts. You'll see the full output:

```
╔══════════════════════════════════════╗
║       MAM Automation Script          ║
╚══════════════════════════════════════╝

[1] Fetching bonus points …
    Bonus points: 5,130
...
╔══════════════════════════════════════╗
║            SUMMARY                   ║
╠══════════════════════════════════════╣
║  • Donated 2,000 to Millionaires Vault║
║  • Bought 6.2 GB upload credit       ║
╚══════════════════════════════════════╝
```

## How it works

| Step | Method                        | What                                                 |
| ---- | ----------------------------- | ---------------------------------------------------- |
| 1    | `requests` + `mam_id` cookie | Fetch bonus points from JSON API                     |
| 2    | Playwright (headless Chrome)  | Login with email/password                            |
| 3    | Playwright                    | Read vault contribution from `/millionaires/pot.php` |
| 4    | Playwright                    | Donate to vault if contribution < 2,000              |
| 5    | Playwright                    | Buy max GB on `/store.php` if vault is satisfied     |

~5 page loads per run. `--rm` auto-removes the container after each run.

## Files

- `mam_automation.py` — the automation script
- `Dockerfile` — container image
- `mam-userscript.sh` — Unraid User Script (copy-paste into User Scripts UI)
