#!/bin/sh
set -e
QPKG_NAME="EmbyUpdater"
QPKG_VER="1.2.0"
ARCH="x86_64"
WORK="/tmp/${QPKG_NAME}_build_$$"
SRC="$(cd "$(dirname "$0")" && pwd)"
OUT="${SRC}/build"

echo "=== ${QPKG_NAME}-shell QPKG Builder ==="
[ -x /sbin/qpkg ] || { echo "BLAD: brak /sbin/qpkg"; exit 1; }

PY3=""
for p in /share/CACHEDEV1_DATA/.qpkg/QBase24/bin/python3 /share/MD0_DATA/.qpkg/QBase24/bin/python3; do
    [ -x "$p" ] && PY3="$p" && break
done
[ -n "$PY3" ] || { echo "BLAD: brak python3"; exit 1; }
echo "   Python3: $PY3"

mkdir -p "$WORK/ctrl" "$WORK/data" "$OUT"

echo "[1/5] Pakowanie plików aplikacji..."
cp "${SRC}/icons/${QPKG_NAME}.gif"      "${WORK}/data/.qpkg_icon.gif"
cp "${SRC}/icons/${QPKG_NAME}_80.gif"   "${WORK}/data/.qpkg_icon_80.gif"
cp "${SRC}/icons/${QPKG_NAME}_gray.gif" "${WORK}/data/.qpkg_icon_gray.gif"
cp -r "${SRC}/shared/." "${WORK}/data/"
cp -r "${SRC}/bin"      "${WORK}/data/bin"
chmod +x "${WORK}/data/EmbyUpdater.sh"       2>/dev/null || true
chmod +x "${WORK}/data/emby-updater.sh"      2>/dev/null || true
chmod +x "${WORK}/data/www/cgi-bin/api.cgi"  2>/dev/null || true
chmod +x "${WORK}/data/bin/busybox"          2>/dev/null || true
# Strip Windows CRLF line endings from shell scripts
find "${WORK}/data" -name "*.sh" -o -name "*.cgi" | xargs sed -i 's/\r//' 2>/dev/null || true
cd "${WORK}/data" && tar czf "${WORK}/data.tar.gz" . && cd "${SRC}"
DATA_LEN=$(wc -c < "${WORK}/data.tar.gz" | tr -d " ")
DATA_BLOCKS=$(( (DATA_LEN + 1023) / 1024 ))
echo "   data.tar.gz: ${DATA_LEN} B (${DATA_BLOCKS} bloków)"

echo "[2/5] Pakowanie plików kontrolnych..."
cp "${SRC}/qpkg.cfg"         "${WORK}/ctrl/"
cp "${SRC}/package_routines" "${WORK}/ctrl/"
cp "${SRC}/qinstall.sh"      "${WORK}/ctrl/" 2>/dev/null || cp /share/homes/admin/EmbyUpdater/qinstall.sh "${WORK}/ctrl/"
cd "${WORK}/ctrl" && tar czf "${WORK}/control.tar.gz" . && cd "${SRC}"
tar cf "${WORK}/control.tar" -C "${WORK}" control.tar.gz
CTRL_LEN=$(wc -c < "${WORK}/control.tar" | tr -d " ")
echo "   control.tar: ${CTRL_LEN} B"

echo "[3/5] Budowanie shell headera..."
QPKG_FILE="${OUT}/${QPKG_NAME}_${QPKG_VER}_${ARCH}.qpkg"
$PY3 /share/homes/admin/EmbyUpdater/build-qpkg.sh-header.py \
    "$QPKG_FILE" "$QPKG_NAME" "$QPKG_VER" "$ARCH" "$CTRL_LEN" "$DATA_BLOCKS" 2>/dev/null || \
