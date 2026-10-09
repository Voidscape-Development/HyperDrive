#!/bin/bash

# The following stub makes it so that this script always runs in the directory it is located within.
# It works on macos, and will follow symbolic links and generally will make it difficult to have

SOURCE=${BASH_SOURCE[0]}
while [ -L "$SOURCE" ]; do # resolve $SOURCE until the file is no longer a symlink
  DIR=$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )
  SOURCE=$(readlink "$SOURCE")
  [[ $SOURCE != /* ]] && SOURCE=$DIR/$SOURCE # if $SOURCE was a relative symlink, we need to resolve it relative to the path where the symlink file was located
done
DIR=$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )



if ! pushd "${DIR}/.." >/dev/null 2>&1; then
  echo "Couldn't enter directory ${DIR}/.. Quitting."
  popd >/dev/null 2>&1
  exit 255
fi

# HyperDrive.exe isn't committed: build it with dependencies/hyperdrive.spec and copy it here
if [ ! -f HyperDrive.exe ]; then
  echo "HyperDrive.exe not found. Build it and copy it to the repository root first."
  popd >/dev/null 2>&1
  exit 1
fi

# Create HyperDrive dir and its stage_strike_app folders
mkdir -p HyperDrive/stage_strike_app/build

cp -R assets \
	layout \
	src \
	LICENSE \
	HyperDrive.exe \
	HyperDrive/

# Only the files committed to user_data: running the program writes
# settings.json and other user files there, and those mustn't ship
git ls-files -z -- user_data | xargs -0 -I{} cp --parents {} HyperDrive/

cp -R stage_strike_app/build \
	HyperDrive/stage_strike_app/

rm -rf \
	HyperDrive/assets/versions.json \
	HyperDrive/layout/game_images \
	HyperDrive/layout/game_screenshots

find HyperDrive/src -type d -name __pycache__ -prune -exec rm -rf {} +

rm -f HyperDrive-windows.zip
zip -rv HyperDrive-windows.zip HyperDrive

rm -rf HyperDrive

popd >/dev/null 2>&1