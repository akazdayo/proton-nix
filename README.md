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

## Supported Proton builds

| Proton build | Nix package | Architecture |
| --- | --- | --- |
| GE-Proton | `proton-ge-bin` | x86_64, aarch64 |
| Proton-CachyOS | `proton-cachyos-bin` | x86_64, aarch64 |
| Proton-CachyOS v3 | `proton-cachyos-v3-bin` | x86_64-v3 |
| Proton-Wineland | `proton-wineland-bin` | x86_64 |
| Proton-Wineland v3 | `proton-wineland-v3-bin` | x86_64-v3 |
| Proton-Wineland WoW64 | `proton-wineland-wow64-bin` | x86_64 |
| Proton-EM | `proton-em-bin` | x86_64 |
| Proton-RTSP | `proton-rtsp-bin` | x86_64 |
| dwproton | `dwproton-bin` | x86_64 |
| Proton Tkg | `proton-tkg-bin` | x86_64 |
