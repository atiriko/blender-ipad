# Personal Blender iPad port

This workspace contains the official experimental `ios` branch, based on Blender
5.1.2, checked out at `a1de44dd54af75a4c8c4a29a5fed2a1334a87446`.
It is a starting point for a native port, not a tested or finished iPad application.

## Build on a Mac

Use an Apple Silicon Mac for this initial workflow. Intel Macs require a separate
host-dependency setup and are not handled by the helper. Install full Xcode with
an iOS SDK that supports deployment/debugging on your iPadOS version. Launch Xcode
once to complete installation and add your Apple account under Settings → Accounts.
Install CMake, Git LFS, and Python 3; if you use Homebrew:

```sh
brew install cmake git-lfs python
```

Clone your fork on the Mac. Use a path without spaces because upstream host-tool
commands do not safely handle spaces. The build folder is created alongside the
source checkout as `../build_ios`.

```sh
GIT_LFS_SKIP_SMUDGE=1 git clone --branch personal-ipad --single-branch https://github.com/atiriko/blender-ipad.git ~/blender-ipad
```

```sh
cd ~/blender-ipad
python3 build_ipad.py setup
python3 build_ipad.py configure --bundle-id personal.yourname.blender
open ../build_ios/Blender.xcodeproj
```

`setup` configures the official Blender LFS server for upstream assets (the GitHub
mirror does not host them) and downloads both macOS and iOS dependencies at the
revisions recorded by this checkout. It does not update the Blender branch.
Expect substantial downloads and build disk usage.

In Xcode, select the `blender` target, open Signing & Capabilities, select your
team, and enable automatic signing. Alternatively pass `--team YOUR_TEAM_ID`
to the configure command. Use your own unique bundle identifier. Connect and
trust the iPad, enable Developer Mode if Xcode requests it, and select it as the
destination. Build the `install` scheme in Release to copy runtime scripts and
libraries; then select the `blender` scheme and run it on the device. The port
automatically builds native macOS code-generation tools while compiling.

For a terminal build after configuring signing:

```sh
python3 build_ipad.py build --jobs 4
```

Upstream's runtime-library installation selects the first available code-signing
identity. On a Mac with multiple identities, verify that the installed libraries
and app are signed for the intended team if deployment fails. This remains an
upstream limitation; this workspace has not been built on macOS yet.

The helper disables the increased-memory entitlement by default to allow a first
attempt with a personal signing team. If your provisioning profile supports it,
configure again with `--increased-memory` for the M5 device. Ordinary device
memory limits still apply without it. No Apple credentials are stored here.

## Device targets and validation

- M5 iPad Pro: first target, using Pencil and touch. Hardware, SDK, and runtime
  behavior still need verification on the actual device.
- iPad Air 3: secondary compatibility target. It has an A12 chip and supports
  first-generation Pencil. Apple's iPadOS 27 list excludes it; confirm its model
  and OS before choosing the final compatibility target. This source currently
  sets a minimum deployment target of iOS 16, but that does not guarantee GPU
  compatibility or sufficient memory on the Air.

Test on each device before calling this a working port:

1. Launch to the default cube; rotate the device and navigate the viewport.
2. Select and transform an object using touch/Pencil; exercise pinch and pan.
3. Sculpt a small mesh and verify Pencil pressure, undo, and redo.
4. Save to the app's Documents folder, find it under Files → On My iPad → Blender,
   quit, relaunch, and reopen it. Do not assume cloud file handling works yet.
5. Check a small Workbench/EEVEE scene, then independently test Cycles availability.
6. Background/resume and try increasing scene sizes while watching for crashes.

Touch navigation, pressure input, Files sharing, and Metal code exist upstream;
their presence is not evidence that they work on these two devices. Several
features are explicitly disabled in the iOS build, including USD, OSL, audio
through Audaspace, and OpenXR.

## Local changes

The local patch adds configurable bundle ID, signing team, and a choice of memory
entitlements. It retains the original touch/Pencil implementation. An unsigned
or untested app must not be mistaken for an installable, verified build.

Sources:
- https://projects.blender.org/blender/blender/src/branch/ios
- https://code.blender.org/2025/07/beyond-mouse-keyboard/
- https://support.apple.com/en-lamr/guide/ipad/ipad213a25b2/27/ipados/27
- https://support.apple.com/en-bh/111939
