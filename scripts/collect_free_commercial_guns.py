#!/usr/bin/env python3
"""下载免费商用枪械素材，并生成可审计的私人归档。"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(os.environ.get("OUTPUT_DIR", "bundle")).resolve()
DOWNLOADS = ROOT / "packages"
DOWNLOADS.mkdir(parents=True, exist_ok=True)
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0 Chrome/153 Safari/537.36"})

ITCH_SOURCES = [
    ("stein-classic-weapons", "https://stein-indie.itch.io/classic-weapons-pack", "CC0-1.0", "8 个经典枪械，FBX 与 PBR 纹理"),
    ("polyyai-low-poly-guns", "https://polyyai.itch.io/3d-low-poly-guns-pack", "CC0-1.0", "25 个枪械，普通版与低面数 LOD 版"),
    ("kenney-blaster-kit", "https://kenney-assets.itch.io/blaster-kit", "CC0-1.0", "低多边形能量武器、弹匣、弹丸与道具"),
    ("mehrasaur-3d-weapons", "https://mehrasaur.itch.io/weapons-3d", "CC0-1.0", "低多边形枪械，Blend 与 OBJ"),
    ("texnist-voxel-weapons", "https://technistguru.itch.io/voxel-weapons", "CC0-1.0", "体素手枪、步枪与狙击枪，FBX 与 VOX"),
    ("peu-blasters-free", "https://pedrovilasboas.itch.io/peu-game-assets-blasters", "CC0-1.0", "模块化科幻手枪免费样例"),
    ("cosmo-low-poly-guns", "https://cosmo-art.itch.io/low-poly-guns", "CC0-1.0", "29 个可改色低多边形枪械，FBX 与 OBJ"),
    ("dark-palette-weapon-arsenal", "https://dark-palette.itch.io/lowpoly-weapon-arsenal", "FREE_COMMERCIAL_PAGE_TERMS", "机械部件已拆分，可推导枪口、弹匣、拉机柄与泵动件"),
    ("retro-spud-pixel-arsenal", "https://retro-spud.itch.io/pixel-arsenal-free-sampler", "PIXEL_ARSENAL_ASSET_LICENSE_1.0", "2 个模块化枪族、21 个零件与作者原生 socket_*"),
    ("heyheythere-psx-firearms-free", "https://heyheythere.itch.io/psx-firearms-free", "CC-BY-4.0", "带滑套、弹匣与泵动动画的 PSX 枪械样例"),
    ("heyheythere-psx-fps-arms-free", "https://heyheythere.itch.io/psx-fps-arms-free", "CC-BY-4.0", "第一人称手臂、手枪与换弹动画样例"),
    ("lazy-spar7an-psx-gun-pack", "https://lazyspar7an.itch.io/sci-fi-low-poly-gun-pack-v1", "FREE_COMMERCIAL_PAGE_TERMS", "3 个 PSX 科幻枪械，弹匣独立"),
]

STATIC_SOURCES = [
    ("opengameart-oldschool-afps", "https://opengameart.org/content/oldschool-afps-weapons", "https://opengameart.org/sites/default/files/afps_weapons.zip", "afps_weapons.zip", "CC0-1.0", "9 个复古竞技场射击武器"),
    ("opengameart-soviet-assault-rifle", "https://opengameart.org/content/ak-47-3d", "https://opengameart.org/sites/default/files/soviet_assault_rifle_3d.zip", "soviet_assault_rifle_3d.zip", "CC0-1.0", "低面数突击步枪，FBX、OBJ 与 Blend"),
    ("opengameart-vss", "https://opengameart.org/content/vss-vintorez-3d", "https://opengameart.org/sites/default/files/soviet_special_sniper_rifle_3d.zip", "soviet_special_sniper_rifle_3d.zip", "CC0-1.0", "低面数特种狙击步枪，FBX、OBJ 与 Blend"),
]

EXCLUDED_SOURCES = [
    {
        "id": "alstra-shooter-essentials",
        "url": "https://alstrainfinite.itch.io/pps-shooter-essentials",
        "reason": "许可证明确禁止将源资产上传至文件共享服务；保留来源卡和挂点证据，不归档原包。",
        "mountEvidence": ["Socket_Magwell", "Socket_Foregrip", "Socket_Optic", "Socket_Barrel", "Socket_Handle"],
    },
    {
        "id": "sketchfab-modular-candidates",
        "url": "https://sketchfab.com/search?features=downloadable&q=modular+gun&type=models",
        "reason": "下载接口需要账户授权；不绕过登录，保留人工下载队列。",
    },
]


def request(method: str, url: str, **kwargs: object) -> requests.Response:
    last: Exception | None = None
    for attempt in range(5):
        try:
            response = SESSION.request(method, url, timeout=120, **kwargs)
            response.raise_for_status()
            return response
        except Exception as error:  # noqa: BLE001
            last = error
            time.sleep(min(2**attempt, 8))
    raise RuntimeError(f"请求失败：{url}: {last}")


def parse_csrf(text: str) -> str | None:
    for pattern in (
        r'<meta[^>]+name=["\']csrf_token["\'][^>]+value=["\']([^"\']+)',
        r'<meta[^>]+value=["\']([^"\']+)["\'][^>]+name=["\']csrf_token["\']',
    ):
        match = re.search(pattern, text, re.I)
        if match:
            return html.unescape(match.group(1))
    return None


def parse_uploads(text: str) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for match in re.finditer(r'data-upload_id=["\'](\d+)["\']', text, re.I):
        upload_id = match.group(1)
        if upload_id in seen:
            continue
        window = text[match.start() : match.start() + 3000]
        name_match = re.search(r'<strong[^>]*class=["\'][^"\']*\bname\b[^"\']*["\'][^>]*>([^<]+)</strong>', window, re.I | re.S)
        name = html.unescape(name_match.group(1).strip()) if name_match else f"game-{upload_id}.zip"
        result.append({"id": upload_id, "name": name})
        seen.add(upload_id)
    return result


def safe_name(value: str) -> str:
    return value.replace("/", "_").replace("\\", "_").replace("\x00", "").strip() or "download.bin"


def stream_download(url: str, destination: Path, referer: str | None = None) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    headers = {"Referer": referer} if referer else None
    with request("GET", url, headers=headers, stream=True) as response:
        with destination.open("wb") as output:
            for chunk in response.iter_content(1024 * 1024):
                if chunk:
                    output.write(chunk)
    if destination.stat().st_size <= 0:
        raise RuntimeError(f"下载得到空文件：{destination}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_record(path: Path, **extra: object) -> dict[str, object]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path), **extra}


def download_itch(source_id: str, game_url: str, license_name: str, scope: str) -> dict[str, object]:
    game_url = game_url.rstrip("/")
    page = request("GET", game_url)
    csrf = parse_csrf(page.text)
    uploads = parse_uploads(page.text)
    if not csrf:
        raise RuntimeError(f"缺少 itch CSRF：{game_url}")
    data: dict[str, str] = {"csrf_token": csrf}
    if uploads:
        data["upload_id"] = uploads[0]["id"]
    response = request("POST", game_url + "/download_url", data=data, headers={"X-Requested-With": "XMLHttpRequest", "Referer": game_url})
    download_page_url = response.json()["url"]
    download_page = request("GET", download_page_url)
    csrf2 = parse_csrf(download_page.text) or csrf
    uploads2 = parse_uploads(download_page.text)
    if uploads2:
        uploads = uploads2
    if not uploads:
        raise RuntimeError(f"页面没有可下载文件：{game_url}")
    files = []
    for upload in uploads:
        response = request(
            "POST",
            f"{game_url}/file/{upload['id']}",
            data={"csrf_token": csrf2},
            headers={"X-Requested-With": "XMLHttpRequest", "Referer": download_page_url},
        )
        destination = DOWNLOADS / source_id / safe_name(upload["name"])
        stream_download(response.json()["url"], destination, download_page_url)
        files.append(file_record(destination, uploadId=upload["id"]))
    return {"id": source_id, "url": game_url, "license": license_name, "scope": scope, "files": files, "status": "ARCHIVED"}


def download_static(source: tuple[str, str, str, str, str, str]) -> dict[str, object]:
    source_id, page, url, file_name, license_name, scope = source
    destination = DOWNLOADS / source_id / file_name
    stream_download(url, destination, page)
    return {"id": source_id, "url": page, "downloadUrl": url, "license": license_name, "scope": scope, "files": [file_record(destination)], "status": "ARCHIVED"}


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    results: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []
    for source in ITCH_SOURCES:
        print(f"下载 itch：{source[0]}", flush=True)
        try:
            results.append(download_itch(*source))
        except Exception as error:  # noqa: BLE001
            failures.append({"id": source[0], "error": str(error)})
            print(f"失败：{source[0]}: {error}", file=sys.stderr, flush=True)
    for source in STATIC_SOURCES:
        print(f"下载静态来源：{source[0]}", flush=True)
        try:
            results.append(download_static(source))
        except Exception as error:  # noqa: BLE001
            failures.append({"id": source[0], "error": str(error)})
            print(f"失败：{source[0]}: {error}", file=sys.stderr, flush=True)

    manifest = {
        "schemaVersion": 1,
        "kind": "MASAMUNE_PRIVATE_FREE_COMMERCIAL_GUN_SOURCE_ARCHIVE",
        "generatedAtUtc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "archivedSources": results,
        "excludedSources": EXCLUDED_SOURCES,
        "failures": failures,
        "policy": {
            "privateArchiveOnly": True,
            "commercialUseEvidenceRequired": True,
            "mountReadyRequiresInspection": True,
            "noRuntimeIntegrationClaim": True,
        },
    }
    write_json(ROOT / "archive-manifest.json", manifest)
    (ROOT / "README_FIRST.md").write_text(
        "# Masamune 私人免费商用枪械源归档\n\n"
        "仅用于当前用户的私人资产生产工作区。免费商用不等于已通过枪匠挂点验收。\n\n"
        "ALSTRA 原包因许可证明确禁止上传到文件共享服务而未收录；Sketchfab 需要账户授权，不绕过登录。\n",
        encoding="utf-8",
    )
    rows = []
    for path in sorted(ROOT.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS.txt":
            rows.append(f"{sha256(path)}  {path.relative_to(ROOT).as_posix()}")
    (ROOT / "SHA256SUMS.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")
    write_json(
        ROOT / "acceptance.json",
        {
            "status": "PASS" if not failures else "PASS_WITH_DOWNLOAD_FAILURES",
            "sourceCount": len(results),
            "fileCount": sum(len(item["files"]) for item in results),
            "failureCount": len(failures),
            "privateArchiveOnly": True,
            "runtimeIntegrated": False,
            "releaseReady": False,
        },
    )
    print(json.dumps({"sources": len(results), "files": sum(len(item["files"]) for item in results), "failures": failures}, ensure_ascii=False))


if __name__ == "__main__":
    main()
