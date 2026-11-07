#!/usr/bin/env bash
# Sync a test-specification workbook to Confluence. Dry-run unless --apply is given.
#
# Usage:
#   CONFLUENCE_EMAIL=me@nos.pt CONFLUENCE_PARENT_PAGE_ID=123456 \
#     sync_confluence/scripts/sync-testspec.sh [--apply] [WORKBOOK.xlsx] [extra flags]
#
# CONFLUENCE_API_TOKEN is prompted for when not set in the environment.
set -euo pipefail

export CONFLUENCE_URL=https://nos-corporativo.atlassian.net
export CONFLUENCE_EMAIL=diogo.m.rodrigues@parceiros.nos.pt
export CONFLUENCE_API_TOKEN=ATATT3xFfGF07JXi3NRg3i4X5aBNpO8QRlye3Hb9rjC-uJ_uJ4nTXic37uQEgrJMfDe0vPolI-jWEYOKT0tSrnTpsZYdo-n2qNHQKrV_U8-RrXefyr87nTfECgbmTTpi9L8NLpNMKhPSjEtVP9bc70y34d1eeDus3VOiPOT4SkheNlVMqJ_N46A=D6A198F3
export CONFLUENCE_SPACE_KEY=HaaS
export CONFLUENCE_PARENT_PAGE_ID=2042265750
export CONFLUENCE_MANAGED_BY=managed-by-testspec-demo
export TESTSPEC_XLSX="../CRIP-L3VPN-CISCO__l3vpn_tests.xlsx"
# export TESTSPEC_XLSX="../CRIP-L3VPN-NOKIA__l3vpn_tests.xlsx"

uv run sync-confluence-testspec "$@"
