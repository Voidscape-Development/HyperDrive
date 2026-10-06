#!/bin/bash

# Renders the app icon and splash screen from their SVG sources:
#   assets/icons/icon.svg   -> assets/icons/icon.png, assets/icons/icon.ico,
#                              stage_strike_app/public/favicon.ico
#   assets/icons/splash.svg -> assets/icons/splash.png (drawn at 2x)
#
# Needs a Chromium/Chrome binary (set CHROME to its path if it isn't on PATH)
# and ImageMagick's convert.

set -e

DIR=$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)
ICONS="$DIR/assets/icons"
CHROME=${CHROME:-$(command -v chromium || command -v chromium-browser || command -v google-chrome)}
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

if [ -z "$CHROME" ]; then
  echo "Chromium not found. Set CHROME to the path of a Chromium/Chrome binary."
  exit 1
fi

# render <svg> <out.png> <width> <height> <scale>
render() {
  "$CHROME" --headless --no-sandbox --disable-gpu --hide-scrollbars \
    --default-background-color=00000000 --force-device-scale-factor="$5" \
    --window-size="$3,$4" --screenshot="$2" "file://$1" >/dev/null 2>&1
}

render "$ICONS/icon.svg" "$TMP/icon512.png" 256 256 2
for size in 16 24 32 48 64 128 256; do
  convert "$TMP/icon512.png" -filter Lanczos -resize "${size}x${size}" -strip \
    "PNG32:$TMP/icon_$size.png"
done
cp "$TMP/icon_256.png" "$ICONS/icon.png"
convert "$TMP"/icon_{16,24,32,48,64,128,256}.png "$ICONS/icon.ico"
convert "$TMP"/icon_{16,24,32,48,64}.png "$DIR/stage_strike_app/public/favicon.ico"

render "$ICONS/splash.svg" "$ICONS/splash.png" 540 220 2

echo "Icons generated"
