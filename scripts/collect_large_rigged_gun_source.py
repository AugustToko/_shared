#!/usr/bin/env python3
"""下载一个大型免费商用枪械来源，并切分为适合 Drive 中转的分片。"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import tarfile
import time
from pathlib import Path

import requests

SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/155 Safari/537.36",
    }
)


def retry_request(method: str, url: str, **kwargs: object) -> requests.Response:
    last_error: Exception | None = None
    for attempt in range(6):
        try:
            response = SESSION.request(method, url, timeout=180, **kwargs)
            response.raise_for_status()
            return response
        except Exception as error:  # noqa: BLE001
            last_error = error
            time.sleep(min(2**attempt, 16))
    raise RuntimeError(f"请求失败：{url}: {last_error}")


def parse_csrf(text: str) -> str | None:
    patterns = (
        r'<meta[^>]+name=["\']csrf_token["\'][^>]+value=["\']([^"\']+)',
        r'<meta[^>]+value=["\']([^"\']+)["\'][^>]+name=["\']csrf_token["\']',
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return html.unescape(match.group(1))
    return None


def parse_uploads(text: str) -> list[dict[str, str]]:
    uploads: list[dict[str, str]] = []
    seen: set[str] = set()
    for match in re.finditer(r'data-upload_id=["\'](\d+)["\']', text, re.I):
        upload_id = match.group(1)
        if upload_id in seen:
            continue
        window = text[match.start() : match.start() + 5000]
        name_match = re.search(
            r'<strong[^>]*class=["\'][^"\']*\bname\b[^"\']*["\'][^>]*>([^<]+)</strong>',
            window,
            re.I | re.S,
        )
        name = html.unescape(name_match.group(1).strip()) if name_match else f"game-{upload_id}.zip"
        uploads.append({"id": upload_id, "name": name})
        seen.add(upload_id)
    return uploads


def safe_name(value: str) -> str:
    return value.replace("/", "_").replace("\\", "_").replace("\x00", "").strip() or "source.zip"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stream_download(url: str, destination: Path, referer: str | None = None) -> None:
    headers = {"Referer": referer} if referer else None
    destination.parent.mkdir(parents=True, exist_ok=True)
    with retry_request("GET", url, headers=headers, stream=True) as response:
        with destination.open("wb") as output:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    output.write(chunk)
    if destination.stat().st_size <= 0:
        raise RuntimeError(f"下载结果为空：{destination}")


def download_itch(config: dict[str, object], source_root: Path) -> Path:
    page_url = str(config["url"]).rstrip("/")
    page = retry_request("GET", page_url)
    (source_root / "source-page.html").write_text(page.text, encoding="utf-8")
    csrf = parse_csrf(page.text)
    uploads = parse_uploads(page.text)
    if not csrf:
        raise RuntimeError("缺少 itch CSRF")
    request_body: dict[str, str] = {"csrf_token": csrf}
    if uploads:
        request_body["upload_id"] = uploads[0]["id"]
    redirect = retry_request(
        "POST",
        page_url + "/download_url",
        data=request_body,
        headers={"X-Requested-With": "XMLHttpRequest", "Referer": page_url},
    )
    download_page_url = str(redirect.json()["url"])
    download_page = retry_request("GET", download_page_url)
    csrf2 = parse_csrf(download_page.text) or csrf
    page_uploads = parse_uploads(download_page.text)
    if page_uploads:
        uploads = page_uploads

    include = re.compile(str(config["includePattern"]), re.I)
    selected = [upload for upload in uploads if include.search(upload["name"])]
    if len(selected) != 1:
        raise RuntimeError(f"下载项匹配数量不是 1：{[item['name'] for item in selected]}; 全部={uploads}")
    upload = selected[0]
    file_response = retry_request(
        "POST",
        f"{page_url}/file/{upload['id']}",
        data={"csrf_token": csrf2},
        headers={"X-Requested-With": "XMLHttpRequest", "Referer": download_page_url},
    )
    source_path = source_root / safe_name(upload["name"])
    stream_download(str(file_response.json()["url"]), source_path, download_page_url)
    return source_path


def split_file(source: Path, parts_root: Path, part_bytes: int) -> list[Path]:
    parts_root.mkdir(parents=True, exist_ok=True)
    parts: list[Path] = []
    with source.open("rb") as input_stream:
        index = 0
        while True:
            chunk = input_stream.read(part_bytes)
            if not chunk:
                break
            part = parts_root / f"{source.name}.part-{index:03d}"
            part.write_bytes(chunk)
            parts.append(part)
            index += 1
    return parts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--part-bytes", type=int, default=75_000_000)
    args = parser.parse_args()

    config_path = Path(args.config)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    source_id = str(config["id"])
    output_root = Path(args.output).resolve()
    source_root = output_root / "source"
    catalog_root = output_root / "catalog"
    parts_root = output_root / "parts"
    source_root.mkdir(parents=True, exist_ok=True)
    catalog_root.mkdir(parents=True, exist_ok=True)

    source_path = download_itch(config, source_root)
    source_sha = sha256_file(source_path)
    source_bytes = source_path.stat().st_size

    manifest = {
        "schemaVersion": 1,
        "kind": "MASAMUNE_PRIVATE_LARGE_GUN_SOURCE_ARCHIVE",
        "sourceId": source_id,
        "title": config["title"],
        "pageUrl": config["url"],
        "license": config["license"],
        "attribution": config.get("attribution"),
        "scope": config["scope"],
        "mountEvidence": config["mountEvidence"],
        "privateArchiveOnly": True,
        "releaseReady": False,
        "runtimeIntegrated": False,
        "sourceFile": {
            "name": source_path.name,
            "bytes": source_bytes,
            "sha256": source_sha,
        },
    }
    (source_root / "source-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    tar_path = output_root / f"{source_id}.tar"
    with tarfile.open(tar_path, mode="w") as archive:
        archive.add(source_root, arcname=source_id)
    tar_sha = sha256_file(tar_path)
    parts = split_file(tar_path, parts_root, args.part_bytes)

    part_records = [
        {
            "name": part.name,
            "bytes": part.stat().st_size,
            "sha256": sha256_file(part),
        }
        for part in parts
    ]
    transfer_manifest = {
        **manifest,
        "archive": {
            "name": tar_path.name,
            "bytes": tar_path.stat().st_size,
            "sha256": tar_sha,
            "partBytes": args.part_bytes,
            "parts": part_records,
        },
    }
    (catalog_root / "transfer-manifest.json").write_text(
        json.dumps(transfer_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (catalog_root / "REASSEMBLE.md").write_text(
        "\n".join(
            [
                f"# {config['title']} 私人归档重组说明",
                "",
                "把全部 `.part-XXX` 放在同一目录，然后执行：",
                "",
                "```bash",
                f"cat '{tar_path.name}.part-'* > '{tar_path.name}'",
                f"sha256sum '{tar_path.name}'",
                f"tar -xf '{tar_path.name}'",
                "```",
                "",
                f"目标 TAR SHA-256：`{tar_sha}`",
                f"原始来源 SHA-256：`{source_sha}`",
                "",
                "该归档只用于当前用户的私人生产工作区；尚未通过 Masamune 枪匠、像素烘焙或 GameScreen 验收。",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(transfer_manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
