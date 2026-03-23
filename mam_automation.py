"""
MAM Automation Script
---------------------
Prioritizes vault contribution (up to 2,000), then buys max GB
with remaining bonus points.

Credentials via environment variables:
    MAM_ID   — your mam_id session cookie
    MAM_USER — your MAM email
    MAM_PASS — your MAM password

Install deps:
    pip install requests playwright
    playwright install chromium

Usage:
    MAM_ID=xxx MAM_USER=you@email.com MAM_PASS=xxx python mam_automation.py
    # Or set env vars in docker-compose.yml
"""

import os
import re
import sys
import asyncio
import requests
from playwright.async_api import async_playwright

# ── Constants ─────────────────────────────────────────────────────────────────

VAULT_TARGET = 2000
BASE_URL     = "https://www.myanonamouse.net"
JSON_API_URL = f"{BASE_URL}/jsonLoad.php"
STORE_URL    = f"{BASE_URL}/store.php"
VAULT_URL    = f"{BASE_URL}/millionaires/pot.php"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

# ── Credentials (from environment variables) ─────────────────────────────────

MAM_ID   = os.environ.get("MAM_ID", "")
EMAIL    = os.environ.get("MAM_USER", "")
PASSWORD = os.environ.get("MAM_PASS", "")

# ── Helpers ───────────────────────────────────────────────────────────────────

def extract_number(text):
    if not text:
        return None
    m = re.search(r"[\d,]+", str(text))
    return int(m.group().replace(",", "")) if m else None

# ── Fetch bonus points via JSON API ──────────────────────────────────────────

