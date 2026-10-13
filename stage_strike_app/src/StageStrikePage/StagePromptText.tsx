import ReactDOMServer from "react-dom/server";
import i18n from "../i18n/config";
import {cn} from "@/lib/utils";
import {PLAYER_TEXT, PLAYER_VAR} from "./playerColors";
import type {StrikeStep} from "./strikeLogic";

function embedHtml(html: string) {
  return <span dangerouslySetInnerHTML={{__html: html}} />;
}

/** One dot per stage to strike or pick in a step, filled once done */
function StepTracker({steps, playerNames, strikesDone}: {steps: StrikeStep[]; playerNames: string[]; strikesDone: number}) {
  if (steps.length === 0) return null;
  return <div className="flex flex-wrap justify-center gap-2">
    {steps.map((step, i) =>
      <div
        key={i}
        className={cn(
          "flex gap-1 rounded-full border px-2 py-1 opacity-50",
          PLAYER_VAR[step.player],
          step.done && "opacity-80",
          step.current && "border-(--color) opacity-100",
        )}
        title={`${playerNames[step.player]}: ${i18n.t(step.kind === "ban" ? "ban_word" : "pick_word")} ${step.count}`}
      >
        {Array.from({length: step.count}).map((_, j) =>
          <span
            key={j}
            className={cn(
              "size-2.5 border-2 border-(--color)",
              step.kind === "pick" ? "rounded-[2px]" : "rounded-full",
              (step.done || (step.current && j < strikesDone)) && "bg-(--color)",
            )}
          />
        )}
      </div>
    )}
  </div>;
}

interface StagePromptTextProps {
  selectedStage: string | null;
  isGentlemans: boolean;
  isPicking: boolean;
  strikeNumber: number;
  strikesDone: number;
  currentPlayer: number;
  currentPlayerName: string;
  steps: StrikeStep[];
  playerNames: string[];
  waiting: boolean;
}

export function StagePromptText({
  selectedStage,
  isGentlemans,
  isPicking,
  strikeNumber,
  strikesDone,
  currentPlayer,
  currentPlayerName,
  steps,
  playerNames,
  waiting,
}: StagePromptTextProps) {
  const playerHtml = ReactDOMServer.renderToStaticMarkup(
    <span className={cn("font-bold", PLAYER_TEXT[currentPlayer])}>{currentPlayerName}</span>
  );
  const word = "rounded-md px-1.5 font-bold uppercase";
  const banHtml = `<span class="${word} bg-ban/15 text-ban">${i18n.t("ban_word")}</span>`;
  const pickHtml = `<span class="${word} bg-pick/15 text-pick">${i18n.t("pick_word")}</span>`;

  let body;
  if (selectedStage) {
    body = i18n.t("report_results");
  } else if (isGentlemans) {
    body = i18n.t("gentlemans_prompt", {gentlemans_pick: i18n.t("gentlemans_pick")});
  } else if (waiting) {
    // A page for the other team
    body = embedHtml(i18n.t(isPicking ? "waiting_for_pick" : "waiting_for_ban", {
      player: playerHtml,
      interpolation: {escapeValue: false},
    }));
  } else if (isPicking) {
    body = embedHtml(i18n.t("select_a_stage_prompt", {
      player: playerHtml,
      pick: pickHtml,
      val: strikeNumber,
      interpolation: {escapeValue: false},
    }));
  } else {
    body = embedHtml(i18n.t("ban_prompt", {
      player: playerHtml,
      ban: banHtml,
      val: strikeNumber,
      interpolation: {escapeValue: false},
    }));
  }

  return <div className="my-4 flex flex-col items-center gap-2 text-center">
    <div className={cn("text-[clamp(18px,3vw,28px)] font-semibold tracking-tight", selectedStage && "text-pick")}>
      {body}
    </div>
    {!selectedStage && !isGentlemans &&
      <StepTracker steps={steps} playerNames={playerNames} strikesDone={strikesDone} />
    }
  </div>;
}
