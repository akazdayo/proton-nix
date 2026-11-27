{ pkgs }:

let
  inherit (pkgs) lib stdenvNoCC;
  system = stdenvNoCC.hostPlatform.system;
  releases = lib.importJSON ./releases.json;
  available = lib.filterAttrs (_: release: release.assets ? ${system}) releases;
in
lib.mapAttrs (
  pname: release:
  let
    asset = release.assets.${system};
  in
  stdenvNoCC.mkDerivation {
    inherit pname;
    version = release.versions.${system};
    src = pkgs.fetchurl { inherit (asset) url hash; };

    outputs = [
      "out"
      "steamcompattool"
    ];
    dontConfigure = true;
    dontBuild = true;
    dontFixup = true;
    nativeBuildInputs = [ pkgs.buildPackages.python3 ];

    # Some upstream tarballs contain the tool at the archive root.
    unpackPhase = ''
      runHook preUnpack
      mkdir source
      tar -xf "$src" -C source
      runHook postUnpack
    '';

    installPhase = ''
      runHook preInstall
      mapfile -d "" manifests < <(find source -maxdepth 3 -type f -name compatibilitytool.vdf -print0)
      if [[ ''${#manifests[@]} != 1 || ! -x "$(dirname "''${manifests[0]}")/proton" ]]; then
        echo "Expected one Steam Proton tool in $src" >&2
        exit 1
      fi
      toolDir=$(dirname "''${manifests[0]}")

      # Steam stores this key per game, so it must survive upstream version changes.
      manifest="$toolDir/compatibilitytool.vdf"
      python3 ${./scripts/steam_manifest.py} "$manifest" "${pname}" > "$manifest.new"
      mv "$manifest.new" "$manifest"

      # SteamPipe repairs must run before the tool is moved into the read-only store.
      if [[ -f "$toolDir/steampipe_fixups.json" ]]; then
        python3 "$toolDir/steampipe_fixups.py" restore "$toolDir"
        rm "$toolDir/steampipe_fixups.json"
      fi

      # The prefix info includes the tool's store path; Wine itself only checks mtime.
      prefixChanged='            if old_ver != CURRENT_PREFIX_VERSION or old_prefix_info != prefix_info:'
      printf -v resetTimestamp '\n%s\n%s\n%s\n%s\n%s' \
        '                if old_ver is not None and (old_ver != CURRENT_PREFIX_VERSION or' \
        '                        g_proton.lib_dir not in old_prefix_info.splitlines()):' \
        '                    update_timestamp = self.prefix_dir + ".update-timestamp"' \
        '                    if os.path.lexists(update_timestamp):' \
        '                        os.remove(update_timestamp)'
      substituteInPlace "$toolDir/proton" \
        --replace-fail "$prefixChanged" "$prefixChanged$resetTimestamp"

      mv "$toolDir" "$steamcompattool"
      echo 'Use this package with programs.steam.extraCompatPackages.' > "$out"
      runHook postInstall
    '';

    meta = {
      inherit (release) homepage;
      description = "Upstream Proton binary for Steam";
      platforms = builtins.attrNames release.assets;
      sourceProvenance = [ lib.sourceTypes.binaryNativeCode ];
    };
  }
) available
