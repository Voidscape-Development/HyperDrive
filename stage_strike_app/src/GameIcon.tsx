import {useState} from "react";
import {BASE_URL} from "./env";
import type {HDGameInfo} from "./backendDataTypes";

/** A game's logo, or its codename without one */
export function GameIcon({game, className}: {game: HDGameInfo; className?: string}) {
  const [errored, setErrored] = useState(false);

  if (errored) {
    return <span className={className}>{game.codename}</span>;
  }
  return <img
    alt={game.name}
    src={`${BASE_URL}/user_data/games/${game.codename}/base_files/logo.png`}
    className={className ?? "h-8 w-auto object-contain"}
    onError={() => setErrored(true)}
  />;
}
