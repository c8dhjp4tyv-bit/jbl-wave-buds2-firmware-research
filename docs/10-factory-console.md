# 10 — Factory / engineering console

The firmware carries an AT-style factory and engineering command console that the
companion app does not expose. Commands are comma-separated request/response
strings (e.g. `ANC,1`), answered in a `,1,%s\n` / `,%s,1\n` form. A dispatch
table of 59 entries lives at `0x2C0F10B0`; each entry is an 8-byte
`[handler][name_ptr]` pair. The entries and their names were read directly from
the image; the UART bridge is `UARTCMD` (`sub_2C067E0C`), and an `AT+TEST=`
front-end is also present.

## Command inventory (verified)

All 59 names were extracted from the pointer table at `0x2C0F10B0` and the string
blob it references. Handler addresses are at image base `0x2C010000`.

Identity and calibration — write:

| Command | Handler | Note |
|---|---|---|
| `SETMACADDR` | `0x2C0681B1` | write BT MAC |
| `SETBLEADDR` | `0x2C068A19` | write BLE MAC |
| `SETTRIM` | `0x2C068D05` | write crystal trim (wrong value degrades RF) |
| `MIDW` | `0x2C0683D9` | module id write |
| `SNW` | `0x2C068429` | serial number write |
| `CIDW` | — | chip id write |
| `BTNAME` | `0x2C0681FD` | BT name |

Identity and calibration — read:

`GETMACADDR` (`0x2C068A6F`), `GETBLEADDR` (`0x2C068CB5`), `GETTRIM` (`0x2C068AC5`),
`MACADDR` (`0x2C067C3D`), `CIDR` (`0x2C068EED`), `MIDR` (`0x2C069135`),
`SNR` (`0x2C069269`), `SWR` (`0x2C067BF5`), `FW` (`0x2C067AFD`),
`LANGIDR` (`0x2C067B45`), `TONEIDR` (`0x2C0688D5`), `GETMICCOUNT` (`0x2C068355`).

Security-sensitive:

| Command | Handler | Note |
|---|---|---|
| `LINKKEY` | `0x2C06803D` | read/write BT pairing link key |
| `HMLICENSE` | `0x2C067B11` | Harman license |
| `FRST` | `0x2C068B67` | factory reset |
| `CLRALL` | `0x2C068879` | clear all data |
| `CLRHMTIME` | `0x2C06828D` | clear usage time |
| `BTCLR` | `0x2C068801` | clear BT pairings |

Modes and control: `DLD` (`0x2C067FF1`, download mode), `DUT` (`0x2C067DAD`,
device-under-test), `SHIP` (`0x2C0684E1`, ship mode), `PAIR` (`0x2C068DED`),
`TWSPAIR` (`0x2C068155`), `RSWITCH` (`0x2C068E19`, role switch),
`UARTCMD` (`0x2C067E0C`), `MEDIAPLAY` (`0x2C068059`), `SGP` (`0x2C067CED`),
`TWSR` (`0x2C067D4D`).

Audio / ANC engineering: `ANC` (`0x2C06851D`), `ANCLV` (`0x2C068591`),
`ANCGAIN` (`0x2C068175`), `AA` (`0x2C068729`), `TT` (`0x2C0687A5`),
`ENC` (`0x2C068619`), `ENCODEC` (`0x2C068221`), `DISCODEC` (`0x2C067EB9`),
`LOOPBACK` (`0x2C067F71`, audio loopback test).

Power / battery / sensors: `BATR` (`0x2C06847D`), `BATTVOLT` (`0x2C067B9D`),
`BATADC` (`0x2C068B05`), `BATCAL` (`0x2C068195`), `BATCONTROL` (`0x2C068D55`),
`AUTOPFR` (`0x2C067FD5`), `FPWROFF` (`0x2C0684DD`, force power off),
`CHARGE` (`0x2C067F4D`), `NTC` (`0x2C068391`, temperature), `LED` (`0x2C0686A1`).

Touch and test: `TOUCH` (`0x2C067E6D`), `TOUCHREAD` (`0x2C0684E5`),
`TOUCHSET` (`0x2C0684D5`), `TOUCHDEBUG` (`0x2C0684D9`), `ATEST` (`0x2C067F01`,
analog/ATE test), plus the `AT+TEST=` and `AT+TEST=TOUCH=1` front-end strings.

## Reachability — an open question

This console can read and write device identity (MAC/BLE address), radio
calibration (crystal trim) and the BT link key, so how it can be reached matters.
The evidence gathered here bounds but does not close the question:

- The documented entry point is UART — a `communication_server` thread and the
  `UARTCMD` bridge.
- The dispatch table (`0x2C0F10B0`) and the `UARTCMD` handler (`sub_2C067E0C`)
  have **no direct code cross-references** in IDA; they are reached via a computed
  table base, so the feeding path is not resolved by cross-reference alone.
- No path from the wireless command channel (BLE/SPP) to this AT parser was
  demonstrated.

So, on the evidence here, the console is reachable over UART / the `UARTCMD`
bridge; **over-the-air reachability is not demonstrated and remains an open
question** worth further analysis (tracing the `AT+TEST=` parser's callers and
the SPP passthrough). It is listed for completeness, not as a confirmed remote
surface.
