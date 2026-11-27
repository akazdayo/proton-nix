# proton-nix

Add this to your NixOS `flake.nix`:

```nix
inputs.proton-nix.url = "github:akazdayo/proton-nix";
```

Pass `specialArgs = { inherit inputs; };` to `nixosSystem`, then select the packages in your NixOS module:

```nix
{ inputs, pkgs, ... }:
let
  proton = inputs.proton-nix.packages.${pkgs.stdenv.hostPlatform.system};
in
{
  programs.steam = {
    enable = true;
    extraCompatPackages = [
      proton.proton-ge-bin
      proton.proton-cachyos-bin
    ];
  };
}
```
