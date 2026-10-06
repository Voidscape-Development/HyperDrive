const STORAGE_KEY = "hd_stage_strike_ui_v2";

const DEFAULTS = {
  // Open the character select once each game's winner is reported
  askCharacters: true,
};

export function loadUiSettings() {
  try {
    return {...DEFAULTS, ...JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}")};
  } catch {
    return {...DEFAULTS};
  }
}

export function saveUiSettings(settings) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  } catch {}
  return settings;
}
