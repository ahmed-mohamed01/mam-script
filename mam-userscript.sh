#!/bin/bash
# MAM Automation — Unraid User Script
# Schedule: daily (Custom cron or preset)
#
# Edit these three values:
MAM_ID="your_mam_id_cookie_here"
MAM_USER="your@email.com"
MAM_PASS="your_password_here"

docker run --rm \
  -e MAM_ID="$MAM_ID" \
  -e MAM_USER="$MAM_USER" \
  -e MAM_PASS="$MAM_PASS" \
  ghcr.io/ahmed-mohamed01/mam-script:latest
