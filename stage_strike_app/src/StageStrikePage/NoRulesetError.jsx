import {Box, CircularProgress, Paper, Typography} from "@mui/material";
import i18n from "../i18n/config";

export function NoRulesetError({loading, connected}) {
  let content;
  if (!connected || loading) {
    content = <>
      <CircularProgress size={32} />
      <Typography>{i18n.t(connected ? "loading" : "connecting")}</Typography>
    </>;
  } else {
    content = <>
      <Typography className="ss-empty-icon" aria-hidden>⚠️</Typography>
      <Typography variant="h6">{i18n.t("no_ruleset_title")}</Typography>
      <Typography color="text.secondary">{i18n.t("no_ruleset_error")}</Typography>
    </>;
  }

  return <Box className="ss-empty">
    <Paper className="ss-empty-card" elevation={4}>
      {content}
    </Paper>
  </Box>;
}
