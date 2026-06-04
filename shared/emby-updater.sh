#!/bin/sh
# =============================================================================
# Emby Server Updater dla QNAP x86_64
# Użycie: emby-updater.sh {status|check|update|update-beta}
# =============================================================================
ARCH="x86_64"
GITHUB_API="https://api.github.com/repos/MediaBrowser/Emby.Releases/releases"
PYTHON3=""

# Detect download path: config.json > auto-detect volume > /tmp
find_volume() {
    for vol in /share/CACHEDEV1_DATA /share/CACHEDEV2_DATA /share/MD0_DATA \
               /share/MD1_DATA /share/HDA_DATA /share/HDB_DATA; do
        [ -d "$vol" ] && echo "$vol" && return 0
    done
    find /share -maxdepth 1 -name '*_DATA' -type d 2>/dev/null | head -1
}
QPKG_ROOT=$(/sbin/getcfg EmbyUpdater Install_Path -f /etc/config/qpkg.conf 2>/dev/null)
DL_PATH=""
if [ -n "$QPKG_ROOT" ] && [ -f "$QPKG_ROOT/config.json" ]; then
    DL_PATH=$(grep -o '"download_path":"[^"]*"' "$QPKG_ROOT/config.json" 2>/dev/null | cut -d'"' -f4)
fi
[ -z "$DL_PATH" ] && { VOL=$(find_volume); DL_PATH="${VOL:-/tmp}/Download"; }
TMP_DIR="${DL_PATH}/emby_update_$$"

LOG_FILE="/tmp/emby-updater.log"
[ -d "/share/homes/admin" ] && LOG_FILE="/share/homes/admin/emby-updater.log"

# Znajdź python3
for p in python3 \
          /share/CACHEDEV1_DATA/.qpkg/QBase24/bin/python3 \
          /share/CACHEDEV2_DATA/.qpkg/QBase24/bin/python3 \
          /share/MD0_DATA/.qpkg/QBase24/bin/python3 \
          /share/MD1_DATA/.qpkg/QBase24/bin/python3 \
          /share/HDA_DATA/.qpkg/QBase24/bin/python3; do
    [ -x "$p" ] && PYTHON3="$p" && break
done
[ -z "$PYTHON3" ] && PYTHON3=$(command -v python3 2>/dev/null || true)

log() {
    MSG="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo "$MSG" >> "$LOG_FILE"
    echo "$MSG"
}
die() { log "BLAD: $1"; echo "ERROR: $1" >&2; exit 1; }

get_installed_version() {
    /sbin/getcfg EmbyServer Version -f /etc/config/qpkg.conf 2>/dev/null
}

# Zwraca TAG|NAME|URL dla kanału (stable/beta) - używa Pythona do parsowania JSON
find_release() {
    CHANNEL="$1"
    TMP_JSON="/tmp/emby_rel_$$.json"

    wget -qO- \
        --header="Accept: application/vnd.github.v3+json" \
        --header="User-Agent: QNAP-Emby-Updater/1.0" \
        --timeout=30 \
        "${GITHUB_API}?per_page=20" > "$TMP_JSON" 2>/dev/null

    [ -s "$TMP_JSON" ] || { rm -f "$TMP_JSON"; return 1; }

    RESULT=$("$PYTHON3" - "$CHANNEL" "${ARCH}" "$TMP_JSON" << 'PYEOF'
import sys, json

channel = sys.argv[1]
arch    = sys.argv[2]
path    = sys.argv[3]

with open(path) as f:
    releases = json.load(f)

for r in releases:
    is_pre = r.get("prerelease", False)
    if channel == "stable" and is_pre:
        continue
    if channel == "beta" and not is_pre:
        continue
    tag  = r.get("tag_name", "")
    name = r.get("name", "")
    url  = next(
        (a["browser_download_url"]
         for a in r.get("assets", [])
         if "qnap" in a["name"]
         and arch in a["name"]
         and a["name"].endswith(".qpkg")),
        ""
    )
    if tag and url:
        print("{}|{}|{}".format(tag, name, url))
        break
PYEOF
)
    rm -f "$TMP_JSON"
    [ -n "$RESULT" ] && printf '%s\n' "$RESULT" && return 0
    return 1
}

