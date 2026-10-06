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



if ! pushd "${DIR}" >/dev/null 2>&1; then
  echo "Couldn't enter directory ${DIR}. Quitting."
  exit 255
fi

# uv installs the right Python (see .python-version) and the dependencies
# locked in uv.lock into ./.venv. Install it from https://docs.astral.sh/uv/
if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found. Install it with: curl -LsSf https://astral.sh/uv/install.sh | sh"
  popd >/dev/null 2>&1
  exit 255
fi

uv run --frozen --no-dev main.py
popd >/dev/null 2>&1
