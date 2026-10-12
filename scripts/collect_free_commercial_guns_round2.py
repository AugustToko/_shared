#!/usr/bin/env python3
"""第二轮下载免费商用枪械、配件与机械分件，并生成私人归档清单。"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests

ROOT = Path(os.environ.get("OUTPUT_DIR", "bundle-round2")).resolve()
DOWNLOADS = ROOT / "packages"
DOWNLOADS.mkdir(parents=True, exist_ok=True)
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0 Chrome/153 Safari/537.36"})

# 只收录页面明确允许商业使用的来源。禁止再销售／再分发源文件的条款不影响当前用户私人归档，
# 但会写入许可证字段，后续交付游戏时仍需遵守。
ITCH_SOURCES = [
    {
        "id": "ggbot-untextured-3d-weapons",
        "url": "https://ggbot.itch.io/untextured-3d-weapons",
        "license": "CC0-1.0",
        "scope": "突击步枪、狙击步枪、冲锋枪；Blend、FBX、OBJ",
        "mountEvidence": "STATIC_MODELS",
    },
    {
        "id": "chilly-low-poly-firearms",
        "url": "https://chilly-durango.itch.io/low-poly-firearms",
        "license": "CC0-1.0",
        "scope": "16 把枪；滑套、扳机、转轮、泵、弹匣等机械件分离",
        "mountEvidence": "SEPARATE_MECHANICAL_PARTS",
    },
    {
        "id": "gintoki-12-low-poly-guns",
        "url": "https://gintoki1234.itch.io/12-low-poly-guns",
        "license": "CC0-1.0",
        "scope": "12 把枪与 3 个弹丸；弹匣和扳机等部件分离",
        "mountEvidence": "SEPARATE_MECHANICAL_PARTS",
    },
    {
        "id": "zsky-low-poly-weapons-v1",
        "url": "https://zsky2000.itch.io/low-poly-weapons-pack-v1",
        "license": "CC-BY-4.0",
        "scope": "20+ 低多边形枪械，商业使用需署名",
        "mountEvidence": "STATIC_MODELS",
    },
    {
        "id": "verzatile-assault-rifle-mark1",
        "url": "https://verzatiledev.itch.io/assault-rifle",
        "license": "CC0-1.0",
        "scope": "突击步枪与可拆弹匣，FBX",
        "mountEvidence": "DETACHABLE_MAGAZINE",
    },
    {
        "id": "three-d-models-cc0-guns-explosives",
        "url": "https://3dmodelscc0.itch.io/free-cc0-guns-explosives-pack",
        "license": "CC0-1.0",
        "scope": "19 个枪械与爆炸物模型",
        "mountEvidence": "STATIC_MODELS",
    },
    {
        "id": "plewr-psx-m4a1",
        "url": "https://plewr.itch.io/psx-style-m4a1-model",
        "license": "CC0-1.0",
        "scope": "PSX 风 M4A1，GLB",
        "mountEvidence": "STATIC_MODEL",
    },
    {
        "id": "plewr-psx-ak47",
        "url": "https://plewr.itch.io/psx-style-ak-47-model",
        "license": "CC0-1.0",
        "scope": "PSX 风 AK-47，GLB",
        "mountEvidence": "STATIC_MODEL",
    },
    {
        "id": "plewr-psx-mp5",
        "url": "https://plewr.itch.io/psx-style-mp5-model",
        "license": "CC0-1.0",
        "scope": "PSX 风 MP5，GLB",
        "mountEvidence": "STATIC_MODEL",
    },
    {
        "id": "nekis-ak12-mod-pack",
        "url": "https://nekis5-3d.itch.io/free-ak-12-weapon-mod-pack-3d-attachments-rifle-model",
        "license": "FREE_COMMERCIAL_NO_RAW_REDISTRIBUTION",
        "scope": "AK-12、弹匣、枪口、瞄具、握把和导轨配件",
        "mountEvidence": "MODULAR_ATTACHMENTS",
    },
    {
        "id": "rgs-weapons-pack-low-poly",
        "url": "https://rgsdev.itch.io/weapons-pack-low-poly",
        "license": "FREE_COMMERCIAL_NO_RAW_REDISTRIBUTION",
        "scope": "10 把枪、14 个附件、13 个爆炸物、弹药与补给件",
        "mountEvidence": "SEPARATE_PARTS_AND_ATTACHMENTS",
    },
    {
        "id": "ankers-wild-west-guns",
        "url": "https://ankersassets.itch.io/low-poly-guns",
        "license": "CC0-1.0",
        "scope": "6 把西部枪械、弹药与骨骼绑定",
        "mountEvidence": "RIGGED_MECHANICS",
    },
    {
        "id": "maxorbie-psx-guns",
        "url": "https://maxorbie.itch.io/psx-style-low-poly-guns-asset-pack",
        "license": "CC0-1.0",
        "scope": "9 把 PSX 低多边形枪械",
        "mountEvidence": "STATIC_MODELS",
    },
    {
        "id": "kalnir-16-low-poly-guns",
        "url": "https://kalinr-old.itch.io/16-low-poly-guns",
        "license": "CC-BY-4.0",
        "scope": "16 把枪；各枪部件已绑定，适合换弹与机械动画",
        "mountEvidence": "RIGGED_MECHANICS",
    },
    {
        "id": "bibbers-scifi-weapons",
        "url": "https://bibbers.itch.io/scifi-weapons-pack-low-poly-free",
        "license": "FREE_COMMERCIAL_NO_RAW_REDISTRIBUTION",
        "scope": "科幻步枪、手枪、刀和手雷",
        "mountEvidence": "STATIC_MODELS",
    },
    {
        "id": "delthor-m4-variants",
        "url": "https://delthor-games.itch.io/weapons-pack-vol-2",
        "license": "FREE_COMMERCIAL_NO_RAW_REDISTRIBUTION",
        "scope": "4 个 M4 变体；弹匣、瞄具和镜等部件可拆",
        "mountEvidence": "DETACHABLE_PARTS_AND_ATTACHMENTS",
    },
    {
        "id": "jaks-low-poly-rifle-pack",
        "url": "https://jaks.itch.io/low-poly-rifle-pack",
        "license": "CC-BY-4.0",
        "scope": "10 把低面数步枪",
        "mountEvidence": "STATIC_MODELS",
    },
]

OGA_SOURCES = [
    ("oga-realy-low-poly-gun", "https://opengameart.org/content/realy-low-poly-gun-cc0", "CC0-1.0", "Blend 与 FBX", None, "STATIC_MODEL"),
    ("oga-lightning-pump-action", "https://opengameart.org/content/lightning-pump-action-rifle", "CC0-1.0", "泵动与扳机动画，Blend 与 GLB", None, "RIGGED_MECHANICS"),
    ("oga-revolver-game-asset", "https://opengameart.org/content/revolver-game-asset", "CC0-1.0", "射击、换弹和弹药，FBX、Blend、Godot、Unity", None, "ANIMATED_MECHANICS"),
    ("oga-smg-10", "https://opengameart.org/content/smg-10-3d", "CC0-1.0", "SMG，Blend 与 OBJ", None, "STATIC_MODEL"),
    ("oga-low-poly-m4a1", "https://opengameart.org/content/low-poly-m4a1", "CC0-1.0", "M4A1，独立弹匣，Blend 与 FBX", None, "DETACHABLE_MAGAZINE"),
    ("oga-lowpoly-pistol", "https://opengameart.org/content/lowpoly-pistol", "CC0-1.0", "枪管、满／空弹匣、击锤、扳机、滑套分离", None, "SEPARATE_MECHANICAL_PARTS"),
    ("oga-emg-01a", "https://opengameart.org/content/emg-01a-low-poly-sci-fi-rifle", "CC0-1.0", "科幻步枪，可拆反射瞄具", None, "DETACHABLE_OPTIC"),
    ("oga-n64-fantasy-guns", "https://opengameart.org/content/n64-style-fantasy-guns-weapons-and-items", "CC0-1.0", "N64 风枪械与武器合集", None, "STATIC_MODELS"),
    ("oga-flamethrower-pbr", "https://opengameart.org/content/flamethrower-pbrunity-cc0", "CC0-1.0", "PBR 火焰喷射器，FBX 与 Blend", [r"Flamethrower\.zip$"], "STATIC_MODEL"),
    ("oga-energy-rifle", "https://opengameart.org/content/energy-rifle", "CC0-1.0", "绑定并带动画的能量步枪 FBX", None, "RIGGED_MECHANICS"),
    ("oga-low-poly-pistol-shell", "https://opengameart.org/content/3d-low-poly-pistol-with-bullet-shell", "CC0-1.0", "枪架、扳机和弹壳分离，FBX 与 Blend", None, "SEPARATE_MECHANICAL_PARTS"),
    ("oga-benelli-m1", "https://opengameart.org/content/benelli-m1", "CC0-1.0", "可编辑 Blend 霰弹枪", None, "STATIC_MODEL"),
    ("oga-sci-fi-rifle", "https://opengameart.org/content/sci-fi-rifle", "CC0-1.0", "科幻步枪与完整独立弹匣", None, "DETACHABLE_MAGAZINE"),
    ("oga-kenney-weapon-pack", "https://opengameart.org/content/weapon-pack", "CC0-1.0", "Kenney 30 种武器、弹壳和渲染图", None, "STATIC_MODELS"),
    ("oga-low-poly-stylized-sniper", "https://opengameart.org/content/low-poly-stylized-sniper", "CC0-1.0", "弹匣、上机匣、瞄具、消音器与弹夹分离", None, "SEPARATE_PARTS_AND_ATTACHMENTS"),
    ("oga-silencer", "https://opengameart.org/content/silencer", "CC0-1.0", "独立消音器 Blend", None, "ATTACHMENT"),
    ("oga-semi-auto-shotgun", "https://opengameart.org/content/semi-auto-shotgun-with-magazine", "CC0-1.0_MODEL_ONLY", "半自动弹匣霰弹枪；只收模型包，不收带署名声音的资源包", [r"myShotgun\.zip$"], "DETACHABLE_MAGAZINE"),
    ("oga-two-pistols", "https://opengameart.org/content/two-pistols", "CC0-1.0", "普通与消音手枪 Blend", None, "DETACHABLE_SUPPRESSOR_VARIANT"),
    ("oga-micro-uzi", "https://opengameart.org/content/micro-uzi-untextured", "CC0-1.0", "独立消音器的 Micro Uzi", [r"uzi\.blend$"], "DETACHABLE_SUPPRESSOR"),
    ("oga-simple-handgun", "https://opengameart.org/content/simple-handgun", "CC0-1.0", "简单手枪 Blend", None, "STATIC_MODEL"),
    ("oga-double-barrel-shotgun", "https://opengameart.org/content/double-barrel-shotgun", "CC0-1.0", "双管霰弹枪、贴图与高低模", None, "STATIC_MODEL"),
    ("oga-gun-part-1-free", "https://opengameart.org/content/3d-gun-part-1-free-version", "CC0-1.0", "GLTF、FBX 与 Blend", None, "STATIC_MODEL"),
]

ALLOWED_EXTENSIONS = {".zip", ".7z", ".rar", ".blend", ".fbx", ".glb", ".gltf", ".obj", ".dae"}


def request(method: str, url: str, **kwargs: object) -> requests.Response:
    last: Exception | None = None
    for attempt in range(6):
        try:
            response = SESSION.request(method, url, timeout=180, **kwargs)
            response.raise_for_status()
            return response
        except Exception as error:  # noqa: BLE001
            last = error
            time.sleep(min(2**attempt, 12))
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
        window = text[match.start() : match.start() + 5000]
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


def download_itch(source: dict[str, str]) -> dict[str, object]:
    source_id = source["id"]
    game_url = source["url"].rstrip("/")
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
    return {**source, "files": files, "status": "ARCHIVED", "privateArchiveOnly": True}


def oga_links(page_url: str, text: str, include_patterns: list[str] | None) -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    seen: set[str] = set()
    for raw in re.findall(r'href=["\']([^"\']+)["\']', text, re.I):
        url = urljoin(page_url, html.unescape(raw))
        parsed = urlparse(url)
        name = unquote(Path(parsed.path).name)
        if Path(name).suffix.lower() not in ALLOWED_EXTENSIONS:
            continue
        if "sites/default/files" not in parsed.path:
            continue
        if include_patterns and not any(re.search(pattern, name, re.I) for pattern in include_patterns):
            continue
        if url in seen:
            continue
        seen.add(url)
        links.append((url, safe_name(name)))
    return links


def download_oga(source: tuple[str, str, str, str, list[str] | None, str]) -> dict[str, object]:
    source_id, page_url, license_name, scope, include_patterns, mount_evidence = source
    page = request("GET", page_url)
    links = oga_links(page_url, page.text, include_patterns)
    if not links:
        raise RuntimeError(f"未解析到 OpenGameArt 模型文件：{page_url}")
    files = []
    for url, name in links:
        destination = DOWNLOADS / source_id / name
        stream_download(url, destination, page_url)
        files.append(file_record(destination, downloadUrl=url))
    return {
        "id": source_id,
        "url": page_url,
        "license": license_name,
        "scope": scope,
        "mountEvidence": mount_evidence,
        "files": files,
        "status": "ARCHIVED",
        "privateArchiveOnly": True,
    }


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    results: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []
    for source in ITCH_SOURCES:
        print(f"下载 itch：{source['id']}", flush=True)
        try:
            results.append(download_itch(source))
        except Exception as error:  # noqa: BLE001
            failures.append({"id": source["id"], "error": str(error)})
            print(f"失败：{source['id']}: {error}", file=sys.stderr, flush=True)
    for source in OGA_SOURCES:
        print(f"下载 OpenGameArt：{source[0]}", flush=True)
        try:
            results.append(download_oga(source))
        except Exception as error:  # noqa: BLE001
            failures.append({"id": source[0], "error": str(error)})
            print(f"失败：{source[0]}: {error}", file=sys.stderr, flush=True)

    mount_counts: dict[str, int] = {}
    for item in results:
        key = str(item.get("mountEvidence", "UNKNOWN"))
        mount_counts[key] = mount_counts.get(key, 0) + 1
    manifest = {
        "schemaVersion": 2,
        "kind": "MASAMUNE_PRIVATE_FREE_COMMERCIAL_GUN_SOURCE_ARCHIVE_ROUND2",
        "generatedAtUtc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "archivedSources": results,
        "failures": failures,
        "mountEvidenceSummary": mount_counts,
        "policy": {
            "privateArchiveOnly": True,
            "commercialUseEvidenceRequired": True,
            "rawRedistributionNotGrantedUnlessLicenseSaysSo": True,
            "mountReadyRequiresInspection": True,
            "noRuntimeIntegrationClaim": True,
        },
    }
    write_json(ROOT / "archive-manifest.json", manifest)
    (ROOT / "README_FIRST.md").write_text(
        "# Masamune 私人免费商用枪械源归档 · 第二轮\n\n"
        "本目录是当前用户私人 Google Drive 的源素材备份；免费商用不等于允许公开转售或重新分发。\n"
        "`mountEvidence` 仅描述来源结构，进入 Masamune 前仍需 AssetStudio 检查比例、坐标系、骨骼、插槽和许可证。\n",
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
            "failureIds": [item["id"] for item in failures],
            "mountEvidenceSummary": mount_counts,
            "privateArchiveOnly": True,
            "runtimeIntegrated": False,
            "releaseReady": False,
        },
    )
    print(json.dumps({"sources": len(results), "files": sum(len(item["files"]) for item in results), "failures": failures}, ensure_ascii=False))


if __name__ == "__main__":
    main()
