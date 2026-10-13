import {useId, useState} from "react";
import {Languages} from "lucide-react";
import i18n, {SUPPORTED_LANGUAGES} from "../i18n/config";
import {languageSettings, saveLanguageSettings} from "./languageSettings";
import {Label} from "@/components/ui/label";
import {Select, SelectContent, SelectItem, SelectTrigger, SelectValue} from "@/components/ui/select";
import {Switch} from "@/components/ui/switch";

function resolveCode(lang: string) {
  if (SUPPORTED_LANGUAGES.find(l => l.code === lang)) return lang;
  const short = lang.split(/[-_]/)[0];
  return SUPPORTED_LANGUAGES.find(l => l.code === short)?.code ?? "en";
}

interface LanguageSelectorProps {
  playerLanguages: string[];
  currPlayer: number;
  selectedStage: string | null;
}

export function LanguageSelector({playerLanguages, currPlayer, selectedStage}: LanguageSelectorProps) {
  const [settings, setSettings] = useState(() => ({...languageSettings}));
  const autoId = useId();

  const isSharedStep = selectedStage !== null || currPlayer === -1;
  const autoLang = (!isSharedStep && currPlayer >= 0)
    ? resolveCode(playerLanguages?.[currPlayer] ?? settings.language)
    : resolveCode(settings.language);

  const displayLang = settings.usePlayerLanguage ? autoLang : resolveCode(settings.language);

  const handleLangChange = (lang: string) => {
    setSettings({...settings, language: lang});
    saveLanguageSettings({language: lang});
    if (!settings.usePlayerLanguage) i18n.changeLanguage(lang);
  };

  const handleAutoToggle = (usePlayer: boolean) => {
    setSettings({...settings, usePlayerLanguage: usePlayer});
    saveLanguageSettings({usePlayerLanguage: usePlayer});
    i18n.changeLanguage(usePlayer ? autoLang : resolveCode(settings.language));
  };

  return <div className="flex items-center gap-2">
    <Select value={displayLang} onValueChange={handleLangChange} disabled={settings.usePlayerLanguage}>
      <SelectTrigger size="sm" className="gap-1.5" aria-label="Language">
        <Languages />
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {SUPPORTED_LANGUAGES.map(l => (
          <SelectItem key={l.code} value={l.code}>{l.label}</SelectItem>
        ))}
      </SelectContent>
    </Select>
    <div className="flex items-center gap-1.5">
      <Switch id={autoId} size="sm" checked={settings.usePlayerLanguage} onCheckedChange={handleAutoToggle} />
      <Label htmlFor={autoId} className="text-xs font-normal text-muted-foreground">Auto</Label>
    </div>
  </div>;
}
