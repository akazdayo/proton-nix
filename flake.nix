{
  description = "Upstream Proton binaries for NixOS Steam";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { nixpkgs, ... }: {
    packages = nixpkgs.lib.genAttrs [ "x86_64-linux" "aarch64-linux" ] (
      system: import ./packages.nix { pkgs = nixpkgs.legacyPackages.${system}; }
    );
  };
}
