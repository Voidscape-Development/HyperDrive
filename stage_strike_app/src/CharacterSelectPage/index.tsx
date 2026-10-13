import {useEffect, useRef, useState} from "react";
import "../NoSleep";
import "../StageStrikePage/stageStrike.css";
import {Info, Lock} from "lucide-react";
import i18n from "../i18n/config";
import websocketConnection from "../websocketConnection";
import {TopBar} from "../StageStrikePage/TopBar";
import {NoRulesetError} from "../StageStrikePage/NoRulesetError";
import {
  CharacterReportDialog,
  CharacterSlot,
  PlayerSlots,
  TeamColumn,
  TeamColumns,
} from "../StageStrikePage/CharacterReportDialog";
import {FindCharacter, type Characters} from "../StageStrikePage/characterAssets";
import {CharacterSelectReport} from "../StageStrikePage/postActions";
import {
  useCharacters,
  useScoreboardParam,
  useStrikeData,
  useTeamParam,
  type StrikeData,
  type StrikeTeam,
} from "../StageStrikePage/useHdData";
import {Page} from "@/components/Page";
import {Alert, AlertDescription} from "@/components/ui/alert";
import {Card} from "@/components/ui/card";

/**
 * Character selection only, for a scoreboard (?scoreboard=<n>) and one team
 * (&team=<1|2>) or both. Each team picks once per score: once sent, the
 * picks are locked until the score changes. A team's picks reach the
 * scoreboard once the other team sent theirs, like on the stage strike page.
 */
export default function CharacterSelectPage() {
  const [scoreboard, setScoreboard] = useScoreboardParam();
  const team = useTeamParam();
  const {data, scoreboards, connected, refresh} = useStrikeData(scoreboard, setScoreboard);
  const characters = useCharacters(data?.game);
  const [, forceUpdate] = useState(0);

  useEffect(() => {
    const listener = () => forceUpdate((n) => n + 1);
    i18n.on("languageChanged", listener);
    return () => i18n.off("languageChanged", listener);
  }, []);

  useEffect(() => {
    document.title = `${i18n.t("character_select")} · ${scoreboards.find((s) => s.number === scoreboard)?.name ?? scoreboard}`;
  }, [scoreboard, scoreboards]);

  const playerNames = [data?.p1 || i18n.t("p1"), data?.p2 || i18n.t("p2")];
  const myPlayer = team ? (data?.teams ?? []).findIndex((t) => t?.team === team) : -1;

  return <Page>
    <TopBar
      title={i18n.t("character_select")}
      scoreboard={scoreboard}
      scoreboards={scoreboards}
      onScoreboardChange={setScoreboard}
      teamName={myPlayer !== -1 ? playerNames[myPlayer] : null}
      teamPlayer={myPlayer}
      connected={connected}
      playerLanguages={[]}
      currPlayer={-1}
      selectedStage={null}
    />
    {data
      ? <CharacterSelectView
        data={data}
        scoreboard={scoreboard}
        team={team}
        characters={characters}
        refresh={refresh}
      />
      : <NoRulesetError loading connected={connected} />
    }
  </Page>;
}

/**
 * Asks HyperDrive for the scoreboard's data again when its score changes, as the
 * score is what unlocks the next pick. HyperDrive sends every state change to the
 * app; only the score's matter here.
 */
function useRefreshOnScore(scoreboard: number, refresh: () => void) {
  const timer = useRef<ReturnType<typeof setTimeout>>(null);
  useEffect(() => {
    const socket = websocketConnection.instance();
    const later = () => {
      clearTimeout(timer.current);
      timer.current = setTimeout(refresh, 250);
    };
    const onDelta = (message) => {
      const deltas = message?.delta ?? [];
      const scoreChanged = deltas.some(({path}) => Array.isArray(path)
        && path[0] === "score" && String(path[1]) === String(scoreboard)
        // score.<n>, score.<n>.team, score.<n>.team.<t> or score.<n>.team.<t>.score
        && (path.length <= 4 ? (path.length < 3 || path[2] === "team") : path[2] === "team" && path[4] === "score"));
      if (scoreChanged) later();
    };
    socket.on("program_state_update", onDelta);
    socket.on("program_state", later);
    return () => {
      clearTimeout(timer.current);
      socket.off("program_state_update", onDelta);
      socket.off("program_state", later);
    };
  }, [scoreboard, refresh]);
}

