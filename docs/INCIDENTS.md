# Experiment timeline: failures and resolutions

What broke during this research and how it was resolved. Dead ends are kept
because they bound the conclusions.

| # | Symptom | Cause | Resolution |
|---|---|---|---|
| 1 | A standalone BLE central established the encrypted TOTA v2 session and got replies to `setOtaUser`/`getProtocolVersion`, but `OTAConfigure`/`startOTA` were dropped. | The device gates OTA command handlers on an internal TWS/connection state (`0x2C0905E4`: `MEMORY[0x20026BA0] ∈ {2,4}`), which an external central cannot set. | Pivoted to delivery through the companion app, which runs in the accepting state. See [08](08-delivery-method.md). |
| 2 | Installing the proxy CA on the Samsung phone failed with "certificate file could not be read". | The One UI file picker did not expose the `.pem`. | Converted the CA to DER `.crt` (`openssl x509 -outform der`) and installed it as a user certificate. |
| 3 | The phone would not reach the host proxy over Wi-Fi reliably. | Local network reachability. | Used an `adb reverse` USB tunnel to `127.0.0.1:<port>`. |
| 4 | The first rewrite proxy run returned no OTA config; TLS failed before the response. | `mitmdump` was started without the project CA directory, so its cert did not match the installed CA. | Restarted with `--set confdir=<ca-dir>`; the installed CA then matched. |
| 5 | After a confirmed update, the host could not complete BLE GATT service discovery ("Service Discovery has not been performed yet"). | Host-side BlueZ service cache for the earbuds' rotating LE address. | Removed the stale LE device, power-cycled the host Bluetooth adapter; this is a host-stack quirk, not a device fault. |
| 6 | The read-only BLE `DeviceInfo` version returned `2.0.0` both before and after a confirmed official 2.9.0 update. | The GATT version triple and the OTA release label are different namespaces (see [03](03-firmware-image-layout.md)). | Treated the app About screen + A2DP as the real post-update oracle; the GATT triple is not reliable here. |
| 7 | `extract_factory_table.py` failed on the 2.9.0 decompressed image at the analyzed-build table offset ("name pointer outside the image"). | The IDA image (`wavebuds.elf`) is an **earlier, separately compiled build** than the 2.9.0 package; addresses are relocated. | Discovered and documented the two-build differential ([PROVENANCE.md](PROVENANCE.md)); made the tool locate the table **structurally** so it is build-independent. |
| 8 | Bulk function export via the IDA MCP returned only ~10 rows per call. | The listing tools cap their output. | Shipped `export_ida_inventory.py` (regenerates the full inventory inside IDA) plus enumeration statistics, and a curated `analyzed_functions.csv`, instead of a bulk inline CSV. |
