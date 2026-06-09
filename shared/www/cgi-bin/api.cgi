#!/bin/sh
# =============================================================================
# EmbyUpdater — CGI API handler (pure shell, no Python required)
# Handles all routes via PATH_INFO: /login /logout /status /check
#                                    /update /config /settings /schedule
#                                    /selfcheck /selfupdate
# =============================================================================

QPKG_ROOT=$(/sbin/getcfg EmbyUpdater Install_Path -f /etc/config/qpkg.conf 2>/dev/null)
[ -z "$QPKG_ROOT" ] && QPKG_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

CONFIG="$QPKG_ROOT/config"          # key=value config file
SCRIPT="$QPKG_ROOT/emby-updater.sh"
SESSION_DIR="/tmp/eu_sessions"
SESSION_TTL=28800                    # 8h
CRONTAB="/etc/config/crontab"
CRON_MARKER="# EmbyUpdater-auto"
RESET_FILE="$QPKG_ROOT/reset_credentials"
GH_REPO="MaciekZd/emby-updater"

mkdir -p "$SESSION_DIR"

ROUTE="${PATH_INFO:-/}"
METHOD="${REQUEST_METHOD:-GET}"

# Read POST body (Content-Length bytes)
BODY=""
if [ "$METHOD" = "POST" ]; then
    LEN="${CONTENT_LENGTH:-0}"
    [ "$LEN" -gt 0 ] 2>/dev/null && read -r -n "$LEN" BODY 2>/dev/null || read -r BODY
fi

# ── Config (key=value) ────────────────────────────────────────────────────────

cfg_get()  { grep -m1 "^$1=" "$CONFIG" 2>/dev/null | cut -d= -f2-; }
cfg_set()  {
    if grep -q "^$1=" "$CONFIG" 2>/dev/null; then
        sed -i "s|^$1=.*|$1=$2|" "$CONFIG"
    else
        printf '%s=%s\n' "$1" "$2" >> "$CONFIG"
    fi
}

init_config() {
    [ -f "$RESET_FILE" ] && rm -f "$RESET_FILE" "$CONFIG"
    [ -f "$CONFIG" ] && return
    printf 'username=admin\npassword_hash=%s\nlanguage=pl\ndownload_path=\nsched_enabled=false\nsched_channel=stable\nsched_frequency=weekly\nsched_day=0\nsched_hour=3\n' \
        "$(sha256 admin)" > "$CONFIG"
}

# ── Crypto ────────────────────────────────────────────────────────────────────

sha256() { printf '%s' "$1" | sha256sum | cut -d' ' -f1; }

# ── Session ───────────────────────────────────────────────────────────────────

new_session() {
    TOKEN=$(dd if=/dev/urandom bs=32 count=1 2>/dev/null | sha256sum | cut -d' ' -f1)
    printf '%s' "$(( $(date +%s) + SESSION_TTL ))" > "$SESSION_DIR/$TOKEN"
    printf '%s' "$TOKEN"
}

valid_session() {
    local tok="$1" exp now
    [ -z "$tok" ] || [ ! -f "$SESSION_DIR/$tok" ] && return 1
    exp=$(cat "$SESSION_DIR/$tok"); now=$(date +%s)
    [ "$now" -gt "$exp" ] && { rm -f "$SESSION_DIR/$tok"; return 1; }
    printf '%s' "$(( now + SESSION_TTL ))" > "$SESSION_DIR/$tok"
    return 0
}

get_cookie() {
    printf '%s' "$HTTP_COOKIE" | tr ';' '\n' | \
        grep "^[[:space:]]*$1=" | sed 's/^[^=]*=//' | tr -d ' ' | head -1
}

# ── JSON helpers ──────────────────────────────────────────────────────────────

json_esc() {
    printf '%s' "$1" | tr -d '\r' | awk '{
        gsub(/\\/, "\\\\")
        gsub(/"/, "\\\"")
        gsub(/\t/, "\\t")
        printf "%s\\n", $0
    }' | sed '$ s/\\n$//'
}

json_str_val() {
    printf '%s' "$BODY" | grep -o "\"$1\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" | \
        head -1 | sed 's/.*"[^"]*"[[:space:]]*:[[:space:]]*"\([^"]*\)"/\1/'
}

json_raw_val() {
    printf '%s' "$BODY" | grep -o "\"$1\"[[:space:]]*:[[:space:]]*[^,}]*" | \
        head -1 | sed 's/.*:[[:space:]]*//' | tr -d ' '
}

# ── HTTP output ───────────────────────────────────────────────────────────────

send_json() {
    printf 'Content-Type: application/json\r\n\r\n%s\n' "$1"
}

send_status() {
    printf 'Status: %s\r\nContent-Type: application/json\r\n\r\n%s\n' "$1" "$2"
}

require_auth() {
    TOKEN=$(get_cookie eu_sess)
    valid_session "$TOKEN" && return 0
    send_status "401 Unauthorized" '{"error":"unauthorized"}'
    exit 0
}

# ── Schedule (crontab) ────────────────────────────────────────────────────────

