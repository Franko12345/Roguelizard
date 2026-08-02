"""Pure-Python PNG encoder for RGBA grids.

We avoid Pillow so the asset generator runs anywhere with just the stdlib
(zlib). Output is non-interlaced 8-bit RGBA -- exactly what issue #191
demands. Each scanline is prefixed by filter byte 0 (None).
"""

import struct
import zlib


def _chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def write_rgba_png(path: str, width: int, height: int, pixels: bytes) -> None:
    """Write a non-interlaced 8-bit RGBA PNG.

    ``pixels`` must be exactly width * height * 4 bytes (R,G,B,A per pixel)
    laid out row-major from top-left.
    """
    assert len(pixels) == width * height * 4

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)

    # add filter byte (0) at the start of every scanline
    stride = width * 4
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        raw.extend(pixels[y * stride : (y + 1) * stride])
    idat = zlib.compress(bytes(raw), 9)

    blob = sig + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")
    with open(path, "wb") as fh:
        fh.write(blob)
