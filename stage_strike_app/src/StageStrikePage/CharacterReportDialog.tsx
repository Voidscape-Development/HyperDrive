import {type ReactNode, useEffect, useMemo, useState} from "react";
import {ArrowLeft, CircleCheck, Plus, Search, X} from "lucide-react";
import {toast} from "sonner";
import i18n from "../i18n/config";
import {ReportCharacters, type StrikeTarget} from "./postActions";
import {CharacterIcon, CharacterName, FindCharacter, type Character, type Characters} from "./characterAssets";
import type {CharacterSelect, StrikeTeam, StrikeTeamPlayer} from "./useHdData";
import {Alert, AlertDescription} from "@/components/ui/alert";
import {Button} from "@/components/ui/button";
import {Card} from "@/components/ui/card";
import {Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle} from "@/components/ui/dialog";
import {Input} from "@/components/ui/input";
import {cn} from "@/lib/utils";
import {PLAYER_TEXT, PLAYER_VAR} from "./playerColors";

interface Slot {
  en_name: string;
  skin: number;
}

type Selections = Record<string, (Slot | null)[]>;

/** {team: {player: [[character en_name, skin], ...]}} */
export type CharacterPicks = Record<string, Record<string, [string, number][]>>;

const slotKey = (team: StrikeTeam, player: StrikeTeamPlayer) => `${team.team}-${player.player}`;

/** Whether any player has fewer characters set than HyperDrive's character count */
export function MissingCharacters(teams: StrikeTeam[], charactersPerPlayer: number) {
  const count = charactersPerPlayer ?? 1;
  return (teams ?? []).some((team) => (team?.players ?? []).some((player) => {
    for (let i = 0; i < count; i += 1) {
      if (!player.characters?.[i]) return true;
    }
    return false;
  }));
}

function initialSelections(teams: StrikeTeam[], characters: Characters, count: number) {
  const selections: Selections = {};
  (teams ?? []).forEach((team) => {
    (team?.players ?? []).forEach((player) => {
      const slots: (Slot | null)[] = [];
      for (let i = 0; i < count; i += 1) {
        const current = player.characters?.[i];
        const character = FindCharacter(characters, current);
        slots.push(character ? {en_name: character.en_name, skin: current.skin ?? 0} : null);
      }
      selections[slotKey(team, player)] = slots;
    });
  });
  return selections;
}

/** A character box: an icon and a name, in a team's color once picked */
export function CharacterSlot({character, skin, onClick, onClear, label, highlight}: {
  character: Character | null;
  skin: number;
  onClick?: () => void;
  onClear?: () => void;
  label?: string;
  highlight?: boolean;
}) {
  const icon = character ? CharacterIcon(character, skin) : null;
  const body = <>
    {icon
      ? <img src={icon} alt="" className="size-12 object-contain" />
      : <Plus className="size-9 opacity-60" />
    }
    <span className="max-w-full truncate text-xs">{character ? CharacterName(character) : label}</span>
  </>;
  const box = cn(
    "flex min-h-24 w-full flex-col items-center justify-center gap-1 rounded-lg border-2 bg-black/20 p-2",
    character ? "border-(--color)" : "border-dashed border-foreground/25",
    highlight && "border-warning",
  );

  return <div className="relative">
    {onClick
      ? <button
        type="button"
        className={cn(box, "cursor-pointer transition-colors outline-none hover:bg-accent focus-visible:ring-[3px] focus-visible:ring-ring/50")}
        onClick={onClick}
        aria-label={label}
      >
        {body}
      </button>
      : <div className={box}>{body}</div>
    }
    {character && onClear &&
      <Button
        variant="ghost"
        size="icon-xs"
        className="absolute top-1 right-1"
        aria-label={i18n.t("clear")}
        onClick={onClear}
      >
        <X />
      </Button>
    }
  </div>;
}

