# Checks src/state_schema.py, the description of the program state that the
# clients' types are generated from:
# - layout/include/state.d.ts is what scripts/gen_state_types.py generates;
# - the sample state the previews are rendered with (made by running the
#   application, see scripts/previews/gen_sample_state.py) fits it, and has
#   no key it doesn't describe;
# - the keys the application sets (the StateManager.Set / Unset calls in
#   src/, read from the source) are described.
# Run from the repository root: python test/test_state_schema.py
import glob
import importlib.util
import inspect
import json
import os
import re
import sys
import types
import typing

from pydantic import BaseModel

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SAMPLE_STATE = os.path.join(ROOT, "scripts", "previews", "sample_state.json")


def Load(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# Loaded by path: importing the src package would import the application
gen = Load("gen_state_types", "scripts/gen_state_types.py")
schema = gen.load_schema()

# ---------------------------------------------------------------------------
# Paths of the schema


def Alternatives(annotation):
    """The types an annotation allows, without None and Annotated. Loose and
    Any are None: anything goes below."""
    if annotation is typing.Any:
        return [None]
    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)
    if origin is typing.Annotated:
        return [None] if schema.LooseMarker in args[1:] else Alternatives(args[0])
    if origin in (typing.Union, types.UnionType):
        return [a for arg in args if arg is not type(None) for a in Alternatives(arg)]
    return [annotation]


def Hints(model):
    return typing.get_type_hints(model, include_extras=True)


def ExtraType(model):
    """What a model's other keys hold, if it says (numbered keys)."""
    extra = Hints(model).get("__pydantic_extra__")
    return typing.get_args(extra)[1] if extra is not None else None


def Resolve(annotation, segments):
    """Whether a path of keys can be in the state, from a type of the
    schema: "ok", "loose" (it goes into what isn't described), "dynamic"
    (a key made at run time, in a model: not checked) or an error message.
    A segment is a key, or a pattern with * for the parts made at run time."""
    if not segments:
        return "ok"
    results = [ResolveOne(a, segments) for a in Alternatives(annotation)]
    for good in ("ok", "dynamic", "loose"):
        if good in results:
            return good
    return results[0]


def ResolveOne(annotation, segments):
    if annotation is None:
        return "loose"
    key, rest = segments[0], segments[1:]
    origin = typing.get_origin(annotation)
    if origin in (dict, list):
        return Resolve(typing.get_args(annotation)[-1], rest)
    if inspect.isclass(annotation) and issubclass(annotation, BaseModel):
        hints = Hints(annotation)
        extra = ExtraType(annotation)
        if key == "*":
            # A numbered key where the model has them, otherwise any key
            return Resolve(extra, rest) if extra is not None else "dynamic"
        pattern = re.compile(".*".join(re.escape(part) for part in key.split("*")))
        for name, field in annotation.model_fields.items():
            if pattern.fullmatch(field.alias or name):
                return Resolve(hints[name], rest)
        if extra is not None and "*" not in key:
            return Resolve(extra, rest)
        return f"{annotation.__name__} has no key {key!r}"
    return f"{key!r} is under a value that isn't an object ({annotation!r})"


def TestResolve():
    state = schema.State
    assert Resolve(state, ["score", "*", "team", "1", "score"]) == "ok"
    assert Resolve(state, ["score", "ruleset", "name"]) == "ok"
    assert Resolve(state, ["team_battle", "team*_spinner-total"]) == "ok"
    assert Resolve(state, ["bracket", "bracket", "sets", "m1", "players", "0", "name"]) == "ok"
    assert Resolve(state, ["score", "*", "station_queue", "anything"]) == "loose"
    assert Resolve(state, ["score", "*", "team", "*", "*"]) == "dynamic"
    assert "no key 'nope'" in Resolve(state, ["nope"])
    assert "no key 'nope'" in Resolve(state, ["score", "*", "team", "1", "nope"])
    assert "isn't an object" in Resolve(state, ["score", "*", "phase", "x"])


# ---------------------------------------------------------------------------
# The generated types


