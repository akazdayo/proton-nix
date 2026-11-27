from unittest import TestCase

from scripts.steam_manifest import rewrite_tool_id


class SteamManifestTest(TestCase):
    def test_preserves_fields_and_comments(self):
        for space in (" ", "\r\n"):
            with self.subTest(space=space):
                original = (
                    f'\ufeff"compatibilitytools" {{{space}"compat_tools"{space}{{{space}"Proton-2" {{\r\n'
                    '    // "Proton-2" is the upstream ID\r\n'
                    '    "install_path" "." "display_name" "Proton-2"\r\n'
                    '}}}\r\n'
                )
                self.assertEqual(rewrite_tool_id(original, "proton-bin"), original.replace('"Proton-2"', '"proton-bin"', 1))

    def test_rejects_missing_install_path(self):
        original = '"compatibilitytools" { "compat_tools" { "Proton-2" { "display_name" "install_path" } } }'
        with self.assertRaisesRegex(ValueError, "exactly one install_path"):
            rewrite_tool_id(original, "proton-bin")

    def test_rejects_multiple_tools(self):
        original = '"compatibilitytools" { "compat_tools" { "v1" {"install_path" "."} "v2" {"install_path" "."} } }'
        with self.assertRaisesRegex(ValueError, "Expected one Steam compatibility tool"):
            rewrite_tool_id(original, "proton-bin")
