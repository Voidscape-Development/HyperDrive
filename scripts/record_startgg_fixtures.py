# Records start.gg's responses for test/test_startgg_provider.py: runs the
# test's scenario (every StartGGDataProvider method the app calls) against a
# real, finished event and saves each request and response, anonymized, to
# test/fixtures/startgg/. Then update the expected results:
#   python scripts/record_startgg_fixtures.py
#   python test/test_startgg_provider.py --update
# Run from the repository root. Needs network access to start.gg.
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "test"))
import startgg_harness as H

# A finished Ultimate event with a double elimination bracket, stations,
# stream assignments, stages reported, DQs and a grand final reset
EVENT = "https://www.start.gg/tournament/game-night-at-dave-and-busters-111/event/ultimate-singles"
FAKE_TOURNAMENT = "hyperdrive-test-tournament"
FAKE_TOURNAMENT_NAME = "HyperDrive Test Tournament"


# =====================================================
# ANONYMIZING
# =====================================================
class Anonymizer:
    """Replaces what identifies people (tags, sponsors, names, handles,
    pronouns, cities, avatars) and the event (its name, slug, venue and
    streams) with placeholders, the same one for the same value everywhere.
    Numeric ids are kept: the provider's lookups depend on them."""

    PERSON_PARENTS = {"entrant", "entrants", "player", "user", "participants", "team"}
    PERSON_KEYS = {"participants", "initialSeedNum", "gamerTag", "isDisqualified"}

    def __init__(self, tournamentSlug, tournamentName):
        self.maps = {}
        self.originals = set()
        self.tournamentSlug = tournamentSlug
        self.tournamentName = tournamentName
        # The name of the series ("Weekly #111" -> "Weekly"), which other
        # editions in players' histories carry too
        self.series = re.sub(r"\s*#\s*\d+\s*$", "", tournamentName)
        self.seriesSlug = re.sub(r"-\d+$", "", tournamentSlug)
        self.originals.update({tournamentName, self.series, tournamentSlug, self.seriesSlug})

    # Place names show up in other events' names ("... Brooklyn"), and alone
    # they don't identify anyone: they're replaced but not checked for
    UNCHECKED = {"city"}

    def Fake(self, kind, value, pattern):
        if value in (None, ""):
            return value
        if kind not in self.UNCHECKED:
            self.originals.add(value)
        table = self.maps.setdefault(kind, {})
        if value not in table:
            table[value] = pattern.format(len(table) + 1)
        return table[value]

    def Collect(self, value, parent=""):
        """First pass: tags and prefixes, so entrant names made of them can
        be rebuilt from the same placeholders"""
        if isinstance(value, dict):
            if parent == "player" or "gamerTag" in value:
                self.Fake("tag", value.get("gamerTag"), "Player {}")
                self.Fake("prefix", value.get("prefix"), "Team {}")
            for k, v in value.items():
                self.Collect(v, k)
        elif isinstance(value, list):
            for v in value:
                self.Collect(v, parent)

    def EntrantName(self, name):
        if not name:
            return name
        self.originals.add(name)
        parts = [p.strip() for p in name.split("|")]
        if all(p in self.maps.get("tag", {}) or p in self.maps.get("prefix", {}) for p in parts):
            fake = [self.maps["tag"].get(p) or self.maps["prefix"].get(p) for p in parts]
            return " | ".join(fake)
        tag = parts[-1]
        if tag in self.maps.get("tag", {}):
            # A sponsor prefix with "|" in it, e.g. "B Team | Bloom | Tag"
            prefix = " | ".join(parts[:-1])
            return f"{self.Fake('prefix', prefix, 'Team {}')} | {self.maps['tag'][tag]}"
        return self.Fake("entrant", name, "Entrant {}")

    def Slug(self, value):
        if not isinstance(value, str):
            return value
        if value.startswith("user/"):
            return self.Fake("user_slug", value, "user/anon{:04d}")
        value = value.replace(self.tournamentSlug, FAKE_TOURNAMENT)
        value = value.replace(self.seriesSlug, FAKE_TOURNAMENT)
        return value.replace(self.series, FAKE_TOURNAMENT_NAME)

    def Walk(self, value, parent=""):
        if isinstance(value, list):
            return [self.Walk(v, parent) for v in value]
        if not isinstance(value, dict):
            return self.Slug(value)
        person = parent in self.PERSON_PARENTS or bool(self.PERSON_KEYS & value.keys())
        out = {}
        for k, v in value.items():
            if isinstance(v, (dict, list)):
                out[k] = self.Walk(v, k)
            elif not isinstance(v, str):
                out[k] = v
            elif k == "gamerTag":
                out[k] = self.Fake("tag", v, "Player {}")
            elif k == "prefix":
                out[k] = self.Fake("prefix", v, "Team {}")
            elif k == "name" and parent in ("player", "user"):
                out[k] = self.Fake("real_name", v, "Real Name {}")
            elif k == "name" and person:
                out[k] = self.EntrantName(v)
            elif k == "genderPronoun":
                out[k] = self.Fake("pronoun", v, "pronoun{}")
            elif k == "externalUsername":
                out[k] = self.Fake("handle", v, "handle{}")
            elif k == "city":
                out[k] = self.Fake("city", v, "City {}")
            elif k == "venueAddress":
                out[k] = self.Fake("venue", v, "Venue {}")
            elif k == "streamName":
                out[k] = self.Fake("stream", v, "stream{}")
            elif k == "shortSlug":
                out[k] = self.Fake("short_slug", v, "short{}")
            elif k == "url" and "/images/user/" in v:
                out[k] = self.Fake(
                    "avatar", v, "https://images.start.gg/images/user/0/avatar-{}.png"
                )
            else:
                out[k] = self.Slug(v)
        return out

    def Leaks(self, value):
        """Original values (3+ characters) still in the anonymized data"""
        found = set()
        check = [o for o in self.originals if isinstance(o, str) and len(o) >= 3]

        def walk(v):
            if isinstance(v, dict):
                for x in v.values():
                    walk(x)
            elif isinstance(v, list):
                for x in v:
                    walk(x)
            elif isinstance(v, str):
                found.update(o for o in check if o in v)

        walk(value)
        return found


