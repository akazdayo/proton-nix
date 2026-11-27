"""Pin the latest upstream release assets that ProtonUp-Qt can install in Steam."""

import base64
from datetime import datetime
import hashlib
from http.client import HTTPException
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


MANIFEST = Path(__file__).resolve().parents[1] / "releases.json"
X86 = "x86_64-linux"
ARM = "aarch64-linux"
GITHUB = "https://github.com/"
DAWN = "https://dawn.wine/"

# Each pattern selects the Steam asset, rather than a distro package or source archive.
SOURCES = [
    (GITHUB + "GloriousEggroll/proton-ge-custom", {
        "proton-ge-bin": {
            X86: r"GE-Proton.+(?<!-aarch64)\.tar\.gz",
            ARM: r"GE-Proton.+-aarch64\.tar\.gz",
        },
    }),
    (GITHUB + "CachyOS/proton-cachyos", {
        "proton-cachyos-bin": {
            X86: r"proton-cachyos-.+-slr-x86_64\.tar\.xz",
            ARM: r"proton-cachyos-.+-slr-arm64\.tar\.xz",
        },
        "proton-cachyos-v3-bin": {X86: r"proton-cachyos-.+-slr-x86_64_v3\.tar\.xz"},
    }),
    (GITHUB + "nanomatters/proton-salkim", {
        "proton-wineland-bin": {X86: r"proton-wineland-.+-x86_64\.tar\.xz"},
        "proton-wineland-v3-bin": {X86: r"proton-wineland-.+-x86_64_v3\.tar\.xz"},
        "proton-wineland-wow64-bin": {X86: r"proton-wineland-.+-x86_64_wow64\.tar\.xz"},
    }),
    (GITHUB + "BananaWorks07/Proton", {
        "proton-em-bin": {X86: r"proton-EM-.+\.tar\.xz"},
    }),
    (GITHUB + "SpookySkeletons/proton-rtsp", {
        "proton-rtsp-bin": {X86: r"(proton-rtsp-|GE-Proton.+-rtsp).+\.tar\.gz"},
    }),
    (DAWN + "dawn-winery/dwproton", {
        "dwproton-bin": {X86: r"dwproton-.+-x86_64\.tar\.xz"},
    }),
    (GITHUB + "Frogging-Family/wine-tkg-git", {
        "proton-tkg-bin": {X86: r"proton_tkg_.+\.release\.tar\.(gz|xz)"},
    }),
]


def fetch(url):
    request = Request(url, headers={"User-Agent": "proton-nix"})
    token = os.environ.get("GH_TOKEN")
    if token and urlsplit(url).hostname == "api.github.com":
        # urllib does not forward unredirected headers to the download host.
        request.add_unredirected_header("Authorization", f"Bearer {token}")
    return urlopen(request, timeout=120)


def release_list(homepage):
    # shortcut: inspect one page; follow pagination if a supported variant falls off it.
    if homepage.startswith(GITHUB):
        endpoint = homepage.replace(GITHUB, "https://api.github.com/repos/", 1)
        query = "?per_page=100"
    else:
        endpoint = homepage.replace(DAWN, DAWN + "api/v1/repos/", 1)
        query = "?limit=50"
    with fetch(f"{endpoint}/releases{query}") as response:
        releases = json.load(response)
    return sorted(
        (r for r in releases if not r["draft"] and not r["prerelease"]),
        key=lambda r: datetime.fromisoformat(r["published_at"]),
        reverse=True,
    )


def select_asset(releases, pattern):
    for release in releases:
        matches = [a for a in release["assets"] if re.fullmatch(pattern, a["name"])]
        if len(matches) > 1:
            raise ValueError(f"Ambiguous assets for {pattern} in {release['tag_name']}")
        if matches:
            return release, matches[0]
    raise ValueError(f"No upstream release asset matched {pattern}")