compare_versions() {
    [ "$1" = "$2" ] && return 0
    set -- $(printf '%s' "$1" | tr '.' ' ')
    A1=${1:-0}; A2=${2:-0}; A3=${3:-0}; A4=${4:-0}
    set -- $(printf '%s' "$2" | tr '.' ' ')
    B1=${1:-0}; B2=${2:-0}; B3=${3:-0}; B4=${4:-0}
    for P in "$A1:$B1" "$A2:$B2" "$A3:$B3" "$A4:$B4"; do
        A=$(printf '%s' "$P" | cut -d: -f1)
        B=$(printf '%s' "$P" | cut -d: -f2)
        [ "$A" -gt "$B" ] 2>/dev/null && return 1
        [ "$A" -lt "$B" ] 2>/dev/null && return 2
    done
    return 0
}

do_install() {
    URL="$1"; VER="$2"
    mkdir -p "$TMP_DIR" || die "Nie mozna utworzyc katalogu tymczasowego"
    FILE="$TMP_DIR/emby_${VER}.qpkg"
    log "Pobieranie: $(basename "$URL")"
    wget -q --no-check-certificate -O "$FILE" "$URL" || { rm -rf "$TMP_DIR"; die "Pobieranie nie powiodlo sie"; }
    [ -s "$FILE" ] || { rm -rf "$TMP_DIR"; die "Plik pusty"; }
    log "Pobrano: $(du -sh "$FILE" | cut -f1)"
    log "Instalowanie $VER ..."
    sh "$FILE" >> "$LOG_FILE" 2>&1
    rm -rf "$TMP_DIR"
    NEW_VER=$(/sbin/getcfg EmbyServer Version -f /etc/config/qpkg.conf 2>/dev/null)
    CLEAN_VER=$(printf "%s" "$VER" | tr -cd "0-9.")
    CLEAN_NEW=$(printf "%s" "$NEW_VER" | tr -cd "0-9.")
    if [ "$CLEAN_NEW" = "$CLEAN_VER" ]; then
        log "Sukces: $NEW_VER"
        echo "SUCCESS"
    else
        log "Blad inst - wersja po: ${NEW_VER:-nieznana}"
        echo "FAILED:version_mismatch"
    fi
}

cmd_status() {
    INST=$(get_installed_version)
    echo "INSTALLED=${INST:-unknown}"
}

cmd_check() {
    log "--- sprawdzanie aktualizacji ---"
    INST=$(get_installed_version)
    log "Zainstalowana: ${INST:-nieznana}"

    SI=$(find_release stable)
    BI=$(find_release beta)
    ST=$(printf '%s' "$SI" | cut -d'|' -f1)
    SN=$(printf '%s' "$SI" | cut -d'|' -f2)
    BT=$(printf '%s' "$BI" | cut -d'|' -f1)
    BN=$(printf '%s' "$BI" | cut -d'|' -f2)

    log "Stable: ${ST:-blad}  Beta: ${BT:-blad}"
    printf 'INSTALLED=%s\nSTABLE_TAG=%s\nSTABLE_NAME=%s\nBETA_TAG=%s\nBETA_NAME=%s\n' \
        "${INST:-unknown}" "${ST:-unknown}" "${SN:-unknown}" \
        "${BT:-unknown}" "${BN:-unknown}"
}

cmd_update() {
    CHANNEL="${1:-stable}"
    log "=== aktualizacja ($CHANNEL) ==="
    INST=$(get_installed_version)
    log "Zainstalowana: ${INST:-nieznana}"

    INFO=$(find_release "$CHANNEL") || die "Nie udalo sie pobrac informacji o wersji"
    TTAG=$(printf '%s' "$INFO" | cut -d'|' -f1)
    TNAM=$(printf '%s' "$INFO" | cut -d'|' -f2)
    TURL=$(printf '%s' "$INFO" | cut -d'|' -f3)
    log "Docelowa: $TNAM (tag: $TTAG)"

    CI=$(printf '%s' "$INST" | tr -cd '0-9.')
    CT=$(printf '%s' "$TTAG" | tr -cd '0-9.')

    if [ -n "$CI" ]; then
        compare_versions "$CI" "$CT"
        CMP=$?
        [ $CMP -eq 0 ] && { log "Juz aktualne ($INST)"; echo "UP_TO_DATE"; exit 0; }
        [ $CMP -eq 1 ] && [ "$CHANNEL" = "stable" ] && \
            { log "Zainstalowana ($INST) nowsza niz stable"; echo "NEWER_INSTALLED"; exit 0; }
    fi

    do_install "$TURL" "$TTAG"
}

case "$1" in
    status)      cmd_status ;;
    check)       cmd_check ;;
    update)      cmd_update stable ;;
    update-beta) cmd_update beta ;;
    *)
        echo "Uzycie: $0 {status|check|update|update-beta}"
        exit 1
        ;;
esac
