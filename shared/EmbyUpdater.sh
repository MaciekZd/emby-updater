#!/bin/sh
CONF=/etc/config/qpkg.conf
QPKG_NAME="EmbyUpdater"
QPKG_ROOT=$(/sbin/getcfg $QPKG_NAME Install_Path -f ${CONF})
HTTP_PORT=9876
PID_FILE="/var/run/EmbyUpdater.pid"
export QPKG_ROOT HTTP_PORT

find_python3() {
    for p in python3 /share/CACHEDEV1_DATA/.qpkg/QBase24/bin/python3 \
              /share/MD0_DATA/.qpkg/QBase24/bin/python3; do
        command -v "$p" >/dev/null 2>&1 && { "$p" -c "import http.server" 2>/dev/null && echo "$p" && return 0; }
    done
    return 1
}

case "$1" in
  start)
    ENABLED=$(/sbin/getcfg $QPKG_NAME Enable -u -d FALSE -f $CONF)
    [ "$ENABLED" != "TRUE" ] && echo "$QPKG_NAME is disabled." && exit 1

    chmod +x "${QPKG_ROOT}/emby-updater.sh"  2>/dev/null
    chmod +x "${QPKG_ROOT}/server.py"         2>/dev/null

    [ -d /share/homes/admin ] && \
        ln -sf "${QPKG_ROOT}/emby-updater.sh" /share/homes/admin/emby-updater.sh 2>/dev/null

    PY3=$(find_python3) || {
        echo "EmbyUpdater: brak python3 – GUI niedostępne, CLI działa normalnie."
        echo "Skrypt: ${QPKG_ROOT}/emby-updater.sh"
        exit 0
    }

    # Update App Center icons from embedded fix_icons.py
    [ -f "${QPKG_ROOT}/fix_icons.py" ] && "$PY3" "${QPKG_ROOT}/fix_icons.py" 2>/dev/null

    cd "${QPKG_ROOT}"
    "$PY3" "${QPKG_ROOT}/server.py" &
    echo $! > "${PID_FILE}"
    /sbin/log_tool -t0 -uSystem -p127.0.0.1 -mlocalhost \
        -a "[EmbyUpdater] GUI: http://NAS_IP:${HTTP_PORT}/" 2>/dev/null
    echo "EmbyUpdater uruchomiony na porcie ${HTTP_PORT}"
    ;;

  stop)
    [ -f "${PID_FILE}" ] && { kill "$(cat "${PID_FILE}")" 2>/dev/null; rm -f "${PID_FILE}"; }
    rm -f /share/homes/admin/emby-updater.sh 2>/dev/null
    echo "EmbyUpdater zatrzymany."
    ;;

  restart)
    $0 stop; sleep 1; $0 start
    ;;

  *)
    echo "Użycie: $0 {start|stop|restart}"
    exit 1
    ;;
esac
exit 0
