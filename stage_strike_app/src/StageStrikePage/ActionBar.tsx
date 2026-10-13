import type {ReactNode} from "react";
import {Check, Trophy, Undo2} from "lucide-react";
import i18n from "../i18n/config";
import {ConfirmClicked, MatchWinner, type StrikeTarget} from "./postActions";
import {Button} from "@/components/ui/button";
import {cn} from "@/lib/utils";
import {PLAYER_FILL, PLAYER_OUTLINE} from "./playerColors";
import type {PendingWinner, StrikeTeam} from "./useHdData";

interface WinnerButtonProps {
  target: StrikeTarget;
  player: number;
  playerNames: string[];
  label?: string;
  outline?: boolean;
}

function WinnerButton({target, player, playerNames, label, outline = false}: WinnerButtonProps) {
  return <Button
    variant={outline ? "outline" : "default"}
    size="lg"
    className={cn(
      "h-12 min-w-0 max-w-[520px] flex-1 text-base font-semibold",
      outline ? PLAYER_OUTLINE[player] : PLAYER_FILL[player],
    )}
    onClick={() => MatchWinner(target, player)}
  >
    <Trophy />
    <span className="truncate">{label ?? i18n.t("player_won", {player: playerNames[player]})}</span>
  </Button>;
}

function Bar({children, className}: {children: ReactNode; className?: string}) {
  return <div className={cn(
    "mx-auto flex w-full max-w-[1500px] flex-col items-center gap-2 animate-in fade-in slide-in-from-bottom-2",
    className,
  )}>
    {children}
  </div>;
}

function PendingText({children}: {children: ReactNode}) {
  return <p className="text-center text-sm font-medium">{children}</p>;
}

interface ActionBarProps {
  target: StrikeTarget;
  canConfirm: boolean;
  selectedStage: string | null;
  playerNames: string[];
  teams: StrikeTeam[];
  myPlayer: number;
  pendingWinner: PendingWinner | null;
}

/**
 * The step's main action: confirming the strikes, or who won the game.
 * A team's page reports the winner, and the other team's page confirms it.
 */
export function ActionBar({target, canConfirm, selectedStage, playerNames, teams, myPlayer, pendingWinner}: ActionBarProps) {
  if (selectedStage) {
    const teamMode = myPlayer !== -1;
    // The strike player (0 or 1) whose page reported the result
    const reporter = pendingWinner
      ? (teams ?? []).findIndex((t) => t?.team === pendingWinner.team)
      : -1;
    const winner = pendingWinner?.winner;

    if (teamMode && pendingWinner && reporter === myPlayer) {
      return <Bar>
        <PendingText>
          {i18n.t("waiting_for_confirm", {
            team: playerNames[(myPlayer + 1) % 2],
            player: playerNames[winner],
          })}
        </PendingText>
        <Button variant="outline" onClick={() => MatchWinner(target, -1)}>
          <Undo2 />
          {i18n.t("take_back")}
        </Button>
      </Bar>;
    }

    if (teamMode && pendingWinner) {
      return <Bar>
        <PendingText>
          {i18n.t("reported_winner", {team: playerNames[reporter], player: playerNames[winner]})}
        </PendingText>
        <div className="flex w-full justify-center gap-3">
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
            outline
            label={i18n.t("dispute_winner", {player: playerNames[(winner + 1) % 2]})}
          />
        </div>
      </Bar>;
    }

    return <Bar>
      {pendingWinner && reporter !== -1 &&
        // The page for both teams can settle it
        <PendingText>
          {i18n.t("reported_winner", {team: playerNames[reporter], player: playerNames[winner]})}
        </PendingText>
      }
      <div className="flex w-full justify-center gap-3">
        {[0, 1].map((player) =>
          <WinnerButton key={player} target={target} player={player} playerNames={playerNames} />
        )}
      </div>
    </Bar>;
  }

  if (canConfirm) {
    return <Bar>
      <Button
        size="lg"
        className="h-12 w-full max-w-[420px] bg-pick text-base font-semibold text-zinc-950 hover:bg-pick/90"
        onClick={() => ConfirmClicked(target)}
      >
        <Check />
        {i18n.t("confirm")}
      </Button>
    </Bar>;
  }

  return null;
}
