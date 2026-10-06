import {useCallback, useEffect, useRef, useState} from "react";
import "../App.css";
import {
    Box,
    Button,
    ButtonGroup,
    Checkbox,
    Chip,
    FormControl,
    IconButton,
    InputLabel,
    MenuItem,
    Paper,
    Select,
    Stack,
    TextField,
    Tooltip,
    Typography,
} from "@mui/material";
import {
    CenterFocusStrong,
    ChevronLeft,
    ChevronRight,
    Clear,
    Fullscreen,
    Loop,
    Person,
    Videocam,
} from "@mui/icons-material";
import i18n from "../i18n/config";
import websocketConnection from "../websocketConnection";

/**
 * Remote for the bracket focus layout (layout/bracket_focus): what it zooms
 * to, like the bracket widget's "Layout focus" bar. Tap sets (and rounds)
 * to select them, then "Focus selected"; or focus a player's run, follow a
 * scoreboard's set, or tour the rounds. On a focus channel (?channel=<name>,
 * "main" by default): each layout shows one.
 */
export default function BracketFocusPage() {
    const [state, setState] = useState(null);
    const [connected, setConnected] = useState(false);
    const [selected, setSelected] = useState(new Set());
    const [selectedRounds, setSelectedRounds] = useState(new Set());
    const [scoreboard, setScoreboard] = useState(1);
    const [interval, setIntervalValue] = useState(8);
    const [channel, setChannel] = useState(
        () => new URLSearchParams(window.location.search).get("channel") || "main"
    );
    const [, forceUpdate] = useState(0);
    const refreshTimer = useRef(null);
    // For the socket's callbacks, which outlive renders
    const channelRef = useRef(channel);
    const pickChannelRef = useRef(null);

    useEffect(() => {
        document.title = `TSH ${i18n.t("bracket_focus")}`;
        const listener = () => forceUpdate((n) => n + 1);
        i18n.on("languageChanged", listener);
        return () => i18n.off("languageChanged", listener);
    }, []);

    useEffect(() => {
        const socket = websocketConnection.instance();
        const request = () => socket.emit("bracket_focus", {channel: channelRef.current});
        const onConnect = () => {
            setConnected(true);
            request();
        };
        const onDisconnect = () => setConnected(false);
        const onFocus = (data) => {
            // The channel was removed (or never was): back to main
            if (Array.isArray(data)) {
                if (data[0] === "NO_CHANNEL" && channelRef.current !== "main") {
                    pickChannelRef.current("main");
                }
                return;
            }
            // Answers about a channel picked before don't count
            if (data && typeof data === "object" && data.channel === channelRef.current) {
                setState(data);
            }
        };
        // The bracket or the focus may have changed: ask again, at most
        // twice a second
        const onUpdate = () => {
            if (refreshTimer.current) return;
            refreshTimer.current = setTimeout(() => {
                refreshTimer.current = null;
                request();
            }, 500);
        };
        socket.on("connect", onConnect);
        socket.on("disconnect", onDisconnect);
        socket.on("bracket_focus", onFocus);
        socket.on("program_state_update", onUpdate);
        socket.on("program_state", onUpdate);
        if (socket.connected) onConnect();
        return () => {
            socket.off("connect", onConnect);
            socket.off("disconnect", onDisconnect);
            socket.off("bracket_focus", onFocus);
            socket.off("program_state_update", onUpdate);
            socket.off("program_state", onUpdate);
            clearTimeout(refreshTimer.current);
            refreshTimer.current = null;
        };
    }, []);

    // Picks a channel: kept in the URL, so the page can be bookmarked with it
    const pickChannel = (name) => {
        channelRef.current = name;
        setChannel(name);
        setState(null);
        setSelected(new Set());
        setSelectedRounds(new Set());
        const params = new URLSearchParams(window.location.search);
        if (name === "main") params.delete("channel");
        else params.set("channel", name);
        const query = params.toString();
        window.history.replaceState(null, "", window.location.pathname + (query ? `?${query}` : ""));
        websocketConnection.instance().emit("bracket_focus", {channel: name});
    };
    pickChannelRef.current = pickChannel;

    const focus = state?.focus ?? {mode: "all", sets: [], rounds: []};
    const mode = focus.mode;

    // Keep the inputs in step with what's running
    useEffect(() => {
        if (focus.scoreboard) setScoreboard(focus.scoreboard);
        if (focus.interval) setIntervalValue(focus.interval);
    }, [focus.scoreboard, focus.interval]);

    const send = useCallback((request) => {
        websocketConnection.instance().emit("bracket_focus_set", {...request, channel: channelRef.current});
    }, []);

    const toggle = (set, value, setter) => {
        const next = new Set(set);
        next.has(value) ? next.delete(value) : next.add(value);
        setter(next);
    };

    const clearSelection = () => {
        setSelected(new Set());
        setSelectedRounds(new Set());
    };

    const focusSelected = () => {
        send({
            mode: selected.size ? "sets" : "rounds",
            sets: [...selected],
            rounds: [...selectedRounds],
        });
    };

    const inFocus = new Set(focus.sets ?? []);
    const roundsInFocus = new Set(focus.rounds ?? []);
    const count = selected.size + selectedRounds.size;
    const rounds = state?.rounds ?? [];
    const players = state?.players ?? [];

    let status = i18n.t("bracket_focus_all");
    if (inFocus.size) {
        status = focus.label || i18n.t("bracket_focus_n_sets", {value: inFocus.size});
        if (mode === "tour") {
            status = `${(focus.step ?? 0) + 1}/${focus.steps ?? 1} · ${status}`;
        }
    } else if (mode === "follow") {
        status = i18n.t("bracket_focus_follow_none", {value: focus.scoreboard ?? 1});
    }

    return <Box sx={{padding: 2, paddingBottom: 12, maxWidth: 1400, margin: "0 auto"}}>
        <Stack direction="row" alignItems="center" spacing={1} sx={{marginBottom: 2}} flexWrap="wrap" useFlexGap>
            <Typography variant="h5" sx={{flexGrow: 1}}>
                {i18n.t("bracket_focus")}{state?.name ? ` · ${state.name}` : ""}
            </Typography>
            <FormControl size="small" sx={{minWidth: 140}}>
                <InputLabel>{i18n.t("bracket_focus_channel")}</InputLabel>
                <Select
                    label={i18n.t("bracket_focus_channel")}
                    value={(state?.channels ?? [channel]).includes(channel) ? channel : ""}
                    onChange={(e) => pickChannel(e.target.value)}
                >
                    {(state?.channels ?? [channel]).map((name) => <MenuItem key={name} value={name}>
                        {name}
                    </MenuItem>)}
                </Select>
            </FormControl>
            <Chip
                color={connected ? "success" : "warning"}
                size="small"
                label={connected ? i18n.t("connected") : i18n.t("connecting")}
            />
        </Stack>

        <Paper elevation={2} sx={{padding: 2, marginBottom: 2}}>
            <Typography variant="overline">{i18n.t("bracket_focus_showing")}</Typography>
            <Typography variant="h6" sx={{marginBottom: 2}}>{status}</Typography>

            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap alignItems="center">
                <Button
                    variant={mode === "all" ? "contained" : "outlined"}
                    startIcon={<Fullscreen/>}
                    onClick={() => send({mode: "all"})}
                >
                    {i18n.t("bracket_focus_whole")}
                </Button>
                <ButtonGroup variant="outlined">
                    <Tooltip title={i18n.t("bracket_focus_previous")}>
                        <Button onClick={() => send({move: -1})}><ChevronLeft/></Button>
                    </Tooltip>
                    <Tooltip title={i18n.t("bracket_focus_next")}>
                        <Button onClick={() => send({move: 1})}><ChevronRight/></Button>
                    </Tooltip>
                </ButtonGroup>

                <Stack direction="row" spacing={1} alignItems="center">
                    <Button
                        variant={mode === "follow" ? "contained" : "outlined"}
                        startIcon={<Videocam/>}
                        onClick={() => send(mode === "follow" ? {mode: "all"} : {mode: "follow", scoreboard})}
                    >
                        {i18n.t("bracket_focus_follow")}
                    </Button>
                    <TextField
                        size="small"
                        type="number"
                        label={i18n.t("scoreboard")}
                        value={scoreboard}
                        sx={{width: 110}}
                        slotProps={{htmlInput: {min: 1}}}
                        onChange={(e) => {
                            const value = Math.max(1, parseInt(e.target.value) || 1);
                            setScoreboard(value);
                            if (mode === "follow") send({mode: "follow", scoreboard: value});
                        }}
                    />
                </Stack>

                <Stack direction="row" spacing={1} alignItems="center">
                    <Button
                        variant={mode === "tour" ? "contained" : "outlined"}
                        startIcon={<Loop/>}
                        onClick={() => send(mode === "tour" ? {mode: "all"} : {mode: "tour", interval})}
                    >
                        {i18n.t("bracket_focus_tour")}
                    </Button>
                    <TextField
                        size="small"
                        type="number"
                        label={i18n.t("bracket_focus_seconds")}
                        value={interval}
                        sx={{width: 110}}
                        slotProps={{htmlInput: {min: 2, max: 300}}}
                        onChange={(e) => {
                            const value = Math.min(300, Math.max(2, parseInt(e.target.value) || 8));
                            setIntervalValue(value);
                            if (mode === "tour") send({mode: "tour", interval: value});
                        }}
                    />
                </Stack>

                <FormControl size="small" sx={{minWidth: 200}}>
                    <InputLabel>{i18n.t("bracket_focus_player")}</InputLabel>
                    <Select
                        label={i18n.t("bracket_focus_player")}
                        value={mode === "player" && focus.player ? focus.player : ""}
                        onChange={(e) => send(e.target.value ? {mode: "player", player: e.target.value} : {mode: "all"})}
                        startAdornment={<Person sx={{marginRight: 1}}/>}
                    >
                        <MenuItem value="">—</MenuItem>
                        {players.map((p) => <MenuItem key={p.id} value={p.id}>
                            {p.seed ? `${p.seed}. ` : ""}{p.name}
                        </MenuItem>)}
                    </Select>
                </FormControl>
            </Stack>
        </Paper>

        {rounds.length === 0
            ? <Paper elevation={2} sx={{padding: 2}}>{i18n.t("bracket_focus_no_bracket")}</Paper>
            : <Box sx={{display: "flex", gap: 2, overflowX: "auto", paddingBottom: 1}}>
                {rounds.map((round) => <Paper
                    key={round.key}
                    elevation={2}
                    sx={{
                        minWidth: 220,
                        flexShrink: 0,
                        padding: 1,
                        outline: roundsInFocus.has(round.key) ? "2px solid" : "none",
                        outlineColor: "primary.main",
                    }}
                >
                    <Stack direction="row" alignItems="center">
                        <Checkbox
                            size="small"
                            checked={selectedRounds.has(round.key)}
                            onChange={() => toggle(selectedRounds, round.key, setSelectedRounds)}
                        />
                        <Typography variant="subtitle2" sx={{flexGrow: 1}}>{round.name}</Typography>
                        <Tooltip title={i18n.t("bracket_focus_round")}>
                            <IconButton size="small" onClick={() => send({mode: "rounds", rounds: [round.key]})}>
                                <CenterFocusStrong fontSize="small"/>
                            </IconButton>
                        </Tooltip>
                    </Stack>
                    <Stack spacing={1}>
                        {round.sets.map((set) => <SetCard
                            key={set.id}
                            set={set}
                            selected={selected.has(set.id)}
                            focused={inFocus.has(set.id)}
                            onToggle={() => toggle(selected, set.id, setSelected)}
                            onFocus={() => send({mode: "sets", sets: [set.id]})}
                        />)}
                    </Stack>
                </Paper>)}
            </Box>}

        {/* What's selected, always in reach */}
        <Paper
            elevation={6}
            sx={{
                position: "fixed", left: 0, right: 0, bottom: 0, padding: 1.5,
                display: "flex", gap: 1, justifyContent: "center", alignItems: "center",
            }}
        >
            <Button
                variant="contained"
                size="large"
                startIcon={<CenterFocusStrong/>}
                disabled={count === 0}
                onClick={focusSelected}
            >
                {count
                    ? i18n.t("bracket_focus_selected_n", {value: count})
                    : i18n.t("bracket_focus_selected")}
            </Button>
            <Button size="large" startIcon={<Clear/>} disabled={count === 0} onClick={clearSelection}>
                {i18n.t("bracket_focus_unselect")}
            </Button>
        </Paper>
    </Box>;
}

