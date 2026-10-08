import React from "react";
import {
    Box,
    Button,
    Dialog,
    DialogActions,
    DialogContent,
    DialogContentText,
    DialogTitle,
    IconButton,
    ListItemIcon,
    ListItemText,
    Menu,
    MenuItem,
    Paper,
    Stack,
    Typography,
} from "@mui/material";
import {DeleteSweep, LiveTv, MoreHoriz} from "@mui/icons-material";
import i18n from "../i18n/config";
import {api} from "./api";
import {teamDisplayName} from "./ScoreBar";

/**
 * Where the scoreboard's set comes from, like the desktop's set bar: the
 * linked set or station, or "Manual", with loading the stream's set and
 * clearing the scoreboard next to it.
 */
export default function SourceBar({scoreboardNumber, score}) {
    const [menuAnchor, setMenuAnchor] = React.useState(null);
    const [confirmClear, setConfirmClear] = React.useState(false);

    const linked = !!score?.set_id;
    const teams = score?.team ?? {};
    let title;
    let subtitle;
    if (linked) {
        title = [
            score?.match,
            `${teamDisplayName(teams["1"], 1)} vs ${teamDisplayName(teams["2"], 2)}`,
        ].filter(Boolean).join(" · ");
        const parts = [i18n.t("linked_set", {value: score.set_id})];
        if (score?.station && (score?.auto_update === "stream" || score?.auto_update === "station")) {
            parts.push(`${i18n.t(score.auto_update)} ${score.station}`);
        }
        if (score?.auto_update) {
            parts.push(i18n.t("auto_updating"));
        }
        subtitle = parts.join(" · ");
    } else {
        title = i18n.t("manual");
        subtitle = i18n.t("manual_hint");
    }

    return (
        <>
            <Paper variant={"outlined"} sx={{px: 1.5, py: 1}}>
                <Stack direction={"row"} alignItems={"center"} gap={1.5}>
                    <Box sx={{
                        width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
                        bgcolor: linked ? 'success.main' : 'text.disabled',
                    }}/>
                    <Box sx={{flex: 1, minWidth: 0}}>
                        <Typography noWrap sx={{fontWeight: 600}} title={title}>{title}</Typography>
                        <Typography variant={"body2"} color={"text.secondary"} noWrap title={subtitle}>
                            {subtitle}
                        </Typography>
                    </Box>
                    <Button
                        variant={linked ? "outlined" : "contained"}
                        size={"small"}
                        startIcon={<LiveTv/>}
                        onClick={() => api.pullStreamSet(scoreboardNumber).catch(() => {})}
                        sx={{flexShrink: 0, display: {xs: 'none', sm: 'inline-flex'}}}
                    >
                        {i18n.t("load_stream_set")}
                    </Button>
                    {/* Only the icon on phones */}
                    <IconButton
                        color={"primary"}
                        aria-label={i18n.t("load_stream_set")}
                        title={i18n.t("load_stream_set")}
                        onClick={() => api.pullStreamSet(scoreboardNumber).catch(() => {})}
                        sx={{display: {xs: 'inline-flex', sm: 'none'}}}
                    >
                        <LiveTv/>
                    </IconButton>
                    <IconButton aria-label={i18n.t("more")} onClick={(e) => setMenuAnchor(e.currentTarget)}>
                        <MoreHoriz/>
                    </IconButton>
                </Stack>
            </Paper>

            <Menu anchorEl={menuAnchor} open={!!menuAnchor} onClose={() => setMenuAnchor(null)}>
                <MenuItem onClick={() => {
                    setMenuAnchor(null);
                    setConfirmClear(true);
                }}>
                    <ListItemIcon><DeleteSweep color={"error"}/></ListItemIcon>
                    <ListItemText>{i18n.t("clear_scoreboard")}</ListItemText>
                </MenuItem>
            </Menu>

            <Dialog open={confirmClear} onClose={() => setConfirmClear(false)}>
                <DialogTitle>{i18n.t("clear_scoreboard")}</DialogTitle>
                <DialogContent>
                    <DialogContentText>{i18n.t("clear_scoreboard_confirm")}</DialogContentText>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setConfirmClear(false)}>{i18n.t("cancel")}</Button>
                    <Button color={"error"} onClick={() => {
                        setConfirmClear(false);
                        api.clearAll(scoreboardNumber).catch(() => {});
                    }}>
                        {i18n.t("clear")}
                    </Button>
                </DialogActions>
            </Dialog>
        </>
    );
}
