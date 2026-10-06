import {Box, Typography} from "@mui/material";
import i18n from "../i18n/config";
import {CharacterIcon, CharacterName, FindCharacter} from "./characterAssets";

function TeamCharacters({team, characters}) {
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
          className="ss-panel-char"
        />);
      }
    });
  });
  if (icons.length === 0) return null;
  return <Box className="ss-panel-chars">{icons}</Box>;
}

function PlayerPanel({index, name, team, characters, wins, active, isMe, characterStatus}) {
  return <Box className={`ss-panel p${index + 1} ${active ? "active" : ""}`}>
    <Box className="ss-panel-info">
      <Typography className="ss-panel-name" component="div" noWrap title={name}>
        {name}
      </Typography>
      <TeamCharacters team={team} characters={characters} />
      {characterStatus &&
        <span className={`ss-panel-status ${characterStatus}`}>
          {i18n.t(characterStatus === "ready" ? "characters_ready" : "picking_characters")}
        </span>
      }
    </Box>
    <Typography className="ss-panel-score" component="div">{wins}</Typography>
    {(active || isMe) &&
      <span className="ss-panel-turn">
        {[isMe && i18n.t("you"), active && i18n.t("turn")].filter(Boolean).join(" · ")}
      </span>
    }
  </Box>;
}

export function PlayerPanels({playerNames, teams, characters, wins, currPlayer, myPlayer, characterSelect, currGame, bestOf, phase, match}) {
  const setInfo = [phase, match].filter(Boolean).join(" · ");
  // Who already sent their characters for the next game, not what they picked
  const characterStatus = (index) => {
    if (!characterSelect?.active || !teams?.[index]) return null;
    return characterSelect.submitted?.[String(teams[index].team)] ? "ready" : "picking";
  };

  return <Box className="ss-panels">
    <PlayerPanel
      index={0}
      name={playerNames[0]}
      team={teams?.[0]}
      characters={characters}
      wins={wins[0]}
      active={currPlayer === 0}
      isMe={myPlayer === 0}
      characterStatus={characterStatus(0)}
    />
    <Box className="ss-panels-center">
      {setInfo && <Typography className="ss-set-info" component="div" noWrap>{setInfo}</Typography>}
      <Typography className="ss-game" component="div">
        {i18n.t("game", {value: currGame + 1})}
      </Typography>
      {bestOf > 0 &&
        <Typography className="ss-best-of" component="div">
          {i18n.t("best_of", {value: bestOf})}
        </Typography>
      }
    </Box>
    <PlayerPanel
      index={1}
      name={playerNames[1]}
      team={teams?.[1]}
      characters={characters}
      wins={wins[1]}
      active={currPlayer === 1}
      isMe={myPlayer === 1}
      characterStatus={characterStatus(1)}
    />
  </Box>;
}
