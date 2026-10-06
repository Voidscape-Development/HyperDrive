"""Builds assets/countries.json from the countries+states+cities database
(https://github.com/dr5hn/countries-states-cities-database), keeping only
what HyperDrive reads from it.

Usage: python scripts/gen_countries.py <countries+states+cities.json> [out]

Run weekly by .github/workflows/update_countries.yml.
"""

import json
import os
import sys
import unicodedata

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT_FILE = os.path.join(ROOT, "assets", "countries.json")
MAPPING_FILE = os.path.join(ROOT, "src", "i18n", "mapping.json")


def remove_accents_lower(input_str):
    # Must match CountryHelper.remove_accents_lower
    nfkd_form = unicodedata.normalize("NFKD", input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).lower()


def app_translation_keys():
    """The translation keys HyperDrive can look up: each of its languages, and the
    language without its region (CountryHelper tries both)"""
    with open(MAPPING_FILE, encoding="utf-8") as f:
        languages = json.load(f).get("languages")

    keys = set()
    for language in languages:
        keys.add(language)
        keys.add(language.split("-")[0])
    return keys


def build(countries_json):
    translation_keys = app_translation_keys()

    countries = []
    for country in countries_json:
        states = country.get("states") or []

        cities = {}
        for state in states:
            for city in state.get("cities") or []:
                city_name = remove_accents_lower(city["name"])
                if city_name not in cities:
                    cities[city_name] = state.get("iso2")

        countries.append(
            {
                "name": country.get("name"),
                "iso2": country.get("iso2"),
                "translations": {
                    k: v
                    for k, v in (country.get("translations") or {}).items()
                    if k in translation_keys
                },
                "latitude": country.get("latitude"),
                "longitude": country.get("longitude"),
                "states": [
                    {
                        "name": s.get("name"),
                        "iso2": s.get("iso2"),
                        "latitude": s.get("latitude"),
                        "longitude": s.get("longitude"),
                    }
                    for s in states
                ],
                # City name (accentless, lowercase) to state code, for finding a
                # player's state from their city
                "cities": cities,
            }
        )

    return countries


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    with open(sys.argv[1], "rb") as f:
        countries_json = json.load(f)

    countries = build(countries_json)
    if len(countries) < 200:
        raise Exception(f"Only {len(countries)} countries, the source file looks wrong")

    out_file = sys.argv[2] if len(sys.argv) > 2 else OUT_FILE
    with open(out_file, "w", encoding="utf-8", newline="\n") as f:
        json.dump(countries, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        f.write("\n")

    print(f"Wrote {len(countries)} countries to {out_file} ({os.path.getsize(out_file)} bytes)")


if __name__ == "__main__":
    main()
