#!/usr/bin/env bash
#
# Build helper for the delivery method (docs/08-delivery-method.md).
#
# It wraps the mechanical part of patching YOUR OWN copy of the JBL Headphones
# APK set: apply the network_security_config user-CA change, rebuild, align, and
# sign. The device-authenticity / anti-counterfeit verifier is deliberately not modified.
# Only the network trust configuration is changed for the owner's OTA experiment.
#
# This script distributes nothing proprietary. You supply the APKs, pulled from
# your own device:
#     adb shell pm path jbl.stc.com
#     adb pull <each path> ./apk-in/
#
# Requirements: apktool, zipalign, apksigner, keytool, adb on PATH.
#
# Usage:
#     ./patch_app.sh ./apk-in ./build ./debug.keystore
#
set -euo pipefail

APK_IN="${1:?usage: patch_app.sh <apk-in-dir> <build-dir> <keystore>}"
BUILD="${2:?build dir}"
KEYSTORE="${3:?keystore path}"
BASE_APK="$APK_IN/base.apk"

mkdir -p "$BUILD"

if [[ ! -f "$KEYSTORE" ]]; then
  echo "[*] creating a debug keystore at $KEYSTORE"
  keytool -genkeypair -v -keystore "$KEYSTORE" -alias patch -keyalg RSA -keysize 2048 \
    -validity 10000 -storepass android -keypass android -dname "CN=patch"
fi

echo "[*] decoding base.apk"
apktool d -f -o "$BUILD/base" "$BASE_APK"

NSC="$BUILD/base/res/xml/network_security_config.xml"
if [[ -f "$NSC" ]]; then
  echo "[*] adding a user-CA trust anchor to network_security_config.xml"
  # Insert a <certificates src="user"/> line after each <trust-anchors> that lacks one.
  python3 - "$NSC" <<'PY'
import sys, re, pathlib
p = pathlib.Path(sys.argv[1]); x = p.read_text()
if 'src="user"' not in x:
    x = re.sub(r'(<trust-anchors>)', r'\1\n            <certificates src="user"/>', x)
    p.write_text(x)
    print("    user anchor added")
else:
    print("    user anchor already present")
PY
else
  echo "[!] network_security_config.xml missing; refusing to proceed without reviewing the trust config" >&2
  exit 1
fi

echo "[*] leaving the device-authenticity verifier unchanged"

echo "[*] building"
apktool b -o "$BUILD/base.unsigned.apk" "$BUILD/base"

echo "[*] aligning"
zipalign -f 4 "$BUILD/base.unsigned.apk" "$BUILD/base.aligned.apk"

echo "[*] signing base + splits with your key"
apksigner sign --ks "$KEYSTORE" --ks-pass pass:android --out "$BUILD/base.signed.apk" "$BUILD/base.aligned.apk"
for split in "$APK_IN"/split_*.apk; do
  [[ -e "$split" ]] || continue
  name="$(basename "$split" .apk)"
  zipalign -f 4 "$split" "$BUILD/$name.aligned.apk"
  apksigner sign --ks "$KEYSTORE" --ks-pass pass:android --out "$BUILD/$name.signed.apk" "$BUILD/$name.aligned.apk"
done

echo
echo "[*] done. Install (this removes the original and its data):"
echo "    adb uninstall jbl.stc.com"
printf "    adb install-multiple"
printf " %q" "$BUILD/base.signed.apk" "$BUILD"/split_*.signed.apk
echo
