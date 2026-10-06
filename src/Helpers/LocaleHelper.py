import json
import os
import traceback

from loguru import logger
from qtpy import QtCore
from qtpy.QtCore import *
from qtpy.QtGui import *

from src.SettingsManager import SettingsManager

from .DictHelper import deep_clone
from .DirHelper import ResolvePath

# The romanizers are imported when first used: pypinyin alone takes ~40MB


class LocaleHelperSignals(QObject):
    localeChanged = Signal()


class LocaleHelper(QObject):
    exportLocale = "en-US"
    programLocale = "en-US"
    fgTermLocale = "en-US"
    matchNames = {}
    phaseNames = {}
    translator = None
    languages = []
    remapping = {}
    countryToLanguage = {}
    countryToContinent = {}
    # Creating a Cutlet loads the whole MeCab dictionary, so it's done once
    cutletInstance = None

    def LoadLocale():
        settingsProgramLocale = SettingsManager.Get("program_language", None)
        settingsExportLocale = SettingsManager.Get("game_asset_language", None)
        settingsFgTerm = SettingsManager.Get("fg_term_language", None)

        if settingsProgramLocale and settingsProgramLocale != "default":
            current_locale = [settingsProgramLocale]
        else:
            current_locale = QtCore.QLocale().uiLanguages()

        logger.info("OS locale: " + str(current_locale))

        oldTranslator = LocaleHelper.translator
        i18n_dir = ResolvePath("src/i18n")

        if oldTranslator:
            QGuiApplication.instance().removeTranslator(oldTranslator)

        LocaleHelper.translator = QTranslator()
        localeFound = False
        for locale in current_locale:
            if localeFound:
                break
            for f in os.listdir(f"{i18n_dir}/"):
                if f.endswith(".qm"):
                    lang = f.split("_", 1)[1].split(".")[0]
                    if lang == locale:
                        LocaleHelper.translator.load(QLocale(lang), f"{i18n_dir}/{f}")
                        LocaleHelper.programLocale = locale
                        localeFound = True
                        break
                    elif lang == locale.split("-")[0]:
                        LocaleHelper.translator.load(QLocale(lang), f"{i18n_dir}/{f}")
                        LocaleHelper.programLocale = locale
                        localeFound = True
                        break

        QGuiApplication.instance().installTranslator(LocaleHelper.translator)

        if settingsExportLocale and settingsExportLocale != "default":
            LocaleHelper.exportLocale = settingsExportLocale
        else:
            LocaleHelper.exportLocale = current_locale[0]

        if settingsFgTerm and settingsFgTerm != "default":
            LocaleHelper.fgTermLocale = settingsFgTerm
        else:
            LocaleHelper.fgTermLocale = current_locale[0]

    def LoadLanguages():
        try:
            i18n_dir = ResolvePath("src/i18n")
            languages_json = json.load(open(f"{i18n_dir}/mapping.json", encoding="utf-8"))
            LocaleHelper.languages = languages_json.get("languages")
            LocaleHelper.remapping = languages_json.get("remapping")
        except Exception as e:
            raise Exception("Error loading languages") from e

    def LoadCountryToLanguage():
        try:
            languages_json = json.load(open("./assets/data_countries.json", encoding="utf-8"))
            LocaleHelper.countryToLanguage = {
                ccode: cdata.get("languages") for ccode, cdata in languages_json.items()
            }
            LocaleHelper.countryToContinent = {
                ccode: cdata.get("continent") for ccode, cdata in languages_json.items()
            }
        except Exception as e:
            raise Exception("Error loading languages") from e

    def GetCountrySpokenLanguages(countryCode2: str):
        return LocaleHelper.countryToLanguage.get(countryCode2.upper(), [])

    def GetCountryContinent(countryCode2: str):
        return LocaleHelper.countryToContinent.get(countryCode2.upper(), "")

    def RomanizeTextFromCountry(text, countryCode2: str):
        romanized_text = text
        if romanized_text:
            languages = LocaleHelper.GetCountrySpokenLanguages(countryCode2)
            if "ja" in languages:
                if LocaleHelper.cutletInstance is None:
                    import cutlet

                    LocaleHelper.cutletInstance = cutlet.Cutlet()
                romanized_text = LocaleHelper.cutletInstance.romaji(text)
            elif "zh" in languages:
                from pypinyin import pinyin

                pinyin_text = pinyin(text)
                romanized_text = ""
                for pinyin_character in pinyin_text:
                    romanized_text = romanized_text + pinyin_character[0]
            elif "ko" in languages:
                import koroman

                romanized_text = koroman.romanize(text)
            elif "ar" in languages:
                from arabic_buckwalter_transliteration.transliteration import arabic_to_buckwalter

                romanized_text = arabic_to_buckwalter(text)
        return romanized_text

    def LoadRoundNames():
        # Load default round names and translation
        try:
            tterm_dir = ResolvePath("./src/i18n/tournament_term")
            original_term_names: dict = json.load(open(f"{tterm_dir}/en.json", encoding="utf-8"))
            term_names = deep_clone(original_term_names)

            for f in os.listdir(f"{tterm_dir}/"):
                if f.endswith(".json"):
                    lang = f.split(".")[0]

                    if lang == LocaleHelper.fgTermLocale:
                        # We found the exact language file
                        translatedRoundNames = json.load(open(f"{tterm_dir}/{f}", encoding="utf-8"))
                        term_names = original_term_names.copy()
                        term_names.update(translatedRoundNames)
                        break
                    elif lang == LocaleHelper.fgTermLocale.split("-")[0]:
                        # We found a more generic language file
                        # Good enough if we don't find a specific one
                        translatedRoundNames = json.load(open(f"{tterm_dir}/{f}", encoding="utf-8"))
                        term_names = original_term_names.copy()
                        term_names.update(translatedRoundNames)

            LocaleHelper.matchNames = term_names.get("match")
            LocaleHelper.phaseNames = term_names.get("phase")
        except:
            logger.error(traceback.format_exc())

        # Load user round names in a separate try/catch
        try:
            term_names: dict = json.load(
                open("./user_data/tournament_terms.json", encoding="utf-8")
            )

            term_names["phase"] = {k: v for k, v in term_names.get("phase", {}).items() if v}
            term_names["match"] = {k: v for k, v in term_names.get("match", {}).items() if v}

            LocaleHelper.phaseNames.update(term_names["phase"])
            LocaleHelper.matchNames.update(term_names["match"])
        except:
            logger.warning("Custom Tournament Terms were not found and/or loaded.")

    def GetRemaps(language: str):
        for remap, langs in LocaleHelper.remapping.items():
            if language.replace("-", "_") in langs:
                logger.info("Loaded remap: " + str(remap))
                return remap
        return None

    def LoadPhaseNamesToWidget(widget):
        for key in dict(sorted(LocaleHelper.phaseNames.items(), key=lambda item: item[1])).keys():
            phaseString = LocaleHelper.phaseNames[key]

            if "{0}" in phaseString:
                if "top" not in key:
                    for letter in ["A", "B", "C", "D"]:
                        if widget.findText(phaseString.format(letter)) < 0:
                            widget.addItem(phaseString.format(letter))
            else:
                if widget.findText(phaseString) < 0:
                    widget.addItem(phaseString)

    def LoadMatchNamesToWidget(widget):
        for key in dict(sorted(LocaleHelper.matchNames.items(), key=lambda item: item[1])).keys():
            matchString = LocaleHelper.matchNames[key]
            try:
                if "{0}" in matchString and ("qualifier" in key):
                    # Generate preset qualifier names
                    couples = [
                        (
                            LocaleHelper.phaseNames.get("top_n").format(8),
                            LocaleHelper.matchNames.get("qualifier_winners_indicator"),
                        ),
                        (
                            LocaleHelper.phaseNames.get("top_n").format(16),
                            LocaleHelper.matchNames.get("qualifier_winners_indicator"),
                        ),
                        (
                            LocaleHelper.phaseNames.get("top_n").format(32),
                            LocaleHelper.matchNames.get("qualifier_winners_indicator"),
                        ),
                        (
                            LocaleHelper.phaseNames.get("top_n").format(6),
                            LocaleHelper.matchNames.get("qualifier_losers_indicator"),
                        ),
                        (
                            LocaleHelper.phaseNames.get("top_n").format(8),
                            LocaleHelper.matchNames.get("qualifier_losers_indicator"),
                        ),
                        (
                            LocaleHelper.phaseNames.get("top_n").format(12),
                            LocaleHelper.matchNames.get("qualifier_losers_indicator"),
                        ),
                        (
                            LocaleHelper.phaseNames.get("top_n").format(16),
                            LocaleHelper.matchNames.get("qualifier_losers_indicator"),
                        ),
                        (
                            LocaleHelper.phaseNames.get("top_n").format(24),
                            LocaleHelper.matchNames.get("qualifier_losers_indicator"),
                        ),
                        (
                            LocaleHelper.phaseNames.get("top_n").format(32),
                            LocaleHelper.matchNames.get("qualifier_losers_indicator"),
                        ),
                    ]

                    for couple in couples:
                        # logger.info(couple)
                        widget.addItem(matchString.format(*couple))
                elif "{0}" in matchString and ("qualifier" not in key):
                    for number in range(5):
                        if key == "best_of":
                            if widget.findText(matchString.format(str(2 * number + 1))) < 0:
                                widget.addItem(matchString.format(str(2 * number + 1)))
                        else:
                            if widget.findText(matchString.format(str(number + 1))) < 0:
                                widget.addItem(matchString.format(str(number + 1)))
                elif "indicator" in key:
                    pass
                else:
                    if widget.findText(matchString) < 0:
                        widget.addItem(matchString)
            except:
                logger.error(f"Unable to generate match strings for {matchString}")


LocaleHelper.LoadLanguages()
LocaleHelper.LoadCountryToLanguage()
