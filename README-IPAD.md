# Blender for iPad (`personal-ipad`)

This repository is a working iPadOS port of Blender 5.1.2 based on the upstream experimental [`ios` branch](https://projects.blender.org/blender/blender/src/branch/ios) (`a1de44dd54af75a4c8c4a29a5fed2a1334a87446`), with fixes and enhancements for building, signing, and running natively on arm64 iPads.

## Key Enhancements Over Upstream `ios`

- **Python 3.13 iOS Runtime & Extension Packaging**: Resolves the upstream Python 3.11 / 3.13 mismatch by fetching a checksum-pinned BeeWare Python 3.13 iOS framework and NumPy wheel, packaging `.so` C-extensions as iOS `.framework` bundles with `.fwork` markers, and setting `config.executable` to the app binary so `AppleFrameworkLoader` resolves extension modules at startup.
- **Apple Pencil & Touch Input Fixes**:
  - Routes Apple Pencil strokes directly through `touchesBegan` / `touchesMoved` / `touchesEnded` with coalesced touch samples (`coalescedTouchesForTouch:`) and precise coordinates.
  - Initializes stylus pressure and tilt at initial contact rather than waiting for movement.
  - Tracks active Pencil touches independently of finger touches so lifting a finger does not reset stylus state.
  - Suppresses finger gesture recognizers during an active Pencil stroke and releases held mouse/stylus buttons cleanly on touch cancellation or app resignation.
  - Balances Apple Pencil double-tap (`PENCIL_TAP`) right-click press/release events.
  - Fixes 3D Viewport orbit and pan gizmos so direct Pencil and mouse drags work alongside two-finger multitouch navigation.
- **Writable Sandbox Paths & Native File Sharing**:
  - Fixes a dangling `c_str()` pointer in `BKE_appdir_folder_default_or_root()` and defaults file operations to the app sandbox's writable `Documents` directory.
  - Redirects unwritable or read-only save paths to `Documents` and presents the native iPadOS `UIActivityViewController` share sheet ("Save to Files", AirDrop, etc.) after completed save/export operations.
- **Floating Touch Shortcuts Strip**:
  - Adds a customizable viewport gizmo toolbar (`space_view3d_ipad.py`) with quick touch buttons for Undo, Redo, Move, Rotate, Scale, Frame Selected, Edit Mode toggle, mode-aware Context Menu, Save, Zoom, mesh tools, and custom Blender operator IDs with JSON properties.
  - Persists user configuration in `ipad_shortcuts.json` inside Blender's user config directory.
- **Configurable Code Signing & Build Helper**:
  - Adds `build_ipad.py` and CMake options (`BLENDER_IOS_BUNDLE_ID`, `BLENDER_IOS_DEVELOPMENT_TEAM`, `BLENDER_IOS_SIGNING_IDENTITY`, `BLENDER_IOS_INCREASED_MEMORY_LIMIT`) to build and sign bundled dynamic libraries, frameworks, and the final `.app` bundle without hardcoding team IDs.

---

## Requirements

- **Apple Silicon Mac** (macOS) with full **Xcode** and the iOS SDK installed.
- **CMake**, **Git LFS**, and **Python 3**:
  ```sh
  brew install cmake git-lfs python
  ```
- An arm64 iPad with Developer Mode enabled and an Apple Developer / personal signing team configured in Xcode (`Settings → Accounts`).

---

## Quick Start: Build & Run on iPad

Clone this repository to a path **without spaces** (upstream host-tool build scripts do not support spaces in paths). The build directory is created alongside the checkout at `../build_ios`.

```sh
GIT_LFS_SKIP_SMUDGE=1 git clone --branch personal-ipad --single-branch https://github.com/atiriko/blender-ipad.git ~/blender-ipad
cd ~/blender-ipad
```

### 1. Download dependencies and prepare the iOS Python 3.13 runtime

```sh
python3 build_ipad.py setup
```

`setup` configures the official Blender Git LFS endpoint for runtime assets, checks out the pinned `lib/macos_arm64` and `lib/ios_arm64` precompiled library submodules, and prepares the Python 3.13 iOS runtime, NumPy wheel, and `fmt` 9.1 headers under `.local/`.

### 2. Configure the Xcode project

```sh
python3 build_ipad.py configure \
  --bundle-id personal.yourname.blender \
  --team YOUR_TEAM_ID \
  --signing-identity YOUR_CERTIFICATE_SHA1
```

- Replace `personal.yourname.blender` with your own unique bundle identifier.
- `--team` and `--signing-identity` are optional if you prefer to configure signing inside Xcode (`open ../build_ios/Blender.xcodeproj`), or if you are performing an unsigned build first.
- Add `--increased-memory` if your provisioning profile supports the `com.apple.developer.kernel.increased-memory-limit` entitlement.

### 3. Build and install

From the terminal (with a valid signing identity configured):

```sh
python3 build_ipad.py build --jobs 4
```

*(Note: `--jobs` defaults to `1` so large geometry-node unity builds succeed on 8 GB Macs; increase `--jobs` on Macs with 16 GB+ RAM.)*

To verify compilation without code signing:

```sh
python3 build_ipad.py build --unsigned --jobs 4
```

To deploy and debug from Xcode:

```sh
open ../build_ios/Blender.xcodeproj
```

1. Select your connected **iPad** as the run destination (do not select an iOS Simulator).
2. Build the **`install`** scheme in `Release` configuration so runtime scripts, assets, Python frameworks, and signed libraries are packaged into `Blender.app`.
3. Select the **`blender`** scheme and run it on your iPad.

---

## Running Automated Regression Checks on macOS

You can run the unit and regression tests for the iOS port directly on macOS:

```sh
python3 tests/ios/test_pencil_input.py
python3 tests/ios/test_navigation_input.py
python3 tests/ios/test_file_sharing.py
python3 tests/ios/test_library_signing.py
python3 tests/ios/test_python_packaging.py
```

To test the Touch Shortcuts UI in desktop Blender 5.1+:

```sh
blender --background --factory-startup --python tests/ios/test_touch_shortcuts.py
```

---

## Upstream References

- [Blender Official Repository (`ios` branch)](https://projects.blender.org/blender/blender/src/branch/ios)
- [Blender Blog: Beyond Mouse & Keyboard](https://code.blender.org/2025/07/beyond-mouse-keyboard/)
- [BeeWare Python-Apple-support](https://github.com/beeware/Python-Apple-support/releases/tag/3.13-b15)
- [CPython 3.13 iOS Documentation](https://docs.python.org/3.13/using/ios.html)
