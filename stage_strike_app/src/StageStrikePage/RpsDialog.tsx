import {Dices, Trophy} from "lucide-react";
import i18n from "../i18n/config";
import {ReportRpsWin, type StrikeTarget} from "./postActions";
import {Button} from "@/components/ui/button";
import {Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle} from "@/components/ui/dialog";
import {cn} from "@/lib/utils";
import {PLAYER_FILL} from "./playerColors";

/** Who starts striking: always open until someone won rock paper scissors */
export function RpsDialog({target, playerNames}: {target: StrikeTarget; playerNames: string[]}) {
  return <Dialog open={true}>
    <DialogContent
      showCloseButton={false}
      onEscapeKeyDown={(e) => e.preventDefault()}
      onInteractOutside={(e) => e.preventDefault()}
      className="sm:max-w-lg"
    >
      <DialogHeader className="items-center text-center sm:text-center">
        <div className="text-4xl tracking-[0.3em]" aria-hidden>✊🖐️✌️</div>
        <DialogTitle className="text-xl">{i18n.t("rock_paper_scissors")}</DialogTitle>
        <DialogDescription>{i18n.t("initial_explanation")}</DialogDescription>
      </DialogHeader>

      <div className="grid grid-cols-2 gap-3">
        {[0, 1].map((player) =>
          <Button
            key={player}
            size="lg"
            className={cn("h-14 min-w-0 text-base font-semibold", PLAYER_FILL[player])}
            onClick={() => ReportRpsWin(target, player)}
          >
            <Trophy />
            <span className="truncate">{i18n.t("player_won", {player: playerNames[player]})}</span>
          </Button>
        )}
      </div>
      <Button variant="outline" className="w-full" onClick={() => ReportRpsWin(target, Math.random() > 0.5 ? 1 : 0)}>
        <Dices />
        {i18n.t("randomize")}
      </Button>
    </DialogContent>
  </Dialog>;
}
