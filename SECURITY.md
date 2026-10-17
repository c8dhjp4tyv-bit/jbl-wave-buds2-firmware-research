# Security disclosure

## Summary

This repository documents, among other findings, a security-relevant property of
the JBL Wave Buds 2 (Bestechnic BES1306) update path:

- The OTA firmware image is **not cryptographically signed**. On-device integrity
  rests on CRC-32 alone (container trailer plus per-segment and whole-image CRC-32
  in the protocol). A modified-but-CRC-valid image is accepted and booted (see
  [docs/04-security-model.md](docs/04-security-model.md)).
- The companion app does **not pin** its OTA endpoints, so the OTA configuration
  and download can be intercepted with a user-installed CA (see
  [docs/07-app-side-analysis.md](docs/07-app-side-analysis.md)).

## Impact

For the device owner, this enables legitimate firmware modification. The
security concern is the combination: an attacker able to (a) get a user CA
trusted on a victim's phone (e.g. a tampered app build) or (b) hold a
man-in-the-middle position where the app's transport trust can be subverted,
could cause the app to deliver an arbitrary firmware image that the device will
accept because it is only CRC-checked. There is no on-device signature backstop
and no exposed recovery path if a bad image is activated.

## Scope and ethics

- All research was performed on hardware owned by the author.
- No JBL/Harman firmware binary, decompiled image, or application code is
  distributed here. The tooling operates on artifacts the reader obtains from
  their own device and from the vendor's public server.
- Nothing here targets third parties or other people's devices.

## Coordinated disclosure

This is published in the spirit of coordinated disclosure. Harman product
security advisories are coordinated through the vendor's PSIRT and CERT@VDE (see,
e.g., Harman Bluetooth Security Advisories and VDE-2024-076). The maintainer
welcomes contact from Harman/JBL product security to discuss remediation
(firmware image signing / secure boot provisioning, and transport pinning) and
will coordinate on timing.

- Vendor: Harman International (JBL) — product security / PSIRT.
- Maintainer contact: umutcagand@protonmail.com

If you are a researcher who finds an error in this analysis, or a vendor
representative, please open an issue or email the maintainer.
