from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from urllib.error import HTTPError

from scripts import update


class ReleaseUpdateTest(TestCase):
    homepage = "https://github.com/example/proton"
    older = "2026-11-01T12:00:00Z"
    newer = "2026-11-02T12:00:00Z"

    def release(self, tag, published_at, has_asset=True):
        return {
            "tag_name": tag,
            "published_at": published_at,
            "assets": [{
                "name": f"proton-{tag}-x86_64.tar.gz",
                "browser_download_url": f"{self.homepage}/releases/download/{tag}/proton-{tag}-x86_64.tar.gz",
                "digest": "sha256:" + "01" * 32,
            }] if has_asset else [],
        }

    def refresh(self, old_tag, releases, published_at=None):
        asset = {"url": f"{self.homepage}/releases/download/{old_tag}/previous.tar.gz", "hash": "old-hash"}
        if published_at:
            asset["publishedAt"] = published_at
        previous = {
            "example-bin": {
                "homepage": self.homepage,
                "versions": {update.X86: old_tag},
                "assets": {update.X86: asset},
            },
        }
        sources = [(self.homepage, {"example-bin": {update.X86: r"proton-.+-x86_64\.tar\.gz"}})]
        with TemporaryDirectory() as directory:
            manifest = Path(directory) / "releases.json"
            manifest.write_text(json.dumps(previous))
            with (
                patch.object(update, "MANIFEST", manifest),
                patch.object(update, "SOURCES", sources),
                patch.object(update, "release_list", return_value=releases),
                redirect_stdout(StringIO()),
            ):
                update.main()
            return previous["example-bin"], json.loads(manifest.read_text())["example-bin"]

    def test_keeps_pin_when_newest_asset_is_removed(self):
        releases = [self.release("v2", self.newer, has_asset=False), self.release("v1", self.older)]
        for published_at in (None, self.newer):
            with self.subTest(published_at=published_at):
                previous, updated = self.refresh("v2", releases, published_at)
                previous["assets"][update.X86]["publishedAt"] = self.newer
                self.assertEqual(updated, previous)

    def test_keeps_pin_when_release_disappears_from_api(self):
        for published_at in (None, self.newer):
            with self.subTest(published_at=published_at):
                previous, updated = self.refresh("v2", [self.release("v1", self.older)], published_at)
                self.assertEqual(updated, previous)

    def test_moves_legacy_pin_to_newer_release(self):
        releases = [self.release("v2", self.newer), self.release("v1", self.older)]
        _, updated = self.refresh("v1", releases)
        self.assertEqual(updated["versions"][update.X86], "v2")
        self.assertEqual(updated["assets"][update.X86]["publishedAt"], self.newer)

    def test_moves_to_newer_release_when_pinned_tag_is_unlisted(self):
        _, updated = self.refresh("v1", [self.release("v2", self.newer)], self.older)
        self.assertEqual(updated["versions"][update.X86], "v2")

    def test_continues_after_upstream_outage(self):
        down = "https://github.com/example/unavailable"
        variants = {update.X86: r"proton-.+-x86_64\.tar\.gz"}
        sources = [(down, {"unavailable-bin": variants}), (self.homepage, {"example-bin": variants})]
        old_pin = {
            "homepage": down,
            "versions": {update.X86: "v1"},
            "assets": {update.X86: {"url": f"{down}/releases/download/v1/proton-v1.tar.gz", "hash": "old-hash"}},
        }
        error = HTTPError(down, 503, "Unavailable", {}, None)
        log = StringIO()
        with TemporaryDirectory() as directory:
            manifest = Path(directory) / "releases.json"
            manifest.write_text(json.dumps({"unavailable-bin": old_pin}))
            with (
                patch.object(update, "MANIFEST", manifest),
                patch.object(update, "SOURCES", sources),
                patch.object(update, "release_list", side_effect=[error, [self.release("v2", self.newer)]]),
                redirect_stderr(log),
                redirect_stdout(StringIO()),
            ):
                update.main()
            updated = json.loads(manifest.read_text())
        self.assertEqual(updated["unavailable-bin"], old_pin)
        self.assertEqual(updated["example-bin"]["versions"][update.X86], "v2")
        self.assertIn(f"{down}: update failed", log.getvalue())