read_cron_line() {
    grep "$CRON_MARKER" "$CRONTAB" 2>/dev/null | head -1
}

apply_schedule() {
    sed -i "/$CRON_MARKER/d" "$CRONTAB" 2>/dev/null
    local enabled="$1" channel="$2" freq="$3" day="$4" hour="$5"
    [ "$enabled" = "true" ] || return 0
    local act="update"
    [ "$channel" = "beta" ] && act="update-beta"
    case "$freq" in
        daily)   CRON_TIME="0 $hour * * *" ;;
        weekly)  CRON_TIME="0 $hour * * $day" ;;
        monthly) CRON_TIME="0 $hour 1 * *" ;;
        *)       CRON_TIME="0 $hour * * 0" ;;
    esac
    printf '%s %s %s\n' "$CRON_TIME" "$SCRIPT $act" "$CRON_MARKER" >> "$CRONTAB"
    crontab "$CRONTAB" 2>/dev/null
}

# ── Version helpers ───────────────────────────────────────────────────────────

get_app_version() {
    /sbin/getcfg EmbyUpdater Version -f /etc/config/qpkg.conf 2>/dev/null
}

# Compare semver: returns 0=equal 1=a>b 2=a<b
compare_ver() {
    [ "$1" = "$2" ] && return 0
    local a1 a2 a3 b1 b2 b3
    IFS='.' read -r a1 a2 a3 <<EOF
$1
EOF
    IFS='.' read -r b1 b2 b3 <<EOF
$2
EOF
    a1=${a1:-0}; a2=${a2:-0}; a3=${a3:-0}
    b1=${b1:-0}; b2=${b2:-0}; b3=${b3:-0}
    if   [ "$a1" -gt "$b1" ] 2>/dev/null; then return 1
    elif [ "$a1" -lt "$b1" ] 2>/dev/null; then return 2
    elif [ "$a2" -gt "$b2" ] 2>/dev/null; then return 1
    elif [ "$a2" -lt "$b2" ] 2>/dev/null; then return 2
    elif [ "$a3" -gt "$b3" ] 2>/dev/null; then return 1
    elif [ "$a3" -lt "$b3" ] 2>/dev/null; then return 2
    fi
    return 0
}

# ── Route handlers ────────────────────────────────────────────────────────────

handle_login() {
    USER=$(json_str_val username)
    PASS=$(json_str_val password)
    STORED_USER=$(cfg_get username)
    STORED_HASH=$(cfg_get password_hash)
    PASS_HASH=$(sha256 "$PASS")
    if [ "$USER" = "$STORED_USER" ] && [ "$PASS_HASH" = "$STORED_HASH" ]; then
        TOKEN=$(new_session)
        printf 'Set-Cookie: eu_sess=%s; Path=/; HttpOnly\r\nContent-Type: application/json\r\n\r\n{"ok":true}\n' "$TOKEN"
    else
        send_json '{"ok":false,"error":"Invalid credentials"}'
    fi
}

handle_logout() {
    TOKEN=$(get_cookie eu_sess)
    [ -n "$TOKEN" ] && rm -f "$SESSION_DIR/$TOKEN"
    printf 'Set-Cookie: eu_sess=; Path=/; Max-Age=0\r\nContent-Type: application/json\r\n\r\n{"ok":true}\n'
}

handle_status() {
    require_auth
    OUT=$("$SCRIPT" status 2>/dev/null)
    OUT_ESC=$(json_esc "$OUT")
    LANG=$(cfg_get language)
    SE=$(cfg_get sched_enabled); SC=$(cfg_get sched_channel)
    SF=$(cfg_get sched_frequency); SD=$(cfg_get sched_day); SH=$(cfg_get sched_hour)
    CRON=$(read_cron_line)
    CRON_ESC=$(json_esc "$CRON")
    APP_VER=$(get_app_version)
    send_json "{\"output\":\"$OUT_ESC\",\"language\":\"$LANG\",\"app_version\":\"${APP_VER:-?}\",\"cron\":\"$CRON_ESC\",\"schedule\":{\"enabled\":${SE:-false},\"channel\":\"${SC:-stable}\",\"frequency\":\"${SF:-weekly}\",\"day\":${SD:-0},\"hour\":${SH:-3}}}"
}

handle_check() {
    require_auth
    OUT=$("$SCRIPT" check 2>/dev/null)
    OUT_ESC=$(json_esc "$OUT")
    send_json "{\"output\":\"$OUT_ESC\"}"
}

handle_update() {
    require_auth
    CH=$(json_str_val channel)
    [ "$CH" = "beta" ] && ACT="update-beta" || ACT="update"
    OUT=$("$SCRIPT" "$ACT" 2>/dev/null)
    OUT_ESC=$(json_esc "$OUT")
    send_json "{\"output\":\"$OUT_ESC\"}"
}

