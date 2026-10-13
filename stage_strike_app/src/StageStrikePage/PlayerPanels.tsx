import {Check, Hourglass} from "lucide-react";
import i18n from "../i18n/config";
import {cn} from "@/lib/utils";
import {CharacterIcon, CharacterName, FindCharacter, type Characters} from "./characterAssets";
import {PLAYER_BG, PLAYER_TEXT, PLAYER_VAR} from "./playerColors";
import type {CharacterSelect, StrikeTeam} from "./useHdData";

function TeamCharacters({team, characters, alignEnd}: {team: StrikeTeam; characters: Characters; alignEnd: boolean}) {
  const icons = [];
  (team?.players ?? []).forEach((player) => {
    (player.characters ?? []).forEach((selection, i) => {
      const character = FindCharacter(characters, selection);
      const icon = CharacterIcon(character, selection?.skin ?? 0);
      if (icon) {
        icons.push(<img
          key={`${player.player}-${i}`}
          src={icon}
          alt={CharacterName(character)}
          title={CharacterName(character)}
          className="size-7 object-contain"
        />);
      }
    });
  });
  if (icons.length === 0) return null;
  return <div className={cn("flex gap-1", alignEnd && "justify-end")}>{icons}</div>;
}

type CharacterStatus = "ready" | "picking" | null;

interface PlayerPanelProps {
  index: number;
  name: string;
  team: StrikeTeam;
  characters: Characters;
  wins: number;
  active: boolean;
  isMe: boolean;
  characterStatus: CharacterStatus;
}

function PlayerPanel({index, name, team, characters, wins, active, isMe, characterStatus}: PlayerPanelProps) {
  const right = index === 1;
  return <div
    className={cn(
      "relative flex min-w-0 items-center gap-3 rounded-xl border bg-card px-4 py-2.5 text-card-foreground shadow-sm transition-shadow sm:gap-4",
      PLAYER_VAR[index],
      right && "flex-row-reverse text-right",
      active && "ss-turn border-transparent",
    )}
  >
    <span className={cn("absolute inset-y-2 w-1 rounded-full", PLAYER_BG[index], right ? "right-1.5" : "left-1.5")} />
    <div className={cn("flex min-w-0 flex-1 flex-col gap-1 pl-1", right && "items-end pr-1 pl-0")}>
      <div className="max-w-full truncate text-[clamp(16px,2.4vw,24px)] leading-tight font-semibold" title={name}>
        {name}
      </div>
      <TeamCharacters team={team} characters={characters} alignEnd={right} />
      {characterStatus &&
        <span className={cn(
          "inline-flex items-center gap-1 text-xs font-medium",
          characterStatus === "ready" ? "text-pick" : "text-warning",
        )}>
          {characterStatus === "ready" ? <Check className="size-3.5" /> : <Hourglass className="size-3.5" />}
          {i18n.t(characterStatus === "ready" ? "characters_ready" : "picking_characters")}
        </span>
      }
    </div>
    <div className={cn("text-[clamp(32px,6vw,52px)] leading-none font-bold tabular-nums", PLAYER_TEXT[index])}>
      {wins}
    </div>
    {(active || isMe) &&
      <span className={cn(
        "absolute -top-2.5 rounded-full px-2 py-px text-[11px] font-semibold tracking-wider text-zinc-950 uppercase",
        PLAYER_BG[index],
        right ? "right-4" : "left-4",
      )}>
        {[isMe && i18n.t("you"), active && i18n.t("turn")].filter(Boolean).join(" · ")}
      </span>
    }
  </div>;
}

interface PlayerPanelsProps {
  playerNames: string[];
  teams: StrikeTeam[];
  characters: Characters;
  wins: number[];
  currPlayer: number;
  myPlayer: number;
  characterSelect: CharacterSelect;
  currGame: number;
  bestOf: number;
  phase?: string;
  match?: string;
}

export function PlayerPanels({
  playerNames, teams, characters, wins, currPlayer, myPlayer, characterSelect, currGame, bestOf, phase, match,
}: PlayerPanelsProps) {
  const setInfo = [phase, match].filter(Boolean).join(" · ");
  // Who already sent their characters for the next game, not what they picked
  const characterStatus = (index: number): CharacterStatus => {
    if (!characterSelect?.active || !teams?.[index]) return null;
    return characterSelect.submitted?.[String(teams[index].team)] ? "ready" : "picking";
  };

  const panel = (index: number) => <PlayerPanel
    index={index}
    name={playerNames[index]}
    team={teams?.[index]}
    characters={characters}
    wins={wins[index]}
    active={currPlayer === index}
    isMe={myPlayer === index}
    characterStatus={characterStatus(index)}
  />;

  return <div className="grid grid-cols-2 items-stretch gap-3 sm:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)]">
    {panel(0)}
    <div className="col-span-2 row-start-1 flex min-w-0 flex-row items-center justify-center gap-2 px-2 sm:col-span-1 sm:col-start-2 sm:max-w-[30vw] sm:flex-col sm:gap-0">
      {setInfo &&
        <div className="max-w-full truncate text-xs tracking-wide text-muted-foreground uppercase">{setInfo}</div>
      }
      <div className="text-[clamp(16px,2.4vw,22px)] font-semibold whitespace-nowrap">
        {i18n.t("game", {value: currGame + 1})}
      </div>
      {bestOf > 0 &&
        <div className="text-xs whitespace-nowrap text-muted-foreground">
          {i18n.t("best_of", {value: bestOf})}
        </div>
      }
    </div>
    {panel(1)}
  </div>;
}