# =====================================================
# RECORDING
# =====================================================
def main():
    context = H.SetUpApp()
    provider = H.RecordingProvider(EVENT, context)
    provider.url = provider.GetRealEventURL(EVENT)
    out = H.RunScenario(provider)
    recorded = list(provider.recorded.values())
    print(f"{len(recorded)} requests recorded")

    tournamentSlug = re.search(r"tournament/([^/]+)", provider.url).group(1)
    tournamentName = out["tournament_data"]["tournamentName"]
    anonymizer = Anonymizer(tournamentSlug, tournamentName)
    for r in recorded:
        anonymizer.Collect(r["response"])
    requests = []
    for r in recorded:
        variables = anonymizer.Walk(r["variables"], "variables")
        response = anonymizer.Walk(r["response"])
        jsonParams = {"operationName": r["operation"], "variables": variables, "query": r["query"]}
        requests.append(
            {
                "key": H.RequestKey(r["url"], jsonParams, r["params"]),
                "operation": r["operation"],
                "variables": variables,
                "response": response,
            }
        )
    requests.sort(key=lambda r: r["key"])
    recording = {"event": anonymizer.Slug(provider.url), "requests": requests}

    leaks = anonymizer.Leaks(recording)
    if leaks:
        sys.exit(f"Not saved: these weren't anonymized: {sorted(leaks)[:20]}")
    H.SaveJson(H.RECORDING, recording, compress=True)
    print(f"Saved {H.RECORDING} ({os.path.getsize(H.RECORDING) // 1024} KB)")


if __name__ == "__main__":
    main()
