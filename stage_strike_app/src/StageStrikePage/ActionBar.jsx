import {Box, Button, Typography} from "@mui/material";
import {Check, Close, EmojiEvents} from "@mui/icons-material";
import i18n from "../i18n/config";
import {ConfirmClicked, MatchWinner} from "./postActions";

function WinnerButton({target, player, playerNames, label, variant = "contained"}) {
  return <Button
    className={`ss-winner p${player + 1}`}
    variant={variant}
    color={`p${player + 1}color`}
    size="large"
    startIcon={<EmojiEvents />}
    onClick={() => MatchWinner(target, player)}
  >
    <span className="ss-winner-text">{label ?? i18n.t("player_won", {player: playerNames[player]})}</span>
  </Button>;
}

/**
 * The step's main action: confirming the strikes, or who won the game.
 * A team's page reports the winner, and the other team's page confirms it.
 */
export function ActionBar({target, canConfirm, selectedStage, playerNames, teams, myPlayer, pendingWinner}) {
  if (selectedStage) {
    const teamMode = myPlayer !== -1;
    // The strike player (0 or 1) whose page reported the result
    const reporter = pendingWinner
      ? (teams ?? []).findIndex((t) => t?.team === pendingWinner.team)
      : -1;
    const winner = pendingWinner?.winner;

    if (teamMode && pendingWinner && reporter === myPlayer) {
      return <Box className="ss-actionbar winners pending">
        <Typography className="ss-pending-text">
          {i18n.t("waiting_for_confirm", {
            team: playerNames[(myPlayer + 1) % 2],
            player: playerNames[winner],
          })}
        </Typography>
        <Button
          variant="outlined"
          color="inherit"
          startIcon={<Close />}
          onClick={() => MatchWinner(target, -1)}
        >
          {i18n.t("take_back")}
        </Button>
      </Box>;
    }

    if (teamMode && pendingWinner) {
      return <Box className="ss-actionbar winners pending">
        <Typography className="ss-pending-text">
          {i18n.t("reported_winner", {team: playerNames[reporter], player: playerNames[winner]})}
        </Typography>
        <Box className="ss-pending-buttons">
          <WinnerButton
            target={target}
            player={winner}
            playerNames={playerNames}
            // The text above says who won, so this stays short on phones
            label={i18n.t("confirm")}
          />
          <WinnerButton
            target={target}
            player={(winner + 1) % 2}
            playerNames={playerNames}
            variant="outlined"
            label={i18n.t("dispute_winner", {player: playerNames[(winner + 1) % 2]})}
          />
        </Box>
      </Box>;
    }

    return <Box className={`ss-actionbar winners ${pendingWinner ? "pending" : ""}`}>
      {pendingWinner && reporter !== -1 &&
        // The page for both teams can settle it
        <Typography className="ss-pending-text">
          {i18n.t("reported_winner", {team: playerNames[reporter], player: playerNames[winner]})}
        </Typography>
      }
      <Box className="ss-pending-buttons">
        {[0, 1].map((player) =>
          <WinnerButton key={player} target={target} player={player} playerNames={playerNames} />
        )}
      </Box>
    </Box>;
  }

  if (canConfirm) {
    return <Box className="ss-actionbar">
      <Button
        className="ss-confirm"
        variant="contained"
        color="success"
        size="large"
        startIcon={<Check />}
        onClick={() => ConfirmClicked(target)}
      >
        {i18n.t("confirm")}
      </Button>
    </Box>;
  }

  return null;
}
