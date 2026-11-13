# Third-party notices

## libmpv

The optional `runtime/libmpv-2.dll` compatibility backend is from the official Windows build produced by the `shinchiro/mpv-winbuild-cmake` project.

- Release: `20261103`
- Package: `mpv-dev-x86_64-20261103-git-a687796d9d.7z`
- Download: https://github.com/shinchiro/mpv-winbuild-cmake/releases/download/20261103/mpv-dev-x86_64-20261103-git-a687796d9d.7z
- Package SHA-256: `41cbfda596aaf1dc30053679bcd22828afaeec411340de6bf4c0e786fed1480b`
- `libmpv-2.dll` SHA-256: `B7E85132A1383540B190CBC166E5EAACD00C9163DA5F3A745292670E801DF819`
- mpv source: https://github.com/mpv-player/mpv/tree/a687796d9d
- Build recipes: https://github.com/shinchiro/mpv-winbuild-cmake

The DLL includes mpv, FFmpeg, dav1d and their dependencies. mpv is distributed under GNU GPL v2 or later in this build. The client API headers use the ISC license. The upstream copyright and GPL texts are included in `runtime/`. Component source code and build instructions are available through the linked projects.

## Vulkan Loader

`runtime/vulkan-1.dll` is the 64-bit Vulkan Runtime loader distributed with the locally installed Google Chrome 156.0.8078.79 (loader version 1.4.364.0). libmpv imports this loader even when its D3D11 renderer is selected. The loader does not add Vulkan hardware support or perform software Vulkan rendering in this player.

- Runtime source: https://github.com/KhronosGroup/Vulkan-Loader
- License: Apache License 2.0; included as `runtime/vulkan-LICENSE.txt`.
- DLL SHA-256: `7CDF5782871F20413CF14623C52069244401C0A69A891CD155E81D1F77FF0D6A`

The player itself does not load libmpv for files supported by the Windows backend. No part of VLC is used.