def TestGeneratedTypes():
    with open(gen.OUT_FILE, encoding="utf-8") as file:
        current = file.read()
    assert current == gen.generate(), (
        "layout/include/state.d.ts is not up to date with src/state_schema.py: "
        "run python scripts/gen_state_types.py"
    )
    # Every model is in it
    for model in gen.models(schema):
        assert f"  interface {model.__name__} {{" in current, model.__name__


def TestNoQt():
    with open(gen.SCHEMA_FILE, encoding="utf-8") as file:
        source = file.read()
    imports = re.findall(r"^\s*(?:from|import)\s+([\w.]+)", source, re.M)
    assert set(imports) == {"typing", "pydantic"}, imports


# ---------------------------------------------------------------------------
# The sample state


def Undescribed(value, path=""):
    """Paths of the keys of a validated state that its models don't have."""
    found = set()
    if isinstance(value, BaseModel):
        model = type(value)
        for name, field in model.model_fields.items():
            found |= Undescribed(getattr(value, name), f"{path}.{field.alias or name}")
        for key, item in (value.model_extra or {}).items():
            if ExtraType(model) is not None:
                found |= Undescribed(item, f"{path}.*")
            else:
                found.add(f"{path}.{key}"[1:])
    elif isinstance(value, dict):
        for item in value.values():
            found |= Undescribed(item, f"{path}.*")
    elif isinstance(value, list):
        for item in value:
            found |= Undescribed(item, f"{path}.*")
    return found


def TestSampleState():
    with open(SAMPLE_STATE, encoding="utf-8") as file:
        sample = json.load(file)
    # Raises with the paths that don't fit
    state = schema.State.model_validate(sample)
    assert Undescribed(state) == set(), (
        "Keys of scripts/previews/sample_state.json that src/state_schema.py doesn't describe",
        sorted(Undescribed(state)),
    )
    # Every section but the file's timestamp and what only a tournament
    # provider sets is in the sample
    missing = set(schema.SECTIONS) - set(sample)
    assert missing <= {"timestamp", "provider_videogame"}, missing


def TestValidation():
    with open(SAMPLE_STATE, encoding="utf-8") as file:
        sample = json.load(file)
    schema.State.model_validate({})

    def Fails(change):
        state = json.loads(json.dumps(sample))
        change(state)
        try:
            schema.State.model_validate(state)
        except ValueError:
            return True
        return False

    # Strict: text isn't a number, a number isn't a boolean
    assert Fails(lambda s: s["score"]["1"]["team"]["1"].update(score="2"))
    assert Fails(lambda s: s["score"]["1"]["team"]["1"].update(losers=1))
    assert Fails(lambda s: s["score"].update({"2": "not a scoreboard"}))
    assert Fails(lambda s: s["display"]["folders"].update(scoreboard="on"))
    assert Fails(lambda s: s["team_battle"].update(battle_mode="OTHER"))
    assert not Fails(lambda s: s["score"]["1"]["team"]["1"].update(score=None))

    # Other keys are allowed, and found
    state = json.loads(json.dumps(sample))
    state["score"]["1"]["team"]["1"]["new_key"] = 1
    state["new_section"] = {}
    assert Undescribed(schema.State.model_validate(state)) == {
        "score.*.team.*.new_key",
        "new_section",
    }


# ---------------------------------------------------------------------------
# The keys the application sets

# StateManager.Set("a.b", ...), StateManager.Unset(f"a.{n}.b"): the key when
# it is written there as text
SET_CALL = re.compile(r"StateManager\.(?:Set|Unset)\(\s*(f?)(\"[^\"\n]*\"|'[^'\n]*')")
ANY_SET_CALL = re.compile(r"StateManager\.(?:Set|Unset)\(")

