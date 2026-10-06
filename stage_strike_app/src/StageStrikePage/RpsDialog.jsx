import {Box, Button, Dialog, DialogContent, Typography} from "@mui/material";
import {Casino, EmojiEvents} from "@mui/icons-material";
import i18n from "../i18n/config";
import {ReportRpsWin} from "./postActions";

export function RpsDialog({target, playerNames}) {
  return <Dialog
    open={true}
    onClose={() => {}}
    maxWidth="sm"
    fullWidth
    aria-labelledby="rps-title"
    PaperProps={{className: "ss-dialog"}}
  >
    <DialogContent>
      <Box className="ss-rps">
        <Typography className="ss-rps-hands" component="div" aria-hidden>✊ 🖐️ ✌️</Typography>
        <Typography id="rps-title" variant="h5" component="h2" className="ss-rps-title">
          {i18n.t("rock_paper_scissors")}
        </Typography>
        <Typography color="text.secondary">{i18n.t("initial_explanation")}</Typography>

        <Box className="ss-rps-buttons">
          {[0, 1].map((player) =>
            <Button
              key={player}
              className="ss-rps-player"
              size="large"
              color={`p${player + 1}color`}
              variant="contained"
              startIcon={<EmojiEvents />}
              onClick={() => ReportRpsWin(target, player)}
            >
              <span className="ss-winner-text">{i18n.t("player_won", {player: playerNames[player]})}</span>
            </Button>
          )}
        </Box>
        <Button
          fullWidth
          color="inherit"
          variant="outlined"
          startIcon={<Casino />}
          onClick={() => ReportRpsWin(target, Math.random() > 0.5 ? 1 : 0)}
        >
          {i18n.t("randomize")}
        </Button>
      </Box>
    </DialogContent>
  </Dialog>;
}
