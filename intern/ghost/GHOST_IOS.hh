/* SPDX-FileCopyrightText: 2026 Blender Authors
 *
 * SPDX-License-Identifier: GPL-2.0-or-later */

#pragma once

#include "GHOST_Types.hh"

/** Queue the native iPad share sheet for an existing local file. */
GHOST_TSuccess GHOST_shareFileIOS(const char *filepath);
