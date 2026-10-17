# 07 — App-side analysis (JBL Headphones)

The companion app (`jbl.stc.com`, "JBL Headphones") drives OTA. This chapter
covers how it locates the OTA configuration, the RSA-2048 verifier it ships, and
the transport-trust configuration — the three facts that determine whether a
self-hosted configuration can be delivered to the app. Static analysis used
`apktool` / `androguard`.

## OTA configuration flow

- `OTAUtil.getConfigUrl()` builds the configuration URL from the product's Harman
  storage route and PID; for PID 2100 the observed host/path was
  `https://appstorage.onecloud.harman.com/jbl_headphones/ota/2100/…`.
- The response model (`RemoteOTAConfig`) exposes: `version`, `downloadUrl`,
  `checkSum`, `localPath`, `otaMode`, `pid`, `whatsNewTitle`, `whatsNewContent`.
- The **served** `ota_config.json` for this product uses a nested schema:
  `product { pid, name, firmware { version, md5, bin, only_support_greater_than,
  app_greater_than, whats_new }, case, case_v2, dongle, tone }`.
  Here `bin` is a **filename**; the download URL is reconstructed by the app from
  the storage route + PID, so `bin` must stay intact when the config is modified.
- `OTAUtil.hasOTAUpdate()` compares device firmware against
  `only_support_greater_than` only when that field is present; it does not
  directly compare the live version with the advertised release. The captured
  config omitted that field.
- `OTAFragment.upgradeSuccessful()` builds its success message from the locally
  stored `online_version`. The success banner therefore reflects what the app was
  told to flash, not an independent read of the device version.

Observed config (PID 2100): `version 2.9.0`, `md5 91cd9ade57c67ddc05ba993c82e1cf53`,
`bin COMPRESS_WAVE_BUDS2_OTA2_V2.9.0_56e441_20260918.bin`.

## RSA-2048 configuration verifier

The app ships a configuration signature verifier:

- Class `com.jbl.counterfeit.Rsa2048DynamicVerifier`, method `verifySignatureLoop()`.
- Returns `com.jbl.counterfeit.enums.EnumVerifyResult` — an interface with
  `isPass()` / `isFail()` / `isUnknown()`; the enum implementations are
  `PASS`, `FAIL(WRONG_SIGNATURE)`, `UNKNOWN`.
- A PEM public key is embedded in `classes3.dex`.

Important nuance: the `ota_config.json` body captured for PID 2100 contained **no
signature field**. So for this product/endpoint, no config signature was present
to enforce in the observed flow. The verifier exists in the binary; whether it
gated this specific product's config could not be confirmed from the captured
traffic.

## Transport trust

- No `okhttp` `CertificatePinner` is configured for the OTA hosts — there is no
  application-level certificate pinning.
- `network_security_config.xml` originally trusts `system` anchors only. Adding a
  `<certificates src="user"/>` anchor (a one-line change) makes the app trust a
  user-installed CA.

Consequently the OTA configuration and download can be intercepted with a user CA
and a local proxy — no pinning bypass is required. This is the transport-side
finding that, combined with the absence of on-device firmware signing
([04](04-security-model.md)), makes the delivery method in
[08](08-delivery-method.md) possible.

## Summary of the client-side gate

Image trust is delegated entirely to the client: the app decides what to flash
from a configuration it fetches over TLS, with (for this product) no enforced
config signature observed and no certificate pinning, and the device applies
whatever passes CRC. The gate is the phone's trust store and the app's own
checks — both under the device owner's control.
