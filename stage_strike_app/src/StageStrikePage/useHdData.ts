import {useCallback, useEffect, useState} from "react";
import {useSearchParams} from "react-router-dom";
import websocketConnection from "../websocketConnection";

import type {Character, Characters} from "./characterAssets";
import type {Ruleset, StrikeState} from "./strikeLogic";
import type {ScoreboardOption} from "./TopBar";

const SCOREBOARD_KEY = "hd_stage_strike_scoreboard";

/** A character on the scoreboard */
export interface CharacterSelection {
  en_name: string;
  codename?: string;
  skin?: number;
}

export interface StrikeTeamPlayer {
  player: number;
  name?: string;
  characters?: (CharacterSelection | null)[];
}

/** A team in the strike, in strike order (strike player 0 or 1) */
export interface StrikeTeam {
  // The team's number on the scoreboard, 1 or 2
  team: number;
  name?: string;
  players: StrikeTeamPlayer[];
}

/** The characters picked for the next game: which teams sent theirs */
export interface CharacterSelect {
  active: boolean;
  game?: number;
  submitted?: Record<string, boolean>;
}

export interface PendingWinner {
  // The team (1 or 2) whose page reported it
  team: number;
  // The strike player (0 or 1) who won
  winner: number;
}

/** What HyperDrive sends for a scoreboard's stage strike */
export interface StrikeData {
  scoreboard?: number;
  scoreboards?: ScoreboardOption[];
  ruleset?: Ruleset;
  state?: Partial<StrikeState>;
  best_of?: number;
  p1?: string;
  p2?: string;
  p1_country?: string;
  p2_country?: string;
  teams?: StrikeTeam[];
  characters_per_player?: number;
  phase?: string;
  match?: string;
  game?: string;
  score?: number[];
  character_lock?: {locked?: Record<string, boolean>};
}

function readStoredScoreboard() {
  try {
    return Number.parseInt(localStorage.getItem(SCOREBOARD_KEY) ?? "1") || 1;
  } catch {
    return 1;
  }
}

/**
 * The scoreboard this page strikes for, from ?scoreboard=<n> (so a link can
 * be given to each station), else the last one picked on this device.
 */
export function useScoreboardParam(): [number, (scoreboard: number) => void] {
  const [params, setParams] = useSearchParams();
  const fromUrl = Number.parseInt(params.get("scoreboard") ?? "");
  const scoreboard = fromUrl > 0 ? fromUrl : readStoredScoreboard();

  const setScoreboard = useCallback((number: number) => {
    try {
      localStorage.setItem(SCOREBOARD_KEY, String(number));
    } catch {}
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set("scoreboard", String(number));
      return next;
    }, {replace: true});
  }, [setParams]);

  return [scoreboard, setScoreboard];
}

/** The team (1 or 2) this page is for, from ?team=<n>, or null for both teams */
export function useTeamParam() {
  const [params] = useSearchParams();
  const team = Number.parseInt(params.get("team") ?? "");
  return team === 1 || team === 2 ? team : null;
}

/**
 * HyperDrive's stage strike data for a scoreboard: its ruleset, strike state,
 * players and set info. HyperDrive sends it again whenever the strike changes.
 */
export function useStrikeData(scoreboard: number, onScoreboardMissing?: (scoreboard: number) => void) {
  const [data, setData] = useState<StrikeData | null>(null);
  const [scoreboards, setScoreboards] = useState<ScoreboardOption[]>([]);
  const [connected, setConnected] = useState(false);

  const socket = websocketConnection.instance();

  const refresh = useCallback(() => {
    socket.emit("ruleset", {scoreboardNumber: scoreboard});
  }, [socket, scoreboard]);

  useEffect(() => {
    setData(null);

    const onConnect = () => {
      setConnected(true);
      refresh();
    };
    const onDisconnect = (reason: string) => {
      setConnected(false);
      // The server closing the connection doesn't reconnect on its own
      if (reason === "io server disconnect") socket.connect();
    };
    const onRuleset = (d: StrikeData) => {
      if (d?.scoreboards) {
        setScoreboards(d.scoreboards);
        if (d.scoreboards.length > 0 && !d.scoreboards.some((s) => s.number === scoreboard)) {
          onScoreboardMissing?.(d.scoreboards[0].number);
          return;
        }
      }
      // Updates for other scoreboards are broadcast too
      if (d?.scoreboard === undefined || d.scoreboard === scoreboard) {
        setData(d);
      }
    };

    socket.on("connect", onConnect);
    socket.on("disconnect", onDisconnect);
    socket.on("ruleset", onRuleset);
    if (socket.connected) onConnect();

    return () => {
      socket.off("connect", onConnect);
      socket.off("disconnect", onDisconnect);
      socket.off("ruleset", onRuleset);
    };
  }, [socket, scoreboard, refresh, onScoreboardMissing]);

  return {data, scoreboards, connected, refresh};
}

/** The loaded game's characters, keyed by en_name */
export function useCharacters(game?: string) {
  const [characters, setCharacters] = useState<Characters>({});
  const socket = websocketConnection.instance();

  useEffect(() => {
    const onCharacters = (d: Record<string, Character>) => {
      const byEnName: Characters = {};
      Object.values(d ?? {}).forEach((c) => {
        if (c?.en_name) byEnName[c.en_name] = c;
      });
      setCharacters(byEnName);
    };
    socket.on("characters", onCharacters);
    return () => {
      socket.off("characters", onCharacters);
    };
  }, [socket]);

  useEffect(() => {
    if (game) socket.emit("characters", {});
  }, [socket, game]);

  return characters;
}
