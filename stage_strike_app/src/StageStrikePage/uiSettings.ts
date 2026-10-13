const STORAGE_KEY = "hd_stage_strike_ui_v2";

export interface UiSettings {
  askCharacters: boolean;
}

const DEFAULTS: UiSettings = {
  // Open the character select once each game's winner is reported
  askCharacters: true,
};

export function loadUiSettings(): UiSettings {
  try {
    return {...DEFAULTS, ...JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}")};
  } catch {
    return {...DEFAULTS};
  }
}

export function saveUiSettings(settings: UiSettings) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  } catch {}
  return settings;
}
