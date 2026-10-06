import {ButtonBase, Typography} from "@mui/material";
import i18n from "../i18n/config";

export function StageCard({
  stageName,
  stageImage,
  isSelected,
  onClick,
  isStriked,
  isBanned,
  strikedBy,
  strikedByPlayer,
  isGentlemanEnabled,
  selectedBy,
  selectedByPlayer,
  disabled,
}) {
  const classes = ["ss-stage"];
  if (isStriked) classes.push("striked");
  if (isBanned) classes.push("banned");
  if (isSelected) classes.push("selected");
  if (disabled) classes.push("waiting");

  let stamp = null;
  let label = null;
  let labelClass = "";

  if (isSelected) {
    stamp = isGentlemanEnabled ? "stage-gentlemans" : "stage-selected";
    label = isGentlemanEnabled ? i18n.t("gentlemans") : selectedBy;
    labelClass = isGentlemanEnabled ? "pick" : `p${selectedByPlayer + 1}`;
  } else if (isStriked) {
    stamp = "stage-striked";
    label = strikedBy;
    labelClass = strikedByPlayer >= 0 ? `p${strikedByPlayer + 1}` : "";
  } else if (isBanned) {
    stamp = "stage-dsr";
    label = i18n.t("dsr");
    labelClass = "banned";
  }

  return <ButtonBase
    className={classes.join(" ")}
    onClick={disabled ? undefined : onClick}
    disabled={disabled}
    focusRipple
    aria-pressed={isSelected}
    aria-label={stageName}
  >
    <img className="ss-stage-image" src={stageImage} alt="" loading="lazy" />
    {stamp && <span className={`stamp ${stamp}`} />}
    {label &&
      <span className={`ss-stage-label ${labelClass}`}>{label}</span>
    }
    <Typography className="ss-stage-name" component="span" noWrap>
      {stageName}
    </Typography>
  </ButtonBase>;
}
