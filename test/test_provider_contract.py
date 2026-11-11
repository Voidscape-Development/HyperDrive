# Checks that every tournament data provider keeps the contract of
# TournamentDataProvider:
# - its public methods take what the base class' take (same parameters, same
#   defaults), so a caller written for one provider works with the others
# Run from the repository root: python test/test_provider_contract.py
import inspect
import os
import sys
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.abspath("."))
# Import only the modules needed, not the whole application
for name, path in [
    ("src", "src"),
    ("src.Helpers", "src/Helpers"),
    ("src.TournamentDataProvider", "src/TournamentDataProvider"),
]:
    package = types.ModuleType(name)
    package.__path__ = [os.path.abspath(path)]
    sys.modules[name] = package

from src.TournamentDataProvider.ParryGGDataProvider import ParryGGDataProvider
from src.TournamentDataProvider.StartGGDataProvider import StartGGDataProvider
from src.TournamentDataProvider.TournamentDataProvider import TournamentDataProvider

PROVIDERS = [StartGGDataProvider, ParryGGDataProvider]


def ContractMethods():
    """The base class' own public methods"""
    return sorted(
        name
        for name, value in vars(TournamentDataProvider).items()
        if inspect.isfunction(value) and not name.startswith("_")
    )


def Parameters(function):
    return [
        (p.name, p.kind, p.default)
        for p in inspect.signature(function).parameters.values()
        if p.name != "self"
    ]


# =====================================================
# SIGNATURES
# =====================================================
def TestSignatures():
    methods = ContractMethods()
    assert "GetFutureMatch" in methods and "GetStandings" in methods, methods

    problems = []
    for provider in PROVIDERS:
        for name in methods:
            expected = Parameters(getattr(TournamentDataProvider, name))
            got = Parameters(getattr(provider, name))
            if got != expected:
                problems.append(
                    f"{provider.__name__}.{name}{inspect.signature(getattr(provider, name))}"
                    f" != {inspect.signature(getattr(TournamentDataProvider, name))}"
                )
    assert not problems, "\n" + "\n".join(problems)

    # What a Worker passes is optional everywhere, so a method can be called
    # directly too (the stream queue calls GetFutureMatch(setId))
    for name in methods:
        parameters = inspect.signature(getattr(TournamentDataProvider, name)).parameters
        for extra in ("progress_callback", "cancel_event"):
            if extra in parameters:
                assert parameters[extra].default is None, f"{name}: {extra} has no default"


if __name__ == "__main__":
    TestSignatures()
    print("OK")