# Keys that start with a variable: where that is in the state, by file. A
# call with one that isn't here fails the test: add it.
PLAYER = "score.*.team.*.player.*"
PREFIXES = {
    # Also the commentators and the player lists' players: the same model
    ("src/ScoreboardPlayerWidget.py", "self.path"): PLAYER,
    ("src/ScoreboardPlayerWidget.py", "w.path"): PLAYER,
    ("src/PlayerWidgetMixin.py", "self.path"): PLAYER,
    ("src/Helpers/DynamicExport.py", "path"): PLAYER,
    ("src/Helpers/SponsorHelper.py", "path"): PLAYER,
    ("src/TeamPlayerWidget.py", "self.path"): "team_battle.team.*.player.*",
    ("src/TeamPlayerWidget.py", "w.path"): "team_battle.team.*.player.*",
    # player_list, and bracket.rosters.<key>
    ("src/PlayerListSlotWidget.py", "self.base"): "player_list",
    ("src/PlayerList.py", "self.base"): "player_list",
    ("src/ScoreboardWidget.py", "base"): "score.*",
}


def Segments(key, formatted):
    """A key's segments, with * for the parts an f-string fills in, and the
    variable it starts with, if it does."""
    prefix = None
    if formatted:
        start = re.match(r"\{([^{}]*)\}(?=\.|$)", key)
        if start:
            prefix = start.group(1).strip()
            key = key[start.end() :].lstrip(".")
        key = re.sub(r"\{[^{}]*\}", "*", key)
    return prefix, [s for s in key.split(".") if s]


def SetCalls():
    """(file, line, key as written, prefix variable, segments) of each call
    with its key written as text, and how many calls there are in all."""
    calls, total = [], 0
    for path in sorted(glob.glob(os.path.join(ROOT, "src", "**", "*.py"), recursive=True)):
        with open(path, encoding="utf-8") as file:
            source = file.read()
        name = os.path.relpath(path, ROOT).replace(os.sep, "/")
        if name == "src/StateManager.py":
            continue
        total += len(ANY_SET_CALL.findall(source))
        for match in SET_CALL.finditer(source):
            key = match.group(2)[1:-1]
            line = source.count("\n", 0, match.start()) + 1
            calls.append((name, line, key, *Segments(key, bool(match.group(1)))))
    return calls, total


def TestSegments():
    assert Segments("score.ruleset", False) == (None, ["score", "ruleset"])
    assert Segments("score.{self.n}.team.{t + 1}.color", True) == (
        None,
        ["score", "*", "team", "*", "color"],
    )
    assert Segments("{self.path}.{element.objectName()}", True) == ("self.path", ["*"])
    assert Segments("team_battle.team{team}_total-score", True) == (
        None,
        ["team_battle", "team*_total-score"],
    )
    assert Segments("{base}", True) == ("base", [])


def TestSetCalls():
    calls, total = SetCalls()
    # The scan finds the calls: most have their key written as text
    assert len(calls) > 150 and len(calls) > total * 0.8, (len(calls), total)

    problems = []
    results = {"ok": 0, "loose": 0, "dynamic": 0}
    sections = set()
    for file, line, key, prefix, segments in calls:
        if prefix is not None:
            where = PREFIXES.get((file, prefix))
            if where is None:
                problems.append(
                    f"{file}:{line}: {key!r} starts with {prefix!r}: say where that is in "
                    "the state, in PREFIXES of test/test_state_schema.py"
                )
                continue
            segments = where.split(".") + segments
        if not segments:
            continue
        sections.add(segments[0])
        result = Resolve(schema.State, segments)
        if result in results:
            results[result] += 1
        else:
            problems.append(f"{file}:{line}: {key!r}: {result}")
    assert not problems, (
        "Keys set in src/ that src/state_schema.py doesn't describe (add them there, "
        "then run python scripts/gen_state_types.py):\n" + "\n".join(problems)
    )
    # Mostly checked for real, not waved through
    assert results["ok"] > (results["loose"] + results["dynamic"]) * 4, results
    # Every section is set somewhere (out/program_state.json's timestamp is
    # StateManager's own)
    assert set(schema.SECTIONS) - sections == {"timestamp"}, set(schema.SECTIONS) - sections
    print(f"  {len(calls)} of {total} Set/Unset calls checked: {results}")


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("Test")]
    for test in tests:
        test()
        print(f"{test.__name__}: OK")
