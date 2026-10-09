# Display Controls: shows and hides layouts, by layout folder (scoreboard,
# commentators...) and by group (a layout's ?display=<group>). A layout is
# shown while its folder and every one of its groups are on. No Qt here, so
# it can be tested on its own.

import os

KIND_FOLDER = "folder"
KIND_GROUP = "group"
KINDS = (KIND_FOLDER, KIND_GROUP)

ACTION_SHOW = "show"
ACTION_HIDE = "hide"
ACTION_TOGGLE = "toggle"
ACTIONS = (ACTION_SHOW, ACTION_HIDE, ACTION_TOGGLE)

MAX_GROUP_NAME = 40

# Folders in layout/ that aren't layouts
IGNORED_FOLDERS = ("include",)


def NormalizeGroupName(name):
    """A group's name as it's kept and matched: lowercase, without commas
    (they separate a layout's groups) or extra spaces. Empty if there's
    nothing left."""
    name = " ".join(str(name or "").replace(",", " ").split()).lower()
    return name[:MAX_GROUP_NAME].strip()


def NormalizeAction(action):
    action = str(action or "").strip().lower()
    return action if action in ACTIONS else None


def Resolve(action, shown):
    """Whether something is shown after an action, from whether it is now."""
    if action == ACTION_SHOW:
        return True
    if action == ACTION_HIDE:
        return False
    return not shown


def LayoutFolders(root):
    """The layout folders in root: every folder with a page in it, by name
    (the layouts know theirs from their URL, so it's the name, not the
    path). Sorted, without duplicates."""
    folders = set()
    if not os.path.isdir(root):
        return []
    for path, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in IGNORED_FOLDERS and not d.startswith(".")]
        if path != root and any(f.lower().endswith(".html") for f in files):
            folders.add(os.path.basename(path))
    return sorted(folders, key=str.lower)


def MatchFolder(name, folders):
    """The folder called name (exactly, or else ignoring case), or None."""
    name = str(name or "").strip()
    if name in folders:
        return name
    lowered = name.lower()
    for folder in folders:
        if folder.lower() == lowered:
            return folder
    return None


def BuildState(folders, folderValues, groupValues):
    """What the layouts get in program_state's display: every folder and
    group with whether it's on. Folders never switched are on."""
    state_folders = {f: folderValues.get(f, True) is not False for f in folders}
    # Switched folders that aren't in layout/ anymore still apply, should
    # they come back
    for f, value in folderValues.items():
        state_folders.setdefault(f, value is not False)
    return {
        "folders": state_folders,
        "groups": {g: v is not False for g, v in sorted(groupValues.items())},
    }


def IsVisible(state, folder, groups=()):
    """Whether a layout in folder with these groups is shown (the same as
    the layouts work out in globals.js)."""
    state = state or {}
    if (state.get("folders") or {}).get(folder) is False:
        return False
    return all((state.get("groups") or {}).get(NormalizeGroupName(g)) is not False for g in groups)
