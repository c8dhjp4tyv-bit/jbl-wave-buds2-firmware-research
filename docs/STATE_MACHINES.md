# Recovered state machines

Two state machines drive an update: the TOTA v2 transport handshake and the OTA
command sequence. Both were recovered from the app (`STATIC_IDA` on the app) and
the device handler (`STATIC_IDA` on `0x2C0918BC`), and corroborated on hardware.

## TOTA v2 transport handshake

```
          App                              Device
   ─────────────────                 ──────────────────
   [IDLE]
     │  START  01 10 | rblen | random_b   (cleartext, HEAD..TAIL)
     ▼ ───────────────────────────────────▶
                                       02 10 | random_a        → status 769
     ◀───────────────────────────────────
   derive: hash_key_b = SHA256(besFunc.func1(random_a, random_b))
           aes_key    = besFunc.func(hash_key_b)   (16-byte AES-128)
     │  CONFIRM 03 10 21 00 20 | hash_key_b        (cleartext)
     ▼ ───────────────────────────────────▶
                                       00 10 … "connect success."  → status 770
     ◀───────────────────────────────────
   [CONNECTED]  totauccess = true; subsequent payloads are AES-CBC
```

After `CONNECTED`, inner commands are framed `00 90 | len16 | <opcode cmd>` and
AES-encrypted inside each HEAD..TAIL frame. Details: [05](05-ble-gatt-and-commands.md).

## OTA command sequence (device handler `0x2C0918BC`)

A precondition gates the whole sequence: the device accepts OTA opcodes only
while `MEMORY[0x20026BA0] ∈ {2,4}` (`0x2C0905E4`). The companion app reaches that
state through the normal connection flow; an external central does not (see
[INCIDENTS.md](INCIDENTS.md) #1).

```
getProtocolVersion 0x99 ─▶ getCurrentVersion 0x8E ─▶ setOtaUser 0x97 (USER_FLAG=1)
      ─▶ setUpgradeType 0x9D ─▶ selectSide 0x90 ─▶ checkBreakPoint 0x8C
      ─▶ OTAConfigure 0x86   [check: len==92, CRC-32 over first 88 bytes]
      ─▶ startOTA 0x80       [record image size → 0x2002739C, CRC → 0x200273AC; "BEST" magic]
      ─▶ loop { dataPacket 0x85 → staging flash;  every 16384 B: segmentCRC 0x82
                [running CRC-32 0x200273B0 == expected] }
      ─▶ dataDone 0x88       [all received: 0x200273A0 == 0x2002739C]
      ─▶ imageOverwriteConfirm 0x92  [whole-image CRC ok → set activation flag 0x200274F4=1]
      ─▶ reboot / activation copy (staging → application)
```

Every gate in this machine is a CRC-32 comparison or the `"BEST"` magic
(`0x54534542`); there is no signature or hash step (see
[04](04-security-model.md)). Device→app status codes map `B_xx → 23xx`
(e.g. config OK `2320`, segment-CRC OK `2324`, whole-CRC OK `2326`, errors
`2368`–`2373`); the full list is in [06](06-ota-protocol.md).

## Activation / brick window

The accepting side writes the new image to the staging region while the running
application is untouched (download is brick-safe). The post-reboot activation
copy is the risk window: a CRC-valid but functionally broken image is copied and
run, and no rollback path was identified in the application image
([04](04-security-model.md)). The ROM behavior at activation is `UNRESOLVED`.
