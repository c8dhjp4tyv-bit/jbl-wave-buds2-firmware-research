# 02 — OTA container format

The OTA package (`COMPRESS_WAVE_BUDS2_OTA2_*.bin`) is a sequence of LZMA-"alone"
streams wrapped by a small header and followed by an ASCII CRC-32 trailer. Every
claim in this file is checked by [tools/ota_unpack.py](../tools/ota_unpack.py) /
[tools/ota_repack.py](../tools/ota_repack.py), which round-trip the official
package byte-for-byte.

## Top-level structure

```
+-------------------------------------------------------------+
| 8-byte package header                                       |
|   [0:4]  ff ff ff ff                 magic                  |
|   [4:8]  BE32  = compressed length of stream #0             |
+-------------------------------------------------------------+
| stream #0        (LZMA-alone)                               |
| BE32  = compressed length of stream #1                      |
| stream #1                                                   |
| BE32  = compressed length of stream #2                      |
|   ... (streams #2 .. #6, each followed by the next length)  |
| stream #7        (last; NO trailing length field)           |
+-------------------------------------------------------------+
| ASCII trailer:  "CRC32_OF_IMAGE=0x%08X\n"                   |
+-------------------------------------------------------------+
```

There are 8 streams. Streams #0..#6 each decompress to exactly `0x20000`
(131072) bytes; stream #7 decompresses to the remainder. Their concatenation is
the application image.

## LZMA stream header

Each stream is a raw `.lzma` ("alone") stream beginning with the 13-byte header:

```
5d 00 00 00 04 ff ff ff ff ff ff ff ff
└┬┘ └────┬────┘ └──────────┬──────────┘
 │       │                 └ uncompressed size = 0xFFFF…FF (unknown / -1)
 │       └ dictionary size = 0x04000000 (64 MiB), little-endian
 └ properties byte 0x5D  →  lc=3, lp=0, pb=2
```

Recompression must reproduce this exact header; `tools/ota_repack.py` uses
`FORMAT_ALONE` with `dict_size=0x04000000, lc=3, lp=0, pb=2`.

## Inter-stream length fields

The 4 bytes immediately after each of streams #0..#6 hold the **next** stream's
compressed length as a big-endian u32. The package header's `[4:8]` holds
stream #0's compressed length by the same convention. When repacking, if any
stream's compressed size changes, the corresponding length field (and, for
stream #0, the header) must be updated.

## CRC-32 trailer — exact recipe

- Algorithm: standard CRC-32 (poly `0xEDB88320`, init `0xFFFFFFFF`, reflected
  in/out, final XOR `0xFFFFFFFF`) — identical to `zlib.crc32`.
- Input range: file offset `0` through the **last byte of the literal ASCII
  prefix** `CRC32_OF_IMAGE=0x`, inclusive — i.e. everything up to but not
  including the hex digits.
- Output: 8 uppercase hex digits, then `\n`.

```python
import zlib
prefix = b"CRC32_OF_IMAGE=0x"
cut = package.find(prefix) + len(prefix)
crc = zlib.crc32(package[:cut]) & 0xFFFFFFFF   # compare to the printed value
```

This is a checksum, not a signature: it detects corruption, not tampering. Any
edit to the image can be made self-consistent by recomputing the trailer. See
[04-security-model.md](04-security-model.md) for why the device accepts such an
image.

Note: `ota_config.json`'s `md5` field is the MD5 of the **entire packaged file**
(used by the app to verify the download); it is unrelated to this internal CRC.

## Worked example — official 2.9.0

`COMPRESS_WAVE_BUDS2_OTA2_V2.9.0_56e441_20260918.bin`

| Field | Value |
|---|---|
| Packaged size | 549,558 bytes |
| Package MD5 | `91cd9ade57c67ddc05ba993c82e1cf53` |
| Header | `ff ff ff ff 00 01 28 0f` (`[4:8]` = `0x0001280F` = 75791 = len(stream #0)) |
| Compressed stream sizes | 75791, 56979, 75872, 84322, 86175, 84540, 69289, 16528 |
| Decompressed block sizes | `[131072 × 7, 38092]` → 955,596 total |
| Trailer offset | `0x8629C` (549,532) |
| Trailer | `CRC32_OF_IMAGE=0xA0C7CCEC\n` (file ends at `0x862B6`) |
| CRC input range | `package[:0x862AD]` |
| CRC check | `zlib.crc32(package[:0x862AD]) & 0xFFFFFFFF == 0xA0C7CCEC` |

## Reproduce

```
python3 tools/ota_unpack.py <your_official_package.bin>
```

This prints the header, per-stream compressed sizes, decompressed block sizes,
the CRC-32 (and whether it validates), and the package MD5 — all derived from
your own copy of the package.