/** The character select itself, also shown by the stage strike page when
 * there's no ruleset */
interface CharacterSelectViewProps {
  data: StrikeData;
  scoreboard: number;
  team: number | null;
  characters: Characters;
  refresh: () => void;
  notice?: string;
}

export function CharacterSelectView({data, scoreboard, team, characters, refresh, notice}: CharacterSelectViewProps) {
  useRefreshOnScore(scoreboard, refresh);

  const target = {scoreboard, team};
  const playerNames = [data?.p1 || i18n.t("p1"), data?.p2 || i18n.t("p2")];
  const myPlayer = team ? (data?.teams ?? []).findIndex((t) => t?.team === team) : -1;
  const characterSelect = data?.state?.characterSelect ?? {active: false, submitted: {}};
  const score = data?.score ?? [0, 0];
  const game = (score[0] ?? 0) + (score[1] ?? 0) + 1;

  // Locked for this page's team, or for both teams on a page for both
  const lock = data?.character_lock?.locked ?? {};
  const locked = team ? !!lock[String(team)] : !!(lock["1"] || lock["2"]);

  const otherTeam = myPlayer !== -1 ? data?.teams?.[(myPlayer + 1) % 2] : null;
  const otherName = otherTeam ? (otherTeam.name || playerNames[(myPlayer + 1) % 2]) : null;
  const waitingForOther = !!otherTeam && characterSelect.active
    && !characterSelect.submitted?.[String(otherTeam.team)];

  return <main className="mx-auto flex w-full max-w-[960px] flex-1 flex-col gap-3 overflow-auto px-4 pt-3 pb-4">
    {notice &&
      <Alert>
        <Info />
        <AlertDescription>{notice}</AlertDescription>
      </Alert>
    }

    {locked
      ? <Card className="gap-3 p-4">
        <div className="flex items-center gap-2">
          <Lock className="size-5 text-pick" />
          <h2 className="text-lg font-semibold">
            {i18n.t("characters_locked", {value: game})}
          </h2>
        </div>
        <p className="text-sm text-muted-foreground">
          {waitingForOther
            ? i18n.t("characters_waiting", {team: otherName})
            : i18n.t("characters_locked_hint")}
        </p>
        {!waitingForOther &&
          <LockedCharacters
            teams={(data?.teams ?? []).map((t, i) => (myPlayer === -1 || i === myPlayer) ? t : null)}
            playerNames={playerNames}
            characters={characters}
          />
        }
      </Card>
      : <CharacterReportDialog
        inline
        target={target}
        myPlayer={myPlayer}
        characterSelect={characterSelect}
        game={data?.game}
        teams={data?.teams}
        charactersPerPlayer={data?.characters_per_player}
        playerNames={playerNames}
        characters={characters}
        report={CharacterSelectReport}
        title={i18n.t("characters_for_game", {value: game})}
        onSent={refresh}
      />
    }
  </main>;
}

/** The characters on the scoreboard, once picked */
function LockedCharacters({teams, playerNames, characters}: {
  teams: StrikeTeam[];
  playerNames: string[];
  characters: Characters;
}) {
  return <TeamColumns>
    {teams.map((team, t) => team &&
      <TeamColumn key={t} index={t} name={team.name || playerNames[t]}>
        {(team.players ?? []).map((player) =>
          <PlayerSlots
            key={player.player}
            name={(team.players.length > 1 || team.name) ? player.name : undefined}
          >
            {(player.characters ?? []).filter((c) => c).map((c, i) => {
              const character = FindCharacter(characters, c);
              return character && <CharacterSlot key={i} character={character} skin={c.skin ?? 0} />;
            })}
          </PlayerSlots>
        )}
      </TeamColumn>
    )}
  </TeamColumns>;
}
