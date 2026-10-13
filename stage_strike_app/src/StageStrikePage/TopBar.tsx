import {Gamepad2, Settings} from "lucide-react";
import i18n from "../i18n/config";
import {LanguageSelector} from "./LanguageSelector";
import {Badge} from "@/components/ui/badge";
import {Button} from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {Label} from "@/components/ui/label";
import {Select, SelectContent, SelectItem, SelectTrigger, SelectValue} from "@/components/ui/select";
import {Switch} from "@/components/ui/switch";
import {Tooltip, TooltipContent, TooltipTrigger} from "@/components/ui/tooltip";
import {cn} from "@/lib/utils";
import type {UiSettings} from "./uiSettings";

export interface ScoreboardOption {
  number: number;
  name: string;
}

interface TopBarProps {
  scoreboard: number;
  scoreboards: ScoreboardOption[];
  onScoreboardChange: (scoreboard: number) => void;
  teamName?: string | null;
  teamPlayer: number;
  connected: boolean;
  playerLanguages: string[];
  currPlayer: number;
  selectedStage: string | null;
  uiSettings?: UiSettings;
  onUiSettingsChange?: (changes: Partial<UiSettings>) => void;
  // The page's name, "Stage Strike" by default
  title?: string;
}

export function TopBar({
  scoreboard,
  scoreboards,
  onScoreboardChange,
  teamName,
  teamPlayer,
  connected,
  playerLanguages,
  currPlayer,
  selectedStage,
  uiSettings,
  onUiSettingsChange,
  title,
}: TopBarProps) {
  // Keeps the current scoreboard listed while the list loads
  const options = scoreboards.length > 0
    ? scoreboards
    : [{number: scoreboard, name: i18n.t("scoreboard_n", {value: scoreboard})}];

  const languageSelector = <LanguageSelector
    playerLanguages={playerLanguages}
    currPlayer={currPlayer}
    selectedStage={selectedStage}
  />;

  return <header className="flex shrink-0 items-center gap-3 border-b bg-background/80 px-4 py-2 backdrop-blur">
    <div className="flex min-w-0 items-center gap-2">
      <Gamepad2 className="size-5 shrink-0 text-muted-foreground" />
      <h1 className="hidden truncate text-base font-semibold tracking-tight sm:block">
        {title ?? i18n.t("title")}
      </h1>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            role="status"
            aria-label={connected ? i18n.t("connected") : i18n.t("connecting")}
            className={cn(
              "size-2 shrink-0 rounded-full",
              connected ? "bg-pick" : "animate-pulse bg-ban",
            )}
          />
        </TooltipTrigger>
        <TooltipContent>{connected ? i18n.t("connected") : i18n.t("connecting")}</TooltipContent>
      </Tooltip>
    </div>

    {teamName &&
      <Badge
        className={cn(
          "hidden max-w-[30vw] truncate text-zinc-950 sm:inline-flex",
          teamPlayer === 0 ? "bg-p1" : "bg-p2",
        )}
      >
        {i18n.t("team_view", {team: teamName})}
      </Badge>
    }

    <div className="ml-auto flex items-center gap-2">
      <Select
        value={options.some((s) => s.number === scoreboard) ? String(scoreboard) : undefined}
        onValueChange={(value) => onScoreboardChange(Number(value))}
      >
        <SelectTrigger size="sm" className="min-w-36 max-w-[40vw]" aria-label={i18n.t("scoreboard")}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {options.map((s) =>
            <SelectItem key={s.number} value={String(s.number)}>{s.name}</SelectItem>
          )}
        </SelectContent>
      </Select>

      <div className="hidden sm:block">{languageSelector}</div>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon" aria-label={i18n.t("settings")}>
            <Settings />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-72">
          <div className="p-2 sm:hidden">{languageSelector}</div>
          {uiSettings && <>
            <DropdownMenuLabel>{i18n.t("settings")}</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <div className="flex items-center justify-between gap-3 px-2 py-1.5">
              <Label htmlFor="ss-ask-characters" className="font-normal">
                {i18n.t("auto_ask_characters")}
              </Label>
              <Switch
                id="ss-ask-characters"
                checked={uiSettings.askCharacters}
                onCheckedChange={(checked) => onUiSettingsChange?.({askCharacters: checked})}
              />
            </div>
          </>}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  </header>;
}