function SetCard({set, selected, focused, onToggle, onFocus}) {
    return <Paper
        variant="outlined"
        onClick={onToggle}
        sx={{
            padding: 1,
            cursor: "pointer",
            userSelect: "none",
            borderWidth: selected || focused ? 2 : 1,
            borderStyle: selected ? "dashed" : "solid",
            borderColor: focused ? "primary.main" : selected ? "text.primary" : "divider",
            opacity: set.completed && !focused && !selected ? 0.7 : 1,
        }}
    >
        <Stack direction="row" alignItems="center" spacing={1}>
            <Typography variant="caption" sx={{opacity: 0.6, minWidth: 16}}>{set.identifier}</Typography>
            <Box sx={{flexGrow: 1, minWidth: 0}}>
                {set.players.map((name, i) => <Typography
                    key={i}
                    variant="body2"
                    noWrap
                    sx={{fontStyle: name ? "normal" : "italic", opacity: name ? 1 : 0.5}}
                >
                    {name || i18n.t("bracket_focus_tbd")}
                </Typography>)}
            </Box>
            <Tooltip title={i18n.t("bracket_focus_this_set")}>
                <IconButton
                    size="small"
                    onClick={(e) => {
                        e.stopPropagation();
                        onFocus();
                    }}
                >
                    <CenterFocusStrong fontSize="small"/>
                </IconButton>
            </Tooltip>
        </Stack>
    </Paper>;
}
