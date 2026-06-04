import struct, os, shutil

# Palette (8 colors, indices 0-7)
# 0=black, 1=green, 2=white, 3=red, 4=dark-gray, 5=mid-gray, 6=light-gray, 7=unused(black)
PALETTE = [
    (0,   0,   0),    # 0 black bg
    (67,  176,  42),  # 1 Emby green
    (255, 255, 255),  # 2 white
    (210,  35,  35),  # 3 red arrow
    (30,   30,  30),  # 4 dark gray (gray variant bg)
    (90,   90,  90),  # 5 gray (gray variant shape)
    (200, 200, 200),  # 6 light gray (gray variant triangle)
    (0,    0,   0),   # 7 black (unused)
]

def make_gif(size, pixels_fn):
    pal_bytes = b''.join(bytes(c) for c in PALETTE)
    pixels = [pixels_fn(x, y, size) for y in range(size) for x in range(size)]

    def lzw_encode(data, min_bits=3):
        clear = 1 << min_bits
        eoi   = clear + 1

        # Pass 1: build code sequence
        table = {(i,): i for i in range(clear)}
        next_code = eoi + 1
        code_size = min_bits + 1
        codes = [clear]
        buf = ()
        for b in data:
            nb = buf + (b,)
            if nb in table:
                buf = nb
            else:
                codes.append(table[buf])
                if next_code < 4096:
                    table[nb] = next_code
                    next_code += 1
                    if next_code > (1 << code_size) and code_size < 12:
                        code_size += 1
                buf = (b,)
        if buf:
            codes.append(table[buf])
        codes.append(eoi)

        # Pass 2: pack codes into bits — code_size grows only on new table entries
        out = bytearray()
        cur = 0; bits = 0
        cur_size = min_bits + 1
        nc = eoi + 1  # mirrors next_code from pass 1
        for c in codes:
            cur |= c << bits
            bits += cur_size
            while bits >= 8:
                out.append(cur & 0xFF)
                cur >>= 8; bits -= 8
            # grow code_size only when a new table entry was just added
            if c != clear and c != eoi and nc < 4096:
                nc += 1
                if nc > (1 << cur_size) and cur_size < 12:
                    cur_size += 1
        if bits:
            out.append(cur & 0xFF)
        return bytes(out)

    lzw = lzw_encode(pixels)

    def sub_blocks(data):
        r = b''
        for i in range(0, len(data), 255):
            chunk = data[i:i+255]
            r += bytes([len(chunk)]) + chunk
        return r + b'\x00'

    gsd      = struct.pack('<HHBBB', size, size, 0xF0 | (3-1), 0, 0)
    img_desc = struct.pack('<BHHHHB', 0x2C, 0, 0, size, size, 0)
    img_data = bytes([3]) + sub_blocks(lzw)
    return b'GIF89a' + gsd + pal_bytes + img_desc + img_data + b'\x3B'


def in_diamond(x, y, cx, cy, size, scale):
    """Manhattan-distance diamond centered at cx,cy."""
    return abs(x - cx) + abs(y - cy) <= size * scale


def in_play_triangle(x, y, cx, cy, size):
    """White play triangle pointing right, centered in diamond."""
    tip_x  = cx + size * 0.13
    base_x = cx - size * 0.10
    half_h = size * 0.175
    if base_x <= x <= tip_x:
        progress = (x - base_x) / (tip_x - base_x)
        allowed  = half_h * (1.0 - progress)
        if abs(y - cy) <= allowed:
            return True
    return False


def in_red_arrow(x, y, size):
    """Red upward-pointing arrow in the top-right quadrant."""
    # Arrow bounding box: right 28%, top 46% of the image
    ax1 = size * 0.62
    ax2 = size * 0.90
    ay1 = size * 0.04
    ay2 = size * 0.48
    if not (ax1 <= x <= ax2 and ay1 <= y <= ay2):
        return False
    amid  = (ax1 + ax2) / 2
    aw    = ax2 - ax1
    ah    = ay2 - ay1
    rel_y = y - ay1  # 0 = top (tip), ah = bottom

    head_h   = ah * 0.44   # arrowhead height
    stem_w   = aw * 0.32   # stem width

    if rel_y <= head_h:
        # Triangle: narrow at top, full width at bottom of head
        progress = rel_y / head_h          # 0 at tip → 1 at base
        allowed  = (aw / 2) * progress
        return abs(x - amid) <= allowed
    else:
        return abs(x - amid) <= stem_w / 2


def icon_px(x, y, size):
    cx, cy = size / 2, size / 2

    # Red arrow on top (top-right, overlaps everything)
    if in_red_arrow(x, y, size):
        return 3  # red

    # Two overlapping diamonds create the Emby double-diamond shape
    # Main large diamond
    main = in_diamond(x, y, cx, cy, size, 0.41)
    # Smaller secondary diamond shifted down-left
    off  = size * 0.095
    sec  = in_diamond(x, y, cx - off, cy + off, size, 0.30)

    if main or sec:
        if in_play_triangle(x, y, cx, cy, size):
            return 2  # white
        return 1  # green

    return 0  # black


def gray_px(x, y, size):
    cx, cy = size / 2, size / 2
    off    = size * 0.095
    main   = in_diamond(x, y, cx, cy, size, 0.41)
    sec    = in_diamond(x, y, cx - off, cy + off, size, 0.30)
    if main or sec:
        if in_play_triangle(x, y, cx, cy, size):
            return 6  # light gray
        return 5  # mid gray
    return 4  # dark gray bg


base = '/share/homes/admin/EmbyUpdater/icons'
rss  = '/home/httpd/RSS/images'
os.makedirs(base, exist_ok=True)

for sz, name in [(64, 'EmbyUpdater'), (80, 'EmbyUpdater_80')]:
    data = make_gif(sz, icon_px)
    path = f'{base}/{name}.gif'
    with open(path, 'wb') as f:
        f.write(data)
    shutil.copy(path, f'{rss}/{name}.gif')

data = make_gif(64, gray_px)
path = f'{base}/EmbyUpdater_gray.gif'
with open(path, 'wb') as f:
    f.write(data)
shutil.copy(path, f'{rss}/EmbyUpdater_gray.gif')

print('Icons OK - Emby double-diamond + red up-arrow')
