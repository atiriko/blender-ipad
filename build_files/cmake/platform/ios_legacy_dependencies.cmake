# SPDX-FileCopyrightText: 2026 Blender Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

# The pinned iOS bundle predates the imported CMake targets used by Blender.
# Provide targets for its existing device libraries. Never discover macOS
# libraries from Homebrew while configuring an iOS target.
list(APPEND CMAKE_IGNORE_PREFIX_PATH /opt/homebrew /usr/local)

function(ios_import_library target binary)
  if(NOT EXISTS "${binary}")
    message(FATAL_ERROR "Missing iOS dependency: ${binary}")
  endif()
  add_library(${target} SHARED IMPORTED GLOBAL)
  set_target_properties(${target} PROPERTIES
    IMPORTED_LOCATION "${binary}"
    INTERFACE_INCLUDE_DIRECTORIES "${ARGN}")
endfunction()

ios_import_library(Imath::Imath "${LIBDIR}/imath/lib/libImath.dylib"
  "${LIBDIR}/imath/include" "${LIBDIR}/imath/include/Imath")
ios_import_library(OpenEXR::OpenEXR "${LIBDIR}/openexr/lib/libOpenEXR.dylib"
  "${LIBDIR}/openexr/include" "${LIBDIR}/openexr/include/OpenEXR")
set_property(TARGET OpenEXR::OpenEXR PROPERTY INTERFACE_LINK_LIBRARIES
  "Imath::Imath;${LIBDIR}/openexr/lib/libIex.dylib;${LIBDIR}/openexr/lib/libIlmThread.dylib;${LIBDIR}/openexr/lib/libOpenEXRCore.dylib")
ios_import_library(OpenImageIO::OpenImageIO_Util
  "${LIBDIR}/openimageio/lib/libOpenImageIO_Util.dylib" "${LIBDIR}/openimageio/include")
ios_import_library(OpenImageIO::OpenImageIO
  "${LIBDIR}/openimageio/lib/libOpenImageIO.dylib" "${LIBDIR}/openimageio/include")
set_property(TARGET OpenImageIO::OpenImageIO PROPERTY INTERFACE_LINK_LIBRARIES
  "OpenImageIO::OpenImageIO_Util;Imath::Imath")
add_executable(OpenImageIO::oiiotool IMPORTED GLOBAL)
set_target_properties(OpenImageIO::oiiotool PROPERTIES
  IMPORTED_LOCATION "${CROSSCOMPILE_HOST_LIBDIR}/openimageio/bin/oiiotool")

# Header-only fmt must match the version bundled by the iOS OpenImageIO binary.
# Mixing its fmt 9 headers with the host bundle's fmt 12 breaks compilation.
set(BLENDER_IOS_FMT_INCLUDE_DIR "" CACHE PATH "fmt 9.1 headers for iOS OpenImageIO")
if(NOT EXISTS "${BLENDER_IOS_FMT_INCLUDE_DIR}/fmt/ranges.h")
  message(FATAL_ERROR "Prepare fmt 9.1 headers with build_ipad.py configure")
endif()
add_library(fmt::fmt INTERFACE IMPORTED GLOBAL)
set_target_properties(fmt::fmt PROPERTIES
  INTERFACE_INCLUDE_DIRECTORIES "${BLENDER_IOS_FMT_INCLUDE_DIR}"
  INTERFACE_COMPILE_DEFINITIONS FMT_HEADER_ONLY)
# Eigen is platform-independent; no host object code is linked into the app.
add_library(Eigen3::Eigen INTERFACE IMPORTED GLOBAL)
set_target_properties(Eigen3::Eigen PROPERTIES
  INTERFACE_INCLUDE_DIRECTORIES "${CROSSCOMPILE_HOST_LIBDIR}/eigen/include/eigen3")

set(OPENCOLORIO_INCLUDE_DIRS "${LIBDIR}/opencolorio/include")
set(OPENCOLORIO_LIBRARIES "${LIBDIR}/opencolorio/lib/libOpenColorIO.dylib")