def fetch_bonus_points() -> int:
    session = requests.Session()
    session.cookies.set("mam_id", MAM_ID, domain=".myanonamouse.net")
    resp = session.get(JSON_API_URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    if not isinstance(data, dict) or "username" not in data:
        print("  ❌  Session rejected — mam_id may be expired or wrong IP.")
        sys.exit(1)

    bp = None
    for key in ["seedbonus", "bonusPoints", "bonus_points", "seedBonus", "bonus"]:
        if key in data:
            bp = int(data[key])
            break

    if bp is None:
        print("  ❌  Could not find bonus points in JSON API response.")
        sys.exit(1)

    return bp

# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    W = 52
    border = "=" * (W + 2)
    print(f"\n+{border}+")
    print(f"| {'MAM Automation Script':^{W}} |")
    print(f"+{border}+\n")

    # Validate credentials
    if not MAM_ID:
        print("  ❌  MAM_ID environment variable not set"); sys.exit(1)
    if not EMAIL or not PASSWORD:
        print("  ❌  MAM_USER/MAM_PASS environment variables not set"); sys.exit(1)

    # ── 1. Get bonus points ───────────────────────────────────────────────
    print("[1] Fetching bonus points …")
    bonus_points = fetch_bonus_points()
    print(f"    Bonus points: {bonus_points:,}\n")

    # Track what the script does
    actions = []
    starting_bp = bonus_points

    # ── 2. Playwright session ─────────────────────────────────────────────
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page    = await context.new_page()

        # ── Login ─────────────────────────────────────────────────────
        print("[2] Logging in …")
        await page.goto(f"{BASE_URL}/login.php", timeout=30000)
        await page.wait_for_load_state("domcontentloaded", timeout=15000)
        await page.fill("input[name='email']", EMAIL)
        await page.fill("input[name='password']", PASSWORD)
        await page.click("input[type='submit']")
        await page.wait_for_load_state("networkidle", timeout=20000)

        if "logout" not in (await page.content()).lower():
            print("    ❌  Login failed — check MAM_USER/MAM_PASS\n")
            await browser.close()
            sys.exit(1)
        print("    ✅  Logged in\n")

        # ── 3. Read vault contribution ────────────────────────────────
        print("[3] Checking Millionaires Vault …")
        await page.goto(VAULT_URL, timeout=30000)
        await page.wait_for_load_state("networkidle", timeout=15000)

        vault_contrib = 0
        # Table has multiple donation rows — sum ALL amounts (2nd cell each row)
        try:
            rows = page.locator("div#mainBody table tbody tr")
            count = await rows.count()
            for i in range(count):
                cells = rows.nth(i).locator("td")
                if await cells.count() >= 2:
                    val = (await cells.nth(1).inner_text()).strip()
                    amount = extract_number(val)
                    if amount:
                        vault_contrib += amount
        except Exception:
            pass

        # If no table found, check page text for "no donations on record"
        if vault_contrib == 0:
            body_text = await page.inner_text("body")
            if "no donations on record" in body_text.lower():
                vault_contrib = 0
            else:
                # Try regex fallback
                m = re.search(r"(?:contributed|donated)[^\d]{0,40}([\d,]+)", body_text, re.I)
                if m:
                    vault_contrib = extract_number(m.group(1)) or 0

        print(f"    Current vault contribution: {vault_contrib:,}")
        vault_needed = max(0, VAULT_TARGET - vault_contrib)
        print(f"    Needed to reach {VAULT_TARGET:,}: {vault_needed:,}\n")

        # ── 4. Vault top-up (priority) ────────────────────────────────
        vault_donated = 0
        if vault_needed > 0:
            # How much can we actually donate? Limited by bonus points
            # Round down to nearest 100
            can_donate = min(vault_needed, (bonus_points // 100) * 100)

            if can_donate >= 100:
                print(f"[4] Donating {can_donate:,} to vault …")

                # Navigate to donate page
                donate_btn = page.locator("input[value='Donate to the pot now']")
                if await donate_btn.is_visible(timeout=3000):
                    await donate_btn.click()
                    await page.wait_for_load_state("networkidle", timeout=15000)

                    # Donate in a single selection (dropdown goes up to 2000)
                    await page.select_option("select[name='Donation']", str(can_donate))
                    await page.click("input[value='Donate Points']")
                    await page.wait_for_load_state("networkidle", timeout=15000)

                    # Verify success
                    result = await page.inner_text("div#mainBody")
                    if "thank you" in result.lower():
                        vault_donated = can_donate
                        bonus_points -= can_donate
                        actions.append(f"Donated {can_donate:,} to Millionaires Vault")
                        print(f"    ✅  Donated {can_donate:,} to vault")
                        print(f"    Remaining bonus points: {bonus_points:,}\n")
                    else:
                        print(f"    ❌  Donation may have failed. Response: {result[:200]}\n")
                else:
                    print("    ❌  Donate button not found on vault page\n")
            else:
                print(f"[4] Not enough bonus points to donate (have {bonus_points:,}, need at least 100)")
                actions.append(f"Skipped vault donation — only {bonus_points:,} bonus points available")
                print()
        else:
            print(f"[4] Vault already at {vault_contrib:,} — no donation needed\n")
            actions.append(f"Vault already at {vault_contrib:,} (target: {VAULT_TARGET:,})")

        # ── 5. Buy max GB (only if vault is satisfied) ────────────────
        vault_now = vault_contrib + vault_donated
        if vault_now >= VAULT_TARGET and bonus_points >= 500:
            print(f"[5] Buying max GB with {bonus_points:,} bonus points …")

            await page.goto(STORE_URL, timeout=30000)
            await page.wait_for_load_state("networkidle", timeout=15000)

            # Expand upload credit section
            try:
                await page.click("#uploadCredit", timeout=5000)
                await page.wait_for_timeout(800)
            except Exception:
                pass

            # Click "Max Affordable" button (note trailing space in value)
            btn = page.locator("button[value='Max Affordable ']").first
            if await btn.is_visible(timeout=3000):
                await btn.click()

                # Confirm purchase dialog
                await page.wait_for_timeout(1000)
                ok_btn = page.locator(".ui-dialog-buttonset button").first
                if await ok_btn.is_visible(timeout=5000):
                    await ok_btn.click()
                    await page.wait_for_timeout(1000)

                    # Dismiss success dialog
                    try:
                        ok_btn2 = page.locator(".ui-dialog-buttonset button").first
                        if await ok_btn2.is_visible(timeout=3000):
                            await ok_btn2.click()
                    except Exception:
                        pass

                    # Read updated bonus points from store page
                    bp_after = bonus_points
                    try:
                        bp_el = page.locator("#currentBonusPoints")
                        if await bp_el.is_visible(timeout=3000):
                            bp_after = extract_number(await bp_el.inner_text()) or bp_after
                    except Exception:
                        pass

                    gb_spent = bonus_points - bp_after
                    gb_bought = gb_spent / 500 if gb_spent > 0 else 0
                    bonus_points = bp_after
                    actions.append(f"Bought {gb_bought:.1f} GB upload credit ({gb_spent:,} bonus points)")
                    print(f"    ✅  Bought {gb_bought:.1f} GB ({gb_spent:,} points spent)")
                    print(f"    Remaining bonus points: {bonus_points:,}\n")
                else:
                    print("    ❌  Confirmation dialog did not appear\n")
            else:
                print("    ❌  'Max Affordable' button not found\n")

        elif vault_now < VAULT_TARGET:
            print(f"[5] Skipping GB purchase — vault not yet at {VAULT_TARGET:,} (currently {vault_now:,})\n")
            actions.append("Skipped GB purchase — vault priority")
        else:
            print(f"[5] Skipping GB purchase — only {bonus_points:,} bonus points remaining (need 500)\n")
            actions.append(f"Skipped GB purchase — only {bonus_points:,} points remaining")

        await browser.close()

    # ── Summary ───────────────────────────────────────────────────────────
    W = 52
    border = "=" * (W + 2)
    print(f"+{border}+")
    print(f"| {'SUMMARY':^{W}} |")
    print(f"+{border}+")
    print(f"| {'Starting bonus points:':<28}{starting_bp:>{W-28},} |")
    print(f"| {'Final bonus points:':<28}{bonus_points:>{W-28},} |")
    print(f"| {'Vault contribution:':<28}{vault_contrib + vault_donated:>{W-28},} |")
    print(f"+{border}+")
    for action in actions:
        print(f"|  - {action:<{W-2}} |")
    if not actions:
        print(f"|  {'- No actions taken':<{W}} |")
    print(f"+{border}+\n")

if __name__ == "__main__":
    asyncio.run(main())