$PY3 - "${QPKG_FILE}" "${QPKG_NAME}" "${QPKG_VER}" "${ARCH}" "${CTRL_LEN}" "${DATA_BLOCKS}" << PYEOF
import sys
out_path=sys.argv[1]; qpkg_name=sys.argv[2]; qpkg_ver=sys.argv[3]
arch=sys.argv[4]; ctrl_len=int(sys.argv[5]); data_blocks=int(sys.argv[6])
PLACEHOLDER=b"PLACEHOLDER_00"; PH_LEN=len(PLACEHOLDER)
template=(b"#!/bin/sh\nfind_base(){\nHDD_MOUNT=\`/sbin/getcfg Public path -f /etc/config/smb.conf\`\nif [ -e \"\$HDD_MOUNT\" ]; then\n  if [ -z \"\$QINSTALL_PATH\" ]; then\n    pub=\`/sbin/getcfg Public path -f /etc/config/smb.conf\`\n    if [ ! -z \$pub ] && [ -d \$pub ]; then\n      p1=\`/bin/echo \$pub|/bin/cut -d/ -f2\`\n      p2=\`/bin/echo \$pub|/bin/cut -d/ -f3\`\n      [ -d \"/\${p1}/\${p2}/Public\" ] && QPKG_BASE=\"/\${p1}/\${p2}\"\n    fi\n    if [ -z \$QPKG_BASE ]; then\n      for d in /share/HDA_DATA /share/HDB_DATA /share/HDC_DATA /share/MD0_DATA /share/MD1_DATA /share/MD2_DATA /share/MD3_DATA; do\n        [ -d \$d/Public ] && QPKG_BASE=\$d && break\n      done\n    fi\n    [ -z \$QPKG_BASE ] && { echo \"Public share not found.\"; return 1; }\n    QPKG_INSTALL_PATH=\"\${QPKG_BASE}/.qpkg\"\n"
+f"    QPKG_DIR=\"\${{QPKG_INSTALL_PATH}}/{qpkg_name}\"\n".encode()
+b"  else\n    QPKG_INSTALL_PATH=\"\${QINSTALL_PATH}\"\n"
+f"    QPKG_DIR=\"\${{QINSTALL_PATH}}/{qpkg_name}\"\n".encode()
+b"  fi\n  return 0\nfi\n/bin/grep /mnt/HDA_ROOT /proc/mounts >/dev/null 2>&1 || exit 1\nQPKG_INSTALL_PATH=/mnt/HDA_ROOT/update_pkg\n"
+f"QPKG_DIR=\${{QPKG_INSTALL_PATH}}/{qpkg_name}\n".encode()
+b"}\n"
+f"arch_ok(){{ [ \"\$(/bin/uname -m)\" = \"{arch}\" ]; }}\n".encode()
+b"wrong_arch(){ echo \"Wymaga x86_64.\"; echo -1>/tmp/update_process; exit 1; }\n/bin/echo \"Install QNAP package on TS-NAS...\"\n/bin/grep /mnt/HDA_ROOT /proc/mounts >/dev/null 2>&1 || exit 1\narch_ok || wrong_arch\nfind_base\n"
+f"_EXTRACT_DIR=/tmp/{qpkg_name}_install\n".encode()
+b"/bin/mkdir -p \$_EXTRACT_DIR || exit 1\nscript_len="+PLACEHOLDER+b"\n/bin/dd if=\"\${0}\" bs=\$script_len skip=1|/bin/tar -xO|/bin/tar -xzv -C \$_EXTRACT_DIR || exit 1\n"
+f"offset=\$(/usr/bin/expr \$script_len + {ctrl_len})\n".encode()
+f"/bin/dd if=\"\${{0}}\" bs=\$offset skip=1|/bin/dd bs=1024 count={data_blocks} of=\$_EXTRACT_DIR/data.tar.gz || exit 1\n".encode()
+b"( cd \$_EXTRACT_DIR && /bin/sh qinstall.sh || echo \"Installation Abort.\" )\n/bin/rm -fr \$_EXTRACT_DIR && exit 0\nexit 1\n")
script_len=len(template)-PH_LEN+4
for _ in range(10):
    d=str(script_len).encode(); c=len(template)-PH_LEN+len(d)
    if c==script_len: break
    script_len=c
digits=str(script_len).encode(); header=template.replace(PLACEHOLDER,digits)
assert len(header)==script_len
open(out_path,"wb").write(header)
print(f"   Header: {script_len} B")
PYEOF

echo "[4/5] Łączenie archiwów i tail..."
cat "${WORK}/control.tar" >> "$QPKG_FILE"
cat "${WORK}/data.tar.gz" >> "$QPKG_FILE"
$PY3 - "${QPKG_FILE}" "${QPKG_NAME}" "${QPKG_VER}" << PYEOF
import sys
path,name,ver=sys.argv[1],sys.argv[2],sys.argv[3]
def pad(s,n): return (s[:n]+" "*n)[:n]
tail=pad("",10)+pad("",40)+pad("",10)+pad(name,20)+pad(ver,10)+pad("QNAPQPKG",10)
assert len(tail)==100
open(path,"ab").write(tail.encode("ascii"))
print("   Tail: 100 B")
PYEOF

echo "[5/5] Checksum QNAP..."
/sbin/qpkg --encrypt "$QPKG_FILE"
echo ""
echo "GOTOWE: $(basename $QPKG_FILE) ($(wc -c < $QPKG_FILE) B)"
rm -rf "$WORK"
