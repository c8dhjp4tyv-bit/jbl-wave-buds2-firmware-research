"""Capture JBL Wave Buds OTA config and optionally serve a local test image.

Default mode only saves upstream responses. Rewriting is fail-closed and only
enabled with WAVEBUDS_REWRITE=1 plus an explicit firmware path and version.
For this product, firmware.bin is a filename; it must remain unchanged because
the app constructs the download URL from its Harman storage path and PID.

Operates on your own device's traffic. See docs/08-delivery-method.md.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from mitmproxy import http


ROOT = Path(__file__).resolve().parent
CAPTURE_DIR = Path(os.environ.get("WAVEBUDS_CAPTURE_DIR", ROOT / "captures"))
TARGET_PID = os.environ.get("WAVEBUDS_PID", "2100")
TARGET_HOST = "appstorage.onecloud.harman.com"
TARGET_PREFIX = f"/jbl_headphones/ota/{TARGET_PID}/"
CONFIG_NAME = "ota_config.json"


def _find_firmware_records(value: Any, path: tuple[str, ...] = ()) -> list[dict[str, Any]]:
    """Find model objects that match the app's firmware.version/md5/bin schema."""
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        fw = value.get("firmware")
        if isinstance(fw, dict) and {"version", "md5", "bin"}.issubset(fw):
            pid = value.get("pid")
            path_has_pid = TARGET_PID in path
            if (pid is not None and str(pid) == TARGET_PID) or (pid is None and path_has_pid):
                found.append(fw)
        for key, child in value.items():
            found.extend(_find_firmware_records(child, path + (str(key),)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_find_firmware_records(child, path + (str(index),)))
    return found


def _firmware_request_key(bin_value: Any, config_url: str) -> tuple[str, str] | None:
    """Resolve the exact appstorage request generated from firmware.bin."""
    value = str(bin_value).strip()
    if not value:
        return None

    parsed = urlsplit(value)
    if parsed.scheme:
        host = (parsed.hostname or "").lower()
        path = parsed.path
    else:
        # This app expects a filename and builds the URL from the config path.
        if "/" in value or "\\" in value or value in {".", ".."}:
            return None
        config = urlsplit(config_url)
        host = (config.hostname or "").lower()
        path = config.path.rsplit("/", 1)[0] + "/" + value

    path = path.split("?", 1)[0]
    if host != TARGET_HOST or not path.startswith(TARGET_PREFIX):
        return None
    return host, path


class WavebudsOTA:
    def __init__(self) -> None:
        self.firmware_paths: dict[tuple[str, str], tuple[Path, str]] = {}

    def response(self, flow: http.HTTPFlow) -> None:
        request_path = flow.request.path.split("?", 1)[0]
        if CONFIG_NAME in request_path.lower():
            self._capture_config(flow, request_path)
            return
        self._serve_local_firmware(flow, request_path)

    def _capture_config(self, flow: http.HTTPFlow, request_path: str) -> None:
        CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        parts = urlsplit(flow.request.pretty_url)
        safe_url = f"{parts.scheme}://{parts.netloc}{parts.path}"
        meta_path = CAPTURE_DIR / f"ota_config_{stamp}_meta.json"
        meta_path.write_text(
            json.dumps(
                {
                    "method": flow.request.method,
                    "url": safe_url,
                    "status": flow.response.status_code,
                    "content_type": flow.response.headers.get("content-type", ""),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        try:
            body_text = flow.response.get_text(strict=False)
        except Exception:
            body_text = ""

        if not body_text:
            raw = flow.response.get_content(strict=False) or b""
            (CAPTURE_DIR / f"ota_config_{stamp}.bin").write_bytes(raw)
            print(f"OTA config capture is non-text: status={flow.response.status_code} bytes={len(raw)}")
            return

        original_path = CAPTURE_DIR / f"ota_config_{stamp}_original.json"
        original_path.write_text(body_text, encoding="utf-8")
        print(
            f"OTA config captured: status={flow.response.status_code} "
            f"host={flow.request.pretty_host} path={request_path} file={original_path}"
        )

        try:
            document = json.loads(body_text)
        except json.JSONDecodeError as error:
            print(f"OTA config is not JSON ({error}); leaving response unchanged")
            return

        records = _find_firmware_records(document)
        for record in records:
            print(
                "OTA firmware record: "
                f"version={record.get('version')!r} md5={record.get('md5')!r} "
                f"bin={record.get('bin')!r}"
            )

        if os.environ.get("WAVEBUDS_REWRITE") != "1":
            return

        if flow.request.pretty_host.lower() != TARGET_HOST or not request_path.startswith(TARGET_PREFIX):
            print("OTA config host/path is outside the captured PID 2100 route; leaving response unchanged")
            return

        firmware_path = Path(os.environ.get("WAVEBUDS_FW_PATH", ""))
        version = os.environ.get("WAVEBUDS_VERSION", "")
        if not firmware_path.is_file() or not version:
            print("WAVEBUDS_REWRITE requires an existing WAVEBUDS_FW_PATH and WAVEBUDS_VERSION")
            return
        if not records:
            print(f"No firmware record for PID {TARGET_PID}; leaving response unchanged")
            return

        image = firmware_path.read_bytes()
        image_md5 = hashlib.md5(image).hexdigest()
        routes: list[tuple[tuple[str, str], tuple[Path, str]]] = []
        for record in records:
            key = _firmware_request_key(record.get("bin"), flow.request.pretty_url)
            if key is None:
                print("firmware.bin did not resolve to the captured appstorage route; leaving response unchanged")
                return
            routes.append((key, (firmware_path, image_md5)))

        # Keep firmware.bin intact: OTAUtil.getConfigUrl() constructs the URL from
        # the product's storage route and PID. Only the advertised version and MD5 change.
        for record in records:
            record["version"] = version
            record["md5"] = image_md5

        flow.response.set_text(json.dumps(document, ensure_ascii=False, separators=(",", ":")))
        for key, value in routes:
            self.firmware_paths[key] = value
        rewritten_path = CAPTURE_DIR / f"ota_config_{stamp}_rewritten.json"
        rewritten_path.write_text(flow.response.get_text(strict=False), encoding="utf-8")
        print(
            f"OTA config rewritten for PID {TARGET_PID}: version={version} md5={image_md5}; "
            f"firmware.bin preserved; local image={firmware_path} file={rewritten_path}"
        )

    def _serve_local_firmware(self, flow: http.HTTPFlow, request_path: str) -> None:
        if os.environ.get("WAVEBUDS_REWRITE") != "1" or flow.request.method.upper() != "GET":
            return
        key = (flow.request.pretty_host.lower(), request_path)
        target = self.firmware_paths.get(key)
        if target is None:
            return
        if "range" in flow.request.headers:
            print("Range firmware request detected; refusing local substitution")
            return

        firmware_path, expected_md5 = target
        try:
            image = firmware_path.read_bytes()
        except OSError as error:
            print(f"Cannot read local firmware image ({error}); leaving upstream response unchanged")
            return
        actual_md5 = hashlib.md5(image).hexdigest()
        if actual_md5 != expected_md5:
            print("Local firmware changed after config rewrite; refusing to serve it")
            return

        flow.response.status_code = 200
        for header in ("Content-Encoding", "Content-Range", "Accept-Ranges", "ETag", "Last-Modified", "Content-MD5", "Transfer-Encoding"):
            flow.response.headers.pop(header, None)
        flow.response.headers["Content-Type"] = "application/octet-stream"
        flow.response.set_content(image)
        print(
            f"Served local firmware: host={flow.request.pretty_host} path={request_path} "
            f"bytes={len(image)} md5={actual_md5}"
        )


addons = [WavebudsOTA()]
