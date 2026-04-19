#!/bin/bash

set -euo pipefail

APP_ID="com.github.aliafacan.ZorinDesktopStudio"
MANIFEST="packaging/flatpak/${APP_ID}.json"
REPO_DIR="flatpak-repo"
BUILD_DIR="flatpak-build"

flatpak-builder --force-clean --repo="${REPO_DIR}" "${BUILD_DIR}" "${MANIFEST}"
flatpak build-bundle "${REPO_DIR}" "${APP_ID}.flatpak" "${APP_ID}" || true

echo "Local build complete."
echo "Install locally: flatpak install --user --bundle ${APP_ID}.flatpak"
