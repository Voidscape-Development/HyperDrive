import {useState} from "react";
import i18n from "../i18n/config";
import {RestartStageStrike, SetGentlemans, Undo, Redo} from "./postActions";
import {
  Badge,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
} from "@mui/material";
import {
  Handshake,
  People,
  RestartAlt,
  Undo as UndoIcon,
  Redo as RedoIcon,
} from "@mui/icons-material";

function FooterButton({icon, label, ...props}) {
  return <Button className="ss-footer-button" startIcon={icon} {...props}>
    <span className="ss-footer-label">{label}</span>
  </Button>;
}

export function FooterControls({
  target,
  teamMode,
  isGentlemans,
  canToggleGentlemans = true,
  canUndo,
  canRedo,
  onCharacters,
  missingCharacters,
}) {
  const [confirmRestart, setConfirmRestart] = useState(false);

  return <Box className={`ss-footer ${teamMode ? "team" : ""}`}>
    <FooterButton
      icon={<UndoIcon />}
      label={i18n.t("undo")}
      disabled={!canUndo}
      onClick={() => Undo(target)}
    />
    <FooterButton
      icon={<RedoIcon />}
      label={i18n.t("redo")}
      disabled={!canRedo}
      onClick={() => Redo(target)}
    />
    <FooterButton
      icon={<Handshake />}
      label={i18n.t("gentlemans_pick")}
      className={`ss-footer-button ${isGentlemans ? "active" : ""}`}
      disabled={!canToggleGentlemans}
      onClick={() => SetGentlemans(target, !isGentlemans)}
    />
    <FooterButton
      icon={<Badge color="warning" variant="dot" invisible={!missingCharacters}><People /></Badge>}
      label={i18n.t("characters")}
      onClick={onCharacters}
    />
    {/* Restarting is left to the page for both teams */}
    {!teamMode &&
      <FooterButton
        icon={<RestartAlt />}
        label={i18n.t("restart_all")}
        onClick={() => setConfirmRestart(true)}
      />
    }

    <Dialog open={confirmRestart} onClose={() => setConfirmRestart(false)}>
      <DialogTitle>{i18n.t("restart_all")}</DialogTitle>
      <DialogContent>{i18n.t("restart_confirm")}</DialogContent>
      <DialogActions>
        <Button onClick={() => setConfirmRestart(false)}>{i18n.t("cancel")}</Button>
        <Button
          color="error"
          variant="contained"
          onClick={() => {
            setConfirmRestart(false);
            RestartStageStrike(target);
          }}
        >
          {i18n.t("restart_all")}
        </Button>
      </DialogActions>
    </Dialog>
  </Box>;
}
