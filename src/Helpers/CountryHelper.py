import os
import re
import sys
import traceback
import unicodedata

import orjson
from loguru import logger
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from .LocaleHelper import LocaleHelper


class CountryHelperSignals(QObject):
    countriesUpdated = Signal()


class CountryHelper(QObject):
    instance: "CountryHelper" = None

    countries = {}
    cities = {}
    countryModel = None
    signals = CountryHelperSignals()

    def __init__(self) -> None:
        super().__init__()

    def remove_accents_lower(input_str):
        nfkd_form = unicodedata.normalize("NFKD", input_str)
        return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).lower()

    def GetBasicCountryInfo(country_code):
        if country_code not in CountryHelper.countries:
            return {}

        return {
            "name": CountryHelper.countries[country_code]["name"],
            "display_name": CountryHelper.countries[country_code]["display_name"],
            "en_name": CountryHelper.countries[country_code]["en_name"],
            "code": CountryHelper.countries[country_code]["code"],
            "latitude": CountryHelper.countries[country_code]["latitude"],
            "longitude": CountryHelper.countries[country_code]["longitude"],
            "asset": f"./assets/country_flag/{country_code.lower()}.svg",
        }

    # Generated from the countries+states+cities database by
    # scripts/gen_countries.py, which keeps only what HyperDrive uses of it
    COUNTRIES_FILE = "./assets/countries.json"

    def ReadCountriesFile():
        """The countries with their states, and the cities as
        {country: {city: state}}, for finding a city's state"""
        with open(CountryHelper.COUNTRIES_FILE, "rb") as f:
            countries = orjson.loads(f.read())

        cities = {c.get("iso2"): c.pop("cities", None) or {} for c in countries}

        # Each of the ~140k cities holds its own copy of its state's code;
        # sharing one string per code saves ~7MB
        for country_cities in cities.values():
            for city, state in country_cities.items():
                if isinstance(state, str):
                    country_cities[city] = sys.intern(state)

        return countries, cities

    def LoadCountries():
        try:
            # countries_json is only read here, so it isn't kept around
            countries_json, cities = CountryHelper.ReadCountriesFile()

            # Setup countries - states
            for c in countries_json:
                try:
                    # Load display name
                    display_name = c.get("name")

                    if c.get("translations", {}):
                        locale = LocaleHelper.programLocale
                        if locale.replace("_", "-") in c.get("translations", {}):
                            display_name = c.get("translations", {})[locale.replace("_", "-")]
                        elif re.split("-|_", locale)[0] in c.get("translations", {}):
                            display_name = c.get("translations", {})[re.split("-|_", locale)[0]]

                    # Load display name
                    export_name = c["name"]

                    if c.get("translations", {}):
                        locale = LocaleHelper.exportLocale
                        if locale.replace("_", "-") in c.get("translations", {}):
                            export_name = c.get("translations", {})[locale.replace("_", "-")]
                        elif re.split("-|_", locale)[0] in c.get("translations", {}):
                            export_name = c.get("translations", {})[re.split("-|_", locale)[0]]

                    ccode = (
                        c.get("iso2")
                        if not c.get("iso2").isdigit()
                        else "".join([word[0] for word in re.split(r"\s+|-", c.get("name"))])
                    )

                    CountryHelper.countries[c["iso2"]] = {
                        "name": export_name,
                        "display_name": display_name,
                        "en_name": c.get("name"),
                        "code": ccode,
                        "latitude": c.get("latitude"),
                        "longitude": c.get("longitude"),
                        "states": {},
                    }

                    for s in c.get("states", []):
                        if s.get("iso2") is None:
                            continue

                        scode = s.get("iso2")

                        CountryHelper.countries[c["iso2"]]["states"][s["iso2"]] = {
                            "name": s.get("name"),
                            "code": scode,
                            "original_code": s.get("iso2"),
                            "latitude": s.get("latitude"),
                            "longitude": s.get("longitude"),
                        }
                except:
                    pass

            # Setup model
            CountryHelper.countryModel = QStandardItemModel()

            noCountry = QStandardItem()
            noCountry.setData({}, Qt.ItemDataRole.UserRole)
            CountryHelper.countryModel.appendRow(noCountry)

            for i, country_code in enumerate(CountryHelper.countries.keys()):
                item = QStandardItem()
                item.setIcon(QIcon(f"./assets/country_flag/{country_code.lower()}.svg"))
                countryData = CountryHelper.GetBasicCountryInfo(country_code)
                item.setData(countryData, Qt.ItemDataRole.UserRole)
                item.setData(
                    f"{CountryHelper.countries[country_code]['display_name']} / {CountryHelper.countries[country_code]['en_name']} ({country_code})",
                    Qt.ItemDataRole.EditRole,
                )
                CountryHelper.countryModel.appendRow(item)

            # Cities - states for reverse search
            CountryHelper.cities = cities

            CountryHelper.signals.countriesUpdated.emit()

            AdditionalFlags = os.listdir("./user_data/additional_flag")

            AdditionalFlagsFiltered = []
            for flag in AdditionalFlags:
                filename = os.path.basename(flag)
                ext = filename.split(".")[-1]
                #  Remove flags with less than 3 characters
                if len(filename.removesuffix("." + ext)) >= 3:
                    AdditionalFlagsFiltered.append(flag)
            AdditionalFlags = AdditionalFlagsFiltered

            if AdditionalFlags:
                separator = QStandardItem()
                separator.setData(
                    "    " + QApplication.translate("app", "Custom Flags").upper() + "    ",
                    Qt.ItemDataRole.EditRole,
                )
                separator.setEnabled(False)
                separator.setSelectable(False)
                CountryHelper.countryModel.appendRow(separator)

            for flag in AdditionalFlags:
                item = QStandardItem()
                item.setIcon(QIcon(f"./user_data/additional_flag/{flag}"))
                item.setData(
                    {
                        "name": flag[:-4],
                        "display_name": flag[:-4],
                        "en_name": flag[:-4],
                        "code": flag[:-4],
                        "asset": f"./user_data/additional_flag/{flag}",
                    },
                    Qt.ItemDataRole.UserRole,
                )
                item.setData(flag[:-4], Qt.ItemDataRole.EditRole)
                CountryHelper.countryModel.appendRow(item)
        except:
            logger.error(traceback.format_exc())

    def FindState(countryCode, city):
        # State explicit?
        # Normalize parts of city string
        split = city.replace(" - ", ",").split(",")

        # logger.debug(f"Finding State from city string [{city}]")

        for part in split[::-1]:
            part = part.strip()

            state = next(
                (
                    st
                    for st in CountryHelper.countries.get(countryCode, {})
                    .get("states", {})
                    .values()
                    if CountryHelper.remove_accents_lower(st["code"])
                    == CountryHelper.remove_accents_lower(part)
                ),
                None,
            )
            if state is None:
                state = next(
                    (
                        st
                        for st in CountryHelper.countries.get(countryCode, {})
                        .get("states", {})
                        .values()
                        if CountryHelper.remove_accents_lower(st["name"])
                        == CountryHelper.remove_accents_lower(part)
                    ),
                    None,
                )
            if state is not None:
                # logger.debug(
                #     f"State was explicit: [{city}] -> [{part}] = {state}")
                return state["original_code"]

        # No, so get by City
        for part in split[::-1]:
            part = part.strip()

            state = CountryHelper.cities.get(countryCode, {}).get(
                CountryHelper.remove_accents_lower(part), None
            )

            if state is not None:
                # logger.debug(f"Got state from city name: [{city}] -> [{part}] = {state}")
                return state

        return None

    def GetStates(country_code: str):
        """Returns the states for a country code, or None if the country cannot be found"""

        country_data = CountryHelper.countries.get(country_code)
        if country_data:
            return country_data.get("states") or {}

        return None

    def GetCities(country_code: str, state_code: str):
        """Returns the cities for a country+state code, or None if the state can't be found"""

        states = CountryHelper.get_states(country_code)
        if not states:
            return None

        state = states.get(state_code, None)
        if not state:
            return None

        return state.cities


CountryHelper.instance = CountryHelper()
