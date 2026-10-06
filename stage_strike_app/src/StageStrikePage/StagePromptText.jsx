import {Box, Typography} from "@mui/material";
import i18n from "../i18n/config";
import ReactDOMServer from "react-dom/server";

function embedHtml(html) {
  return <span dangerouslySetInnerHTML={{__html: html}} />;
}

/** One dot per stage to strike or pick in a step, filled once done */
function StepTracker({steps, playerNames, strikesDone}) {
  if (steps.length === 0) return null;
  return <Box className="ss-steps">
    {steps.map((step, i) =>
      <Box
        key={i}
        className={`ss-step p${step.player + 1} ${step.done ? "done" : ""} ${step.current ? "current" : ""}`}
        title={`${playerNames[step.player]}: ${i18n.t(step.kind === "ban" ? "ban_word" : "pick_word")} ${step.count}`}
      >
        {Array.from({length: step.count}).map((_, j) =>
          <span
            key={j}
            className={`ss-step-dot ${step.kind} ${step.done || (step.current && j < strikesDone) ? "filled" : ""}`}
          />
        )}
      </Box>
    )}
  </Box>;
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
}) {
  const playerHtml = ReactDOMServer.renderToStaticMarkup(
    <span className={`ss-prompt-player p${currentPlayer + 1}`}>{currentPlayerName}</span>
  );
  const banHtml = `<span class="ss-prompt-ban">${i18n.t("ban_word")}</span>`;
  const pickHtml = `<span class="ss-prompt-pick">${i18n.t("pick_word")}</span>`;

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

  return <Box className={`ss-prompt ${selectedStage ? "done" : ""}`}>
    <Typography className="ss-prompt-text" component="div">
      {body}
    </Typography>
    {!selectedStage && !isGentlemans &&
      <StepTracker steps={steps} playerNames={playerNames} strikesDone={strikesDone} />
    }
  </Box>;
}
