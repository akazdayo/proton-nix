from unittest import TestCase

from scripts.steam_manifest import rewrite_tool


class SteamManifestTest(TestCase):
    def test_preserves_fields_and_comments(self):
        for version in ("GE-Proton11-14", "GE-Proton11-15"):
            for space in (" ", "\r\n"):
                with self.subTest(version=version, space=space):
                    manifest = (
                        f'\ufeff"compatibilitytools" {{{space}"compat_tools"{space}{{{space}"{{tool_id}}" {{\r\n'
                        f'    // "{version}" is the upstream ID\r\n'
                        '    "install_path" "." "display_name" "{name}"\r\n'
                        '}}}\r\n'
                    )
                    original = manifest.replace("{tool_id}", version).replace("{name}", version)
                    expected = manifest.replace("{tool_id}", "proton-ge-bin").replace("{name}", "GE-Proton")
                    self.assertEqual(rewrite_tool(original, "proton-ge-bin", "GE-Proton"), expected)

    def test_rejects_missing_install_path(self):
        original = '"compatibilitytools" { "compat_tools" { "Proton-2" { "display_name" "install_path" } } }'
        with self.assertRaisesRegex(ValueError, "exactly one install_path"):
            rewrite_tool(original, "proton-bin", "Proton")

    def test_rejects_ambiguous_display_name(self):
        original = '"compatibilitytools" { "compat_tools" { "v1" {"install_path" "." "display_name" "A" "display_name" "B"} } }'
        with self.assertRaisesRegex(ValueError, "exactly one display_name"):
            rewrite_tool(original, "proton-bin", "Proton")

    def test_rejects_multiple_tools(self):
        original = '"compatibilitytools" { "compat_tools" { "v1" {"install_path" "."} "v2" {"install_path" "."} } }'
        with self.assertRaisesRegex(ValueError, "Expected one Steam compatibility tool"):
            rewrite_tool(original, "proton-bin", "Proton")