function CharacterPicker({characters, current, onPick, onPickSkin}: {
  characters: Characters;
  current: Slot | null;
  onPick: (character: Character) => void;
  onPickSkin: (skin: number) => void;
}) {
  const [search, setSearch] = useState("");
  const list = useMemo(() => Object.values(characters)
    .filter((c) => !search || CharacterName(c).toLowerCase().includes(search.toLowerCase())
      || c.en_name.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => CharacterName(a).localeCompare(CharacterName(b))), [characters, search]);

  const currentCharacter = current ? characters[current.en_name] : null;
  const skins = currentCharacter?.skins ?? [];

  return <div className="flex flex-col gap-3">
    {currentCharacter && skins.length > 1 &&
      <div className="flex flex-col gap-1.5">
        <span className="text-xs font-medium tracking-wider text-muted-foreground uppercase">
          {i18n.t("color")} · {CharacterName(currentCharacter)}
        </span>
        <div className="flex flex-wrap gap-1.5">
          {skins.map((_, i) =>
            <button
              type="button"
              key={i}
              className={cn(
                "flex size-14 cursor-pointer items-center justify-center rounded-lg border-2 bg-black/25 transition-colors hover:bg-accent",
                current.skin === i && "border-pick shadow-[0_0_8px] shadow-pick/60",
              )}
              onClick={() => onPickSkin(i)}
              aria-label={`${i18n.t("color")} ${i + 1}`}
            >
              <img src={CharacterIcon(currentCharacter, i)} alt="" className="size-11 object-contain" />
            </button>
          )}
        </div>
      </div>
    }
    <div className="relative">
      <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
      <Input
        autoFocus
        className="pl-8"
        placeholder={i18n.t("search")}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />
    </div>
    <div className="grid grid-cols-[repeat(auto-fill,minmax(88px,1fr))] gap-1.5">
      {list.map((c) =>
        <button
          type="button"
          key={c.en_name}
          className={cn(
            "flex cursor-pointer flex-col items-center gap-1 rounded-lg border-2 border-transparent bg-muted/40 px-1 py-2 transition-colors hover:bg-accent",
            current?.en_name === c.en_name && "border-pick",
          )}
          onClick={() => onPick(c)}
        >
          <img src={CharacterIcon(c, 0)} alt="" loading="lazy" className="size-12 object-contain" />
          <span className="max-w-full truncate text-xs">{CharacterName(c)}</span>
        </button>
      )}
    </div>
  </div>;
}

/** Each team's players and their characters, in the team's color */
export function TeamColumns({children}: {children: ReactNode}) {
  return <div className="grid grid-cols-[repeat(auto-fit,minmax(260px,1fr))] gap-4">{children}</div>;
}

export function TeamColumn({index, name, children}: {index: number; name: string; children: ReactNode}) {
  return <div className={cn("flex flex-col gap-3 rounded-lg border border-t-4 border-t-(--color) bg-muted/30 p-3", PLAYER_VAR[index])}>
    <div className={cn("truncate text-lg font-bold", PLAYER_TEXT[index])}>{name}</div>
    {children}
  </div>;
}

export function PlayerSlots({name, children}: {name?: string; children: ReactNode}) {
  return <div>
    {name && <div className="mb-1 truncate text-sm font-semibold">{name}</div>}
    <div className="grid grid-cols-[repeat(auto-fill,minmax(96px,1fr))] gap-2">{children}</div>
  </div>;
}

interface CharacterReportDialogProps {
  open?: boolean;
  onClose?: () => void;
  target: StrikeTarget;
  myPlayer: number;
  characterSelect: CharacterSelect;
  game: string;
  teams: StrikeTeam[];
  charactersPerPlayer: number;
  playerNames: string[];
  characters: Characters;
  // Shown in the page instead of a dialog (the character select page)
  inline?: boolean;
  // Sends the picks
  report?: (target: StrikeTarget, characters: CharacterPicks) => Promise<Response>;
  title?: string;
  // Called after the picks were sent
  onSent?: () => void;
}

