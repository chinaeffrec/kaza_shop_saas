#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# Kaza Shop — Security Audit Script
# Runs: bandit (SAST), pip-audit (CVE scan), safety (alternative CVE),
#        trufflehog secrets check.
#
# Usage:
#   chmod +x scripts/security_audit.sh
#   ./scripts/security_audit.sh
#   ./scripts/security_audit.sh --ci    # Exit non-zero on any findings
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

CI_MODE=false
[[ "${1:-}" == "--ci" ]] && CI_MODE=true

REPORT_DIR="security/reports"
mkdir -p "$REPORT_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FAIL=0

# ── Colour helpers ─────────────────────────────────────────────────────────────
RED='\033[0;31m'; YEL='\033[0;33m'; GRN='\033[0;32m'; NC='\033[0m'
info()  { echo -e "${GRN}[+]${NC} $*"; }
warn()  { echo -e "${YEL}[!]${NC} $*"; }
error() { echo -e "${RED}[✗]${NC} $*"; FAIL=1; }

echo ""
echo "══════════════════════════════════════════════════════"
echo "  Kaza Shop Security Audit  —  $(date '+%Y-%m-%d %H:%M')"
echo "══════════════════════════════════════════════════════"
echo ""

# ── 1. Bandit (Python SAST) ────────────────────────────────────────────────────
info "Running Bandit (Python SAST)…"
if command -v bandit &>/dev/null; then
    BANDIT_OUT="$REPORT_DIR/bandit_${TIMESTAMP}.json"
    bandit \
        -r app/ \
        -x app/tests/ \
        --confidence-level MEDIUM \
        --severity-level MEDIUM \
        --format json \
        -o "$BANDIT_OUT" 2>/dev/null || true

    HIGH=$(python3 -c "
import json, sys
d = json.load(open('$BANDIT_OUT'))
h = [r for r in d.get('results',[]) if r['issue_severity']=='HIGH']
print(len(h))
for r in h[:5]:
    print(f\"  {r['filename']}:{r['line_number']} — {r['issue_text']}\")
" 2>/dev/null)
    if [[ "${HIGH%%$'\n'*}" -gt 0 ]]; then
        error "Bandit: HIGH severity findings found"
        echo "$HIGH"
    else
        info "Bandit: no HIGH findings"
    fi
    info "  Full report: $BANDIT_OUT"
else
    warn "bandit not installed — skipping (pip install bandit)"
fi

echo ""

# ── 2. pip-audit (CVE scan) ───────────────────────────────────────────────────
info "Running pip-audit (CVE scan)…"
if command -v pip-audit &>/dev/null; then
    PIP_AUDIT_OUT="$REPORT_DIR/pip_audit_${TIMESTAMP}.json"
    if pip-audit \
        --requirement requirements.txt \
        --output "$PIP_AUDIT_OUT" \
        --format json \
        --no-deps \
        2>/dev/null; then
        info "pip-audit: no known vulnerabilities"
    else
        VULN_COUNT=$(python3 -c "
import json
d = json.load(open('$PIP_AUDIT_OUT'))
vulns = [v for pkg in d.get('dependencies',[]) for v in pkg.get('vulns',[])]
print(len(vulns))
for v in vulns[:10]:
    print(f\"  {v.get('id','?')} {v.get('fix_versions','')}: {v.get('description','')[:80]}\")
" 2>/dev/null)
        if [[ "${VULN_COUNT%%$'\n'*}" -gt 0 ]]; then
            error "pip-audit: ${VULN_COUNT%%$'\n'*} CVE(s) found"
            echo "$VULN_COUNT"
        fi
    fi
    info "  Full report: $PIP_AUDIT_OUT"
else
    warn "pip-audit not installed — skipping (pip install pip-audit)"
fi

echo ""

# ── 3. Safety (alternative CVE check) ─────────────────────────────────────────
info "Running safety check…"
if command -v safety &>/dev/null; then
    SAFETY_OUT="$REPORT_DIR/safety_${TIMESTAMP}.txt"
    safety check \
        --requirement requirements.txt \
        --output text \
        > "$SAFETY_OUT" 2>&1 || {
        error "safety: vulnerabilities found — see $SAFETY_OUT"
        head -20 "$SAFETY_OUT"
    }
    info "  Full report: $SAFETY_OUT"
else
    warn "safety not installed — skipping (pip install safety)"
fi

echo ""

# ── 4. TruffleHog (secrets in git history) ────────────────────────────────────
info "Running TruffleHog (secrets scan)…"
if command -v trufflehog &>/dev/null; then
    TRUFFLE_OUT="$REPORT_DIR/trufflehog_${TIMESTAMP}.json"
    trufflehog \
        filesystem \
        --directory . \
        --exclude-paths .trufflehog_ignore \
        --json \
        > "$TRUFFLE_OUT" 2>/dev/null || true

    SECRETS=$(wc -l < "$TRUFFLE_OUT" | tr -d ' ')
    if [[ "$SECRETS" -gt 0 ]]; then
        error "TruffleHog: potential secrets found ($SECRETS)"
        head -5 "$TRUFFLE_OUT"
    else
        info "TruffleHog: no secrets detected"
    fi
    info "  Full report: $TRUFFLE_OUT"
else
    warn "trufflehog not installed — skipping (brew install trufflesecurity/trufflehog/trufflehog)"
fi

echo ""

# ── 5. Hardcoded secrets check (grep fallback) ────────────────────────────────
info "Grepping for common secret patterns…"
GREP_HITS=$(grep -rn \
    --include="*.py" --include="*.js" --include="*.env" \
    -E "(secret_key|password|api_key|token)\s*=\s*['\"][A-Za-z0-9+/=_-]{16,}['\"]" \
    app/ seller-panel/src/ 2>/dev/null \
    | grep -v "test\|example\|placeholder\|changeme\|xxxx\|••••\|your_\|<" \
    || true)

if [[ -n "$GREP_HITS" ]]; then
    warn "Possible hardcoded secrets found:"
    echo "$GREP_HITS"
else
    info "No obvious hardcoded secrets found"
fi

echo ""

# ── 6. Dependency freshness ────────────────────────────────────────────────────
info "Checking for outdated packages…"
if command -v pip &>/dev/null; then
    OUTDATED=$(pip list --outdated --format=columns 2>/dev/null | tail -n +3 | head -20 || true)
    if [[ -n "$OUTDATED" ]]; then
        warn "Outdated packages:"
        echo "$OUTDATED"
    else
        info "All packages are up to date"
    fi
fi

echo ""

# ── Summary ────────────────────────────────────────────────────────────────────
echo "══════════════════════════════════════════════════════"
if [[ $FAIL -eq 0 ]]; then
    echo -e "${GRN}  ✅  Security audit passed${NC}"
else
    echo -e "${RED}  ❌  Security audit found issues (see above)${NC}"
fi
echo "  Reports saved to: $REPORT_DIR/"
echo "══════════════════════════════════════════════════════"
echo ""

$CI_MODE && exit $FAIL || exit 0