handle_config() {
    require_auth
    USER=$(cfg_get username); LANG=$(cfg_get language); DL=$(cfg_get download_path)
    SE=$(cfg_get sched_enabled); SC=$(cfg_get sched_channel)
    SF=$(cfg_get sched_frequency); SD=$(cfg_get sched_day); SH=$(cfg_get sched_hour)
    send_json "{\"username\":\"$USER\",\"language\":\"$LANG\",\"download_path\":\"$DL\",\"schedule\":{\"enabled\":${SE:-false},\"channel\":\"${SC:-stable}\",\"frequency\":\"${SF:-weekly}\",\"day\":${SD:-0},\"hour\":${SH:-3}}}"
}

handle_settings() {
    require_auth
    NEW_LANG=$(json_str_val language)
    NEW_USER=$(json_str_val username)
    NEW_PASS=$(json_str_val password)
    LOGOUT_ALL=$(json_raw_val logout_all)

    [ -n "$NEW_LANG" ] && cfg_set language "$NEW_LANG"
    [ -n "$NEW_USER" ] && cfg_set username "$NEW_USER"
    [ -n "$NEW_PASS" ] && cfg_set password_hash "$(sha256 "$NEW_PASS")"
    # allow clearing download_path
    printf '%s' "$BODY" | grep -q '"download_path"' && \
        cfg_set download_path "$(printf '%s' "$BODY" | grep -o '"download_path":"[^"]*"' | cut -d'"' -f4)"
    [ "$LOGOUT_ALL" = "true" ] && rm -f "$SESSION_DIR"/* 2>/dev/null

    send_json '{"ok":true}'
}

handle_schedule() {
    require_auth
    SE=$(json_raw_val enabled)
    SC=$(json_str_val channel)
    SF=$(json_str_val frequency)
    SD=$(json_raw_val day)
    SH=$(json_raw_val hour)

    cfg_set sched_enabled   "${SE:-false}"
    cfg_set sched_channel   "${SC:-stable}"
    cfg_set sched_frequency "${SF:-weekly}"
    cfg_set sched_day       "${SD:-0}"
    cfg_set sched_hour      "${SH:-3}"

    apply_schedule "$SE" "$SC" "$SF" "$SD" "$SH"
    send_json '{"ok":true}'
}

handle_selfcheck() {
    require_auth
    INST=$(get_app_version)

    LATEST=$(curl -sf --max-time 10 \
        -H "Accept: application/vnd.github+json" \
        "https://api.github.com/repos/${GH_REPO}/releases/latest" 2>/dev/null \
        | grep '"tag_name"' | head -1 \
        | sed 's/.*"tag_name"[[:space:]]*:[[:space:]]*"v\{0,1\}\([^"]*\)".*/\1/')

    if [ -z "$LATEST" ]; then
        send_json "{\"ok\":false,\"error\":\"fetch_failed\",\"installed\":\"${INST:-?}\"}"
        return
    fi

    UPDATE_AVAIL="false"
    compare_ver "${INST:-0}" "$LATEST"
    [ $? -eq 2 ] && UPDATE_AVAIL="true"

    send_json "{\"ok\":true,\"installed\":\"${INST:-?}\",\"latest\":\"$LATEST\",\"update_available\":$UPDATE_AVAIL}"
}

handle_selfupdate() {
    require_auth
    INST=$(get_app_version)

    # Get download URL for the QPKG asset
    RELEASE_JSON=$(curl -sf --max-time 10 \
        -H "Accept: application/vnd.github+json" \
        "https://api.github.com/repos/${GH_REPO}/releases/latest" 2>/dev/null)

    LATEST=$(printf '%s' "$RELEASE_JSON" | grep '"tag_name"' | head -1 \
        | sed 's/.*"tag_name"[[:space:]]*:[[:space:]]*"v\{0,1\}\([^"]*\)".*/\1/')
    DL_URL=$(printf '%s' "$RELEASE_JSON" | grep '"browser_download_url"' | grep '\.qpkg"' | head -1 \
        | sed 's/.*"browser_download_url"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')

    [ -z "$DL_URL" ] && { send_json '{"ok":false,"error":"no_asset"}'; return; }

    compare_ver "${INST:-0}" "$LATEST"
    [ $? -ne 2 ] && { send_json '{"ok":false,"error":"already_latest"}'; return; }

    # Download and install in background (detached from CGI process)
    QPKG_TMP="/tmp/EmbyUpdater_update_$$.qpkg"
    (
        curl -sL --max-time 120 "$DL_URL" -o "$QPKG_TMP" 2>/dev/null && \
        sh "$QPKG_TMP" 2>/dev/null
        rm -f "$QPKG_TMP"
    ) &

    send_json "{\"ok\":true,\"version\":\"$LATEST\"}"
}

# ── Main dispatch ─────────────────────────────────────────────────────────────

init_config

case "$ROUTE" in
    /login)       handle_login       ;;
    /logout)      handle_logout      ;;
    /status)      handle_status      ;;
    /check)       handle_check       ;;
    /update)      handle_update      ;;
    /config)      handle_config      ;;
    /settings)    handle_settings    ;;
    /schedule)    handle_schedule    ;;
    /selfcheck)   handle_selfcheck   ;;
    /selfupdate)  handle_selfupdate  ;;
    *) send_status "404 Not Found" '{"error":"not found"}' ;;
esac
