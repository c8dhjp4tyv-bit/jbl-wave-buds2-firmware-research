# 08 — Delivery method (reproducible)

This chapter documents, end to end, how a self-built firmware image is delivered
to a **device you own** through the companion app's own OTA path. It is the
practical consequence of three findings: no on-device firmware signing
([04](04-security-model.md)), no pinning preventing the tested patched-app OTA connection
([07](07-app-side-analysis.md)), and a fully understood container format
([02](02-ota-container-format.md)).

Nothing proprietary is distributed with this repository. You supply your own copy
of the app (obtained from your own device) and your own copy of the official
firmware (fetched from JBL's server for your product). See
[SECURITY.md](../SECURITY.md) for scope and disclosure.

> The device-side OTA path has no signature check, but it is not foolproof: a
> CRC-valid image that is functionally broken will still be activated and run,
> and there is no exposed recovery. Treat every flash as irreversible. Validate
> the pipeline with the **unmodified** official image first, and only ever flash
> an image derived from the **current** official image for your unit.

## Prerequisites

- The target earbuds (yours) and an Android phone with USB debugging.
- Android build tools: `apktool`, `zipalign`, `apksigner`, a debug keystore.
- `adb`, and a proxy with a user CA (`mitmproxy`).
- Your own copy of the JBL Headphones APK set (base + splits), pulled from your
  phone with `adb`.

## Step 1 — Capture the real OTA config (rewrite disabled)

Run the capture add-on with rewriting off and trigger an update check in the app:

```
WAVEBUDS_REWRITE=0 mitmdump --set confdir=<ca-dir> -s tools/mitm_addon.py
```

Record the `firmware.version`, `firmware.md5`, and `firmware.bin` for your PID,
and the host/path (`appstorage.onecloud.harman.com/jbl_headphones/ota/<pid>/`).
Download that official image and confirm its MD5 matches the config. This is your
baseline and your recovery image.

## Step 2 — Build your image from the current official one

Derive the modified image from the **current** official package so the version
matches your unit, then let the packer recompute the container CRC:

```
python3 tools/ota_repack.py inspect  <official_current.bin>
python3 tools/ota_repack.py make-test <official_current.bin> <custom.bin>
```

`ota_repack.py` refuses to emit unless an unchanged repack of the source is
byte-identical, so a mistake in the format handling cannot silently produce a bad
image. Record the new MD5 and size.

## Step 3 — Patch the app's network trust configuration

The stock app trusts system CAs only. To run the owner-controlled proxy
experiment, change **only** the network security configuration of your own APK:

```xml
<trust-anchors>
  <certificates src="system"/>
  <certificates src="user"/>
</trust-anchors>
```

The supplied `tools/patch_app.sh` decodes and rebuilds your APK, applies this
trust-anchor change, signs the resulting APK set with your own key, and aborts if
the expected network security config is absent. Verify that your APK manifest
actually references this configuration. It does **not** patch the
`com.jbl.counterfeit` package or override RSA anti-counterfeit verification:
no signature field was observed in the PID 2100 OTA config, and no connection
between the anti-counterfeit verifier and this OTA config was demonstrated.

> This broadens the modified app's trust in user CAs. Install a temporary proxy
> CA only on a phone you control, remove it after testing, and do not use this
> modified build for normal daily activity. Re-signing also requires uninstalling
> the official app, clearing its app data. Do not redistribute modified APKs.

## Step 4 — Install the user CA on the phone

Convert the proxy CA to DER and install it as a user certificate. On Samsung/One
UI the system file picker may not expose a `.pem`; convert to a `.crt` (DER) first:

```
openssl x509 -in mitmproxy-ca-cert.pem -outform der -out mitmproxy-ca.crt
```

Install it under user certificates and confirm it appears there.

## Step 5 — Serve your image (rewrite enabled)

Run the add-on with rewriting on. It rewrites only `firmware.version` and
`firmware.md5` in the config and serves your local image for the exact captured
appstorage request; `firmware.bin` (the filename) is preserved because the app
builds the download URL from it:

```
WAVEBUDS_REWRITE=1 \
WAVEBUDS_FW_PATH=<custom.bin> \
WAVEBUDS_VERSION=<version-greater-than-current> \
mitmdump --set confdir=<ca-dir> -s tools/mitm_addon.py
```

Route the phone through the proxy (an `adb reverse` USB tunnel to
`127.0.0.1:<port>` avoids Wi-Fi reachability issues).

## Step 6 — Flash and verify

In the app, open the update screen; it should show your advertised version. Start
the update, keep the earbuds out of the case and near the phone, and let it run to
completion. Then:

- Remove the proxy and `adb reverse` tunnel.
- Confirm the earbuds still pair and play audio (A2DP), and that the app connects
  and shows the expected version on its About screen.

Note: the GATT version readback (DeviceInfo feature 12) is not a reliable
post-update oracle on this unit (see [03](03-firmware-image-layout.md)); the audio
+ app checks are the real confirmation that the image activated and the device is
healthy.

## Validation performed

This method was validated on the author's unit by first flashing the **unchanged**
official 2.9.0 image through the patched app (result: "Update Successful"), then a
derived image differing in exactly one decompressed byte. The device reported
success, rebooted, and remained fully functional — the empirical basis for the
"no effective image signature" conclusion in [04](04-security-model.md).