export function CharacterReportDialog({
  open,
  onClose,
  target,
  myPlayer,
  characterSelect,
  game,
  teams,
  charactersPerPlayer,
  playerNames,
  characters,
  inline = false,
  report = ReportCharacters,
  title,
  onSent,
}: CharacterReportDialogProps) {
  if (inline) open = true;
  const count = Math.max(1, charactersPerPlayer ?? 1);
  const [selections, setSelections] = useState<Selections>({});
  const [edited, setEdited] = useState(false);
  const [picking, setPicking] = useState<{key: string; slot: number; name?: string} | null>(null);
  const [sending, setSending] = useState(false);

  // Follows HyperDrive until something is changed here
  useEffect(() => {
    if (open && !edited) {
      setSelections(initialSelections(teams, characters, count));
    }
  }, [open, edited, teams, characters, count]);

  useEffect(() => {
    if (!open) {
      setEdited(false);
      setPicking(null);
    }
  }, [open]);

  const setSlot = (key: string, slot: number, value: Slot | null) => {
    setEdited(true);
    setSelections((prev) => {
      const slots = [...(prev[key] ?? Array(count).fill(null))];
      slots[slot] = value;
      return {...prev, [key]: slots};
    });
  };

  // A page for one team only sees and sends its own team's characters
  const teamMode = myPlayer !== undefined && myPlayer !== -1;
  const visibleTeams = (teams ?? []).map((team, t) =>
    (!teamMode || t === myPlayer) ? team : null);
  const players = visibleTeams.flatMap((team, t) =>
    (team?.players ?? []).map((player) => ({team, player, t})));
  const complete = players.length > 0 && players.every(({team, player}) =>
    (selections[slotKey(team, player)] ?? []).slice(0, count).every((s) => !!s)
    && (selections[slotKey(team, player)] ?? []).length >= count);

  const selectActive = !!characterSelect?.active;
  const mySubmitted = teamMode && selectActive
    && !!characterSelect.submitted?.[String(teams?.[myPlayer]?.team)];
  const otherTeam = teamMode ? teams?.[(myPlayer + 1) % 2] : null;
  const otherName = otherTeam ? (otherTeam.name || playerNames[(myPlayer + 1) % 2]) : null;

  const send = async (keepCurrent: boolean) => {
    // Keeping the characters sends what the scoreboard has
    const source = keepCurrent ? initialSelections(teams, characters, count) : selections;
    const payload: CharacterPicks = {};
    players.forEach(({team, player}) => {
      payload[String(team.team)] ??= {};
      payload[String(team.team)][String(player.player)] = (source[slotKey(team, player)] ?? [])
        .slice(0, count)
        .filter((s) => !!s)
        .map((s) => [s.en_name, s.skin]);
    });

    setSending(true);
    try {
      const response = await report(target, payload);
      if (response.ok) {
        // The other team's characters are still missing
        const waiting = teamMode && !characterSelect?.submitted?.[String(otherTeam?.team)];
        if (waiting) toast.success(i18n.t("characters_waiting", {team: otherName}));
        else toast.success(i18n.t("characters_sent"));
        setEdited(false);
        onSent?.();
        onClose?.();
      } else if (response.status === 409) {
        // Already picked for this score (character select page)
        toast.warning(i18n.t("characters_locked_short"));
      } else {
        toast.error(i18n.t("characters_failed"));
      }
    } catch (e) {
      console.error(e);
      toast.error(i18n.t("characters_failed"));
    } finally {
      setSending(false);
    }
  };

  let content;
  if (picking) {
    const current = selections[picking.key]?.[picking.slot] ?? null;
    content = <CharacterPicker
      characters={characters}
      current={current}
      onPick={(c) => {
        const skin = current?.en_name === c.en_name ? current.skin : 0;
        setSlot(picking.key, picking.slot, {en_name: c.en_name, skin});
        // Characters with colors stay open to pick one
        if ((c.skins ?? []).length <= 1) setPicking(null);
      }}
      onPickSkin={(skin) => {
        setSlot(picking.key, picking.slot, {...current, skin});
        setPicking(null);
      }}
    />;
  } else if (players.length === 0 || Object.keys(characters).length === 0) {
    content = <p className="text-sm text-muted-foreground">{i18n.t("no_players")}</p>;
  } else {
    content = <div className="flex flex-col gap-3">
      {mySubmitted &&
        <Alert className="border-pick/40 text-pick">
          <CircleCheck />
          <AlertDescription className="text-pick/90">{i18n.t("characters_waiting", {team: otherName})}</AlertDescription>
        </Alert>
      }
      <p className="text-sm text-muted-foreground">
        {i18n.t(teamMode ? "select_characters_hint_team" : "select_characters_hint", {count})}
      </p>
      <TeamColumns>
        {visibleTeams.map((team, t) => team &&
          <TeamColumn key={t} index={t} name={team.name || playerNames[t]}>
            {(team.players ?? []).map((player) => {
              const key = slotKey(team, player);
              return <PlayerSlots
                key={key}
                name={(team.players.length > 1 || team.name)
                  ? player.name || i18n.t("player_n", {value: player.player})
                  : undefined}
              >
                {Array.from({length: count}).map((_, slot) => {
                  const selection = selections[key]?.[slot];
                  const character = selection ? characters[selection.en_name] : null;
                  return <CharacterSlot
                    key={slot}
                    character={character}
                    skin={selection?.skin ?? 0}
                    label={count > 1 ? i18n.t("character_n", {value: slot + 1}) : i18n.t("character")}
                    highlight={!character}
                    onClick={() => setPicking({key, slot, name: player.name})}
                    onClear={() => setSlot(key, slot, null)}
                  />;
                })}
              </PlayerSlots>;
            })}
          </TeamColumn>
        )}
      </TeamColumns>
    </div>;
  }

  const titleText = picking
    ? `${i18n.t("pick_character")}${picking.name ? ` · ${picking.name}` : ""}`
    : title ?? (selectActive
      ? i18n.t("characters_for_game", {value: (characterSelect.game ?? 0) + 1})
      : i18n.t("report_characters"));

  const backButton = picking &&
    <Button variant="ghost" size="icon-sm" aria-label={i18n.t("back")} onClick={() => setPicking(null)}>
      <ArrowLeft />
    </Button>;

  const actions = picking
    ? <Button variant="outline" onClick={() => setPicking(null)}>{i18n.t("done")}</Button>
    : <>
      {!inline && <Button variant="ghost" onClick={onClose}>{i18n.t("cancel")}</Button>}
      <Button
        variant="outline"
        disabled={sending || !game || players.length === 0}
        onClick={() => send(true)}
      >
        {i18n.t("keep_characters")}
      </Button>
      <Button
        className="bg-pick text-zinc-950 hover:bg-pick/90"
        disabled={!complete || sending || !game}
        onClick={() => send(false)}
      >
        {i18n.t("send_to_hd")}
      </Button>
    </>;

  if (inline) {
    return <Card className="gap-4 p-4">
      <div className="flex items-center gap-2">
        {backButton}
        <h2 className="min-w-0 flex-1 truncate text-lg font-semibold">{titleText}</h2>
      </div>
      {content}
      <div className="flex flex-wrap justify-end gap-2">{actions}</div>
    </Card>;
  }

  return <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose?.()}>
    <DialogContent className={cn(
      "flex max-h-[90dvh] flex-col gap-0 p-0 sm:max-w-3xl",
      // Full screen on phones
      "max-sm:inset-0 max-sm:h-dvh max-sm:max-h-none max-sm:max-w-none max-sm:translate-0 max-sm:rounded-none max-sm:border-0",
    )}>
      <DialogHeader className="flex-row items-center gap-2 border-b px-4 py-3 pr-12 text-left">
        {backButton}
        <DialogTitle className="min-w-0 flex-1 truncate">{titleText}</DialogTitle>
        <DialogDescription className="sr-only">{i18n.t("report_characters")}</DialogDescription>
      </DialogHeader>
      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {content}
      </div>
      <DialogFooter className="flex-row flex-wrap justify-end border-t px-4 py-3">
        {actions}
      </DialogFooter>
    </DialogContent>
  </Dialog>;
}