def asset_pin(homepage, release, asset, previous):
    def official_url(item):
        url = item["browser_download_url"]
        if not url.casefold().startswith(f"{homepage}/releases/download/".casefold()):
            raise ValueError(f"Unexpected release asset URL: {url}")
        return url

    url = official_url(asset)
    digest = asset.get("digest")
    pin = {"url": url}
    if digest:
        algorithm, digest = digest.split(":", 1)
    else:
        stem = re.sub(r"\.tar\.(gz|xz)$", "", asset["name"])
        checksum = next(
            (a for a in release["assets"] if a["name"] in (f"{stem}.sha512sum", f"{asset['name']}.sha512sum")),
            None,
        )
        if checksum:
            algorithm = "sha512"
            with fetch(official_url(checksum)) as response:
                digest, filename = response.read(4096).decode().strip().split(maxsplit=1)
            if filename.lstrip("*") != asset["name"]:
                raise ValueError(f"Checksum does not identify {asset['name']}")
        else:
            # Older GitHub uploads have no digest; hash the official bytes on changes.
            pin["revision"] = f"{asset['id']}:{asset['updated_at']}"
            if all(previous.get(key) == value for key, value in pin.items()):
                return previous
            algorithm = "sha256"
            with fetch(url) as response:
                digest = hashlib.file_digest(response, algorithm).hexdigest()

    if algorithm not in ("sha256", "sha512") or not re.fullmatch(
        rf"[0-9a-fA-F]{{{hashlib.new(algorithm).digest_size * 2}}}", digest
    ):
        raise ValueError(f"Invalid checksum for {url}")
    pin["hash"] = f"{algorithm}-" + base64.b64encode(bytes.fromhex(digest)).decode()
    return pin


def update_source(homepage, packages, previous):
    releases = release_list(homepage)
    result = {}
    for name, variants in packages.items():
        old_release = previous.get(name, {})
        assets = {}
        versions = {}
        for system, pattern in variants.items():
            release, asset = select_asset(releases, pattern)
            old_asset = old_release.get("assets", {}).get(system, {})
            old_tag = old_release.get("versions", {}).get(system)
            old_date = old_asset.get("publishedAt")
            if old_tag and not old_date:
                old_date = next((r["published_at"] for r in releases if r["tag_name"] == old_tag), None)
            tag = release["tag_name"]
            published = release["published_at"]
            is_newer = old_date and datetime.fromisoformat(published) > datetime.fromisoformat(old_date)
            if old_tag and old_tag != tag and not is_newer:
                print(f"{name}.{system}: keeping {old_tag}; cannot confirm {tag} is newer", flush=True)
                assets[system] = {**old_asset, "publishedAt": old_date} if old_date else old_asset
                versions[system] = old_tag
                continue

            pin = asset_pin(homepage, release, asset, old_asset)
            assets[system] = {**pin, "publishedAt": published if is_newer or not old_date else old_date}
            versions[system] = tag
        result[name] = {"homepage": homepage, "versions": versions, "assets": assets}
    return result


def main():
    previous = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    manifest = {}
    successful = 0
    for homepage, packages in SOURCES:
        try:
            updated = update_source(homepage, packages, previous)
        except (OSError, HTTPException, ValueError, KeyError, TypeError) as error:
            print(f"{homepage}: update failed; keeping existing pins: {error}", file=sys.stderr, flush=True)
            manifest.update({name: previous[name] for name in packages if name in previous})
            continue
        manifest.update(updated)
        successful += 1
        for name, release in updated.items():
            for system, tag in release["versions"].items():
                print(f"{name}.{system}: {tag}", flush=True)

    if not successful:
        raise SystemExit("No upstream sources could be updated")

    with tempfile.NamedTemporaryFile(mode="w", dir=MANIFEST.parent, delete=False) as output:
        json.dump(manifest, output, indent=2, sort_keys=True)
        output.write("\n")
    os.chmod(output.name, 0o644)
    os.replace(output.name, MANIFEST)


if __name__ == "__main__":
    main()
