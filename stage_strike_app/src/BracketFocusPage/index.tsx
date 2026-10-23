import {Fragment, useCallback, useEffect, useRef, useState} from "react";
import {
    ChevronLeft,
    ChevronRight,
    ChevronsDown,
    ChevronsUp,
    Focus,
    Maximize,
    Repeat,
    User,
    Video,
    X,
} from "lucide-react";
import i18n from "../i18n/config";
import websocketConnection from "../websocketConnection";
import {Field} from "@/components/Field";
import {Badge} from "@/components/ui/badge";
import {Button} from "@/components/ui/button";
import {ButtonGroup} from "@/components/ui/button-group";
import {Card} from "@/components/ui/card";
import {Checkbox} from "@/components/ui/checkbox";
import {Input} from "@/components/ui/input";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectSeparator,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import {Tooltip, TooltipContent, TooltipTrigger} from "@/components/ui/tooltip";
import {cn} from "@/lib/utils";

interface FocusSet {
    id: string;
    identifier?: string;
    players: string[];
    completed?: boolean;
}

interface FocusRound {
    key: string;
    name: string;
    sets: FocusSet[];
}

interface FocusState {
    channel: string;
    channels?: string[];
    name?: string;
    phase?: string;
    phases?: {value: string; label: string; section?: string}[];
    rounds?: FocusRound[];
    players?: {id: string; name: string; seed?: number}[];
    focus?: {
        mode: "all" | "sets" | "rounds" | "side" | "follow" | "tour" | "player";
        side?: "winners" | "losers";
        sets?: string[];
        rounds?: string[];
        label?: string;
        step?: number;
        steps?: number;
        scoreboard?: number;
        interval?: number;
        player?: string;
    };
}

// Radix's Select can't have an empty value
const NO_PLAYER = "__none__";

/** A button with its tooltip */
function TipButton({tip, ...props}: React.ComponentProps<typeof Button> & {tip: string}) {
    return <Tooltip>
        <TooltipTrigger asChild>
            <Button aria-label={tip} {...props}/>
        </TooltipTrigger>
        <TooltipContent>{tip}</TooltipContent>
    </Tooltip>;
}

/**
 * Remote for the bracket focus layout (layout/bracket_focus): what it zooms
 * to, like the bracket widget's "Layout focus" bar. Tap sets (and rounds)
 * to select them, then "Focus selected"; or focus the winners or losers side,
 * a player's run, follow a scoreboard's set, or tour the rounds. On a focus channel (?channel=<name>,
 * "main" by default): each layout shows one.
 */
export default function BracketFocusPage() {
    const [state, setState] = useState<FocusState | null>(null);
    const [connected, setConnected] = useState(false);
    const [selected, setSelected] = useState(new Set<string>());
    const [selectedRounds, setSelectedRounds] = useState(new Set<string>());
    const [scoreboard, setScoreboard] = useState(1);
    const [interval, setIntervalValue] = useState(8);
    const [channel, setChannel] = useState(
        () => new URLSearchParams(window.location.search).get("channel") || "main"
    );
    const refreshTimer = useRef<ReturnType<typeof setTimeout>>(null);
    // For the socket's callbacks, which outlive renders
    const channelRef = useRef(channel);
    const pickChannelRef = useRef<(name: string) => void>(null);

    useEffect(() => {
        document.title = `HyperDrive ${i18n.t("bracket_focus")}`;
    }, []);

    useEffect(() => {
        const socket = websocketConnection.instance();
        const request = () => socket.emit("bracket_focus", {channel: channelRef.current});
        const onConnect = () => {
            setConnected(true);
            request();
        };
        const onDisconnect = () => setConnected(false);
        const onFocus = (data: FocusState | [string]) => {
            // The channel was removed (or never was): back to main
            if (Array.isArray(data)) {
                if (data[0] === "NO_CHANNEL" && channelRef.current !== "main") {
                    pickChannelRef.current("main");
                }
                return;
            }
            // Answers about a channel picked before don't count
            if (data && typeof data === "object" && !Array.isArray(data) && data.channel === channelRef.current) {
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
    const pickChannel = (name: string) => {
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

    const focus: FocusState["focus"] = state?.focus ?? {mode: "all", sets: [], rounds: []};
    const mode = focus.mode;

    // Keep the inputs in step with what's running
    useEffect(() => {
        if (focus.scoreboard) setScoreboard(focus.scoreboard);
        if (focus.interval) setIntervalValue(focus.interval);
    }, [focus.scoreboard, focus.interval]);

    const send = useCallback((request: object) => {
        websocketConnection.instance().emit("bracket_focus_set", {...request, channel: channelRef.current});
    }, []);

    const toggle = (set: Set<string>, value: string, setter: (next: Set<string>) => void) => {
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

    // The phase the channel shows, from the bracket widget's phases (built
    // there or start.gg phase groups loaded there). The sets picked were the
    // old one's.
    const phases = state?.phases ?? [];
    const pickPhase = (value: string) => {
        clearSelection();
        send({phase: value});
    };

    const inFocus = new Set(focus.sets ?? []);
    const roundsInFocus = new Set(focus.rounds ?? []);
    const count = selected.size + selectedRounds.size;
    const rounds = state?.rounds ?? [];
    const players = state?.players ?? [];
    // The sides the bracket has (the grand final goes with winners): no
    // losers side in single elimination
    const sides = [
        {side: "winners", icon: ChevronsUp, label: i18n.t("bracket_focus_winners"), tip: i18n.t("bracket_focus_winners_tip"), sides: ["winners", "grand_final"]},
        {side: "losers", icon: ChevronsDown, label: i18n.t("bracket_focus_losers"), tip: i18n.t("bracket_focus_losers_tip"), sides: ["losers"]},
    ] as const;
    const hasSide = (keys: readonly string[]) =>
        rounds.some((round) => round.sets.length && keys.includes(round.key.split(":")[0]));

    let status = i18n.t("bracket_focus_all");
    if (inFocus.size) {
        status = focus.label || i18n.t("bracket_focus_n_sets", {value: inFocus.size});
        if (mode === "tour") {
            status = `${(focus.step ?? 0) + 1}/${focus.steps ?? 1} · ${status}`;
        }
    } else if (mode === "follow") {
        status = i18n.t("bracket_focus_follow_none", {value: focus.scoreboard ?? 1});
    }

    const channels = state?.channels ?? [channel];

    return <div className="mx-auto max-w-[1400px] p-4 pb-28 text-foreground">
        <div className="mb-4 flex flex-wrap items-end gap-2">
            <h1 className="grow text-2xl font-semibold tracking-tight">
                {i18n.t("bracket_focus")}{state?.name ? ` · ${state.name}` : ""}
            </h1>
            <Field label={i18n.t("bracket_focus_channel")} htmlFor="bf-channel" className="min-w-36">
                <Select value={channels.includes(channel) ? channel : undefined} onValueChange={pickChannel}>
                    <SelectTrigger id="bf-channel" className="w-full"><SelectValue/></SelectTrigger>
                    <SelectContent>
                        {channels.map((name) => (
                            <SelectItem key={name} value={name}>{name === "main" ? i18n.t("bracket_focus_main_channel") : name}</SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </Field>
            <Field label={i18n.t("bracket_focus_phase")} htmlFor="bf-phase" className="min-w-44">
                <Select
                    value={phases.some((p) => p.value === state?.phase) ? state.phase : undefined}
                    onValueChange={pickPhase}
                    disabled={!phases.length}
                >
                    <SelectTrigger id="bf-phase" className="w-full"><SelectValue/></SelectTrigger>
                    <SelectContent>
                        {phases.map((p, i) => <Fragment key={p.value}>
                            {i > 0 && p.section !== phases[i - 1].section && <SelectSeparator/>}
                            <SelectItem value={p.value}>
                                {p.section === "startgg" ? `${p.label} · start.gg` : p.label}
                            </SelectItem>
                        </Fragment>)}
                    </SelectContent>
                </Select>
            </Field>
            <Badge
                variant="outline"
                className={cn("mb-2", connected ? "border-pick/50 text-pick" : "border-warning/50 text-warning")}
            >
                <span className={cn("size-1.5 rounded-full", connected ? "bg-pick" : "animate-pulse bg-warning")}/>
                {connected ? i18n.t("connected") : i18n.t("connecting")}
            </Badge>
        </div>

        <Card className="mb-4 gap-3 p-4">
            <div>
                <div className="text-xs font-medium tracking-wider text-muted-foreground uppercase">
                    {i18n.t("bracket_focus_showing")}
                </div>
                <div className="text-lg font-semibold">{status}</div>
            </div>

            <div className="flex flex-wrap items-end gap-2">
                <Button variant={mode === "all" ? "default" : "outline"} onClick={() => send({mode: "all"})}>
                    <Maximize/>
                    {i18n.t("bracket_focus_whole")}
                </Button>
                <ButtonGroup>
                    <TipButton variant="outline" size="icon" tip={i18n.t("bracket_focus_previous")} onClick={() => send({move: -1})}>
                        <ChevronLeft/>
                    </TipButton>
                    <TipButton variant="outline" size="icon" tip={i18n.t("bracket_focus_next")} onClick={() => send({move: 1})}>
                        <ChevronRight/>
                    </TipButton>
                </ButtonGroup>

                <ButtonGroup>
                    {sides.map(({side, icon: Icon, label, tip, sides: keys}) => {
                        const on = mode === "side" && focus.side === side;
                        return <Tooltip key={side}>
                            <TooltipTrigger asChild>
                                <Button
                                    variant={on ? "default" : "outline"}
                                    disabled={!on && !hasSide(keys)}
                                    onClick={() => send(on ? {mode: "all"} : {mode: "side", side})}
                                >
                                    <Icon/>
                                    {label}
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent>{tip}</TooltipContent>
                        </Tooltip>;
                    })}
                </ButtonGroup>

                <div className="flex items-end gap-2">
                    <Button
                        variant={mode === "follow" ? "default" : "outline"}
                        onClick={() => send(mode === "follow" ? {mode: "all"} : {mode: "follow", scoreboard})}
                    >
                        <Video/>
                        {i18n.t("bracket_focus_follow")}
                    </Button>
                    <Field label={i18n.t("scoreboard")} htmlFor="bf-scoreboard">
                        <Input
                            id="bf-scoreboard"
                            type="number"
                            min={1}
                            value={scoreboard}
                            className="w-24"
                            onChange={(e) => {
                                const value = Math.max(1, parseInt(e.target.value) || 1);
                                setScoreboard(value);
                                if (mode === "follow") send({mode: "follow", scoreboard: value});
                            }}
                        />
                    </Field>
                </div>

                <div className="flex items-end gap-2">
                    <Button
                        variant={mode === "tour" ? "default" : "outline"}
                        onClick={() => send(mode === "tour" ? {mode: "all"} : {mode: "tour", interval})}
                    >
                        <Repeat/>
                        {i18n.t("bracket_focus_tour")}
                    </Button>
                    <Field label={i18n.t("bracket_focus_seconds")} htmlFor="bf-interval">
                        <Input
                            id="bf-interval"
                            type="number"
                            min={2}
                            max={300}
                            value={interval}
                            className="w-24"
                            onChange={(e) => {
                                const value = Math.min(300, Math.max(2, parseInt(e.target.value) || 8));
                                setIntervalValue(value);
                                if (mode === "tour") send({mode: "tour", interval: value});
                            }}
                        />
                    </Field>
                </div>

                <Field label={i18n.t("bracket_focus_player")} htmlFor="bf-player" className="min-w-52">
                    <Select
                        value={mode === "player" && focus.player ? focus.player : NO_PLAYER}
                        onValueChange={(value) => send(value !== NO_PLAYER ? {mode: "player", player: value} : {mode: "all"})}
                    >
                        <SelectTrigger id="bf-player" className="w-full">
                            <User/>
                            <SelectValue/>
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value={NO_PLAYER}>—</SelectItem>
                            {players.map((p) => <SelectItem key={p.id} value={p.id}>
                                {p.seed ? `${p.seed}. ` : ""}{p.name}
                            </SelectItem>)}
                        </SelectContent>
                    </Select>
                </Field>
            </div>
        </Card>

        {rounds.length === 0
            ? <Card className="p-4 text-sm text-muted-foreground">{i18n.t("bracket_focus_no_bracket")}</Card>
            : <div className="flex gap-4 overflow-x-auto pb-2">
                {rounds.map((round) => <Card
                    key={round.key}
                    className={cn(
                        "min-w-56 shrink-0 gap-2 p-2",
                        roundsInFocus.has(round.key) && "ring-2 ring-primary",
                    )}
                >
                    <div className="flex items-center gap-2 pl-1">
                        <Checkbox
                            aria-label={round.name}
                            checked={selectedRounds.has(round.key)}
                            onCheckedChange={() => toggle(selectedRounds, round.key, setSelectedRounds)}
                        />
                        <span className="grow text-sm font-medium">{round.name}</span>
                        <TipButton
                            variant="ghost"
                            size="icon-sm"
                            tip={i18n.t("bracket_focus_round")}
                            onClick={() => send({mode: "rounds", rounds: [round.key]})}
                        >
                            <Focus/>
                        </TipButton>
                    </div>
                    <div className="flex flex-col gap-2">
                        {round.sets.map((set) => <SetCard
                            key={set.id}
                            set={set}
                            selected={selected.has(set.id)}
                            focused={inFocus.has(set.id)}
                            onToggle={() => toggle(selected, set.id, setSelected)}
                            onFocus={() => send({mode: "sets", sets: [set.id]})}
                        />)}
                    </div>
                </Card>)}
            </div>}

        {/* What's selected, always in reach */}
        <div className="fixed inset-x-0 bottom-0 flex items-center justify-center gap-2 border-t bg-background/90 p-3 backdrop-blur">
            <Button size="lg" disabled={count === 0} onClick={focusSelected}>
                <Focus/>
                {count
                    ? i18n.t("bracket_focus_selected_n", {value: count})
                    : i18n.t("bracket_focus_selected")}
            </Button>
            <Button size="lg" variant="ghost" disabled={count === 0} onClick={clearSelection}>
                <X/>
                {i18n.t("bracket_focus_unselect")}
            </Button>
        </div>
    </div>;
}

function SetCard({set, selected, focused, onToggle, onFocus}: {
    set: FocusSet;
    selected: boolean;
    focused: boolean;
    onToggle: () => void;
    onFocus: () => void;
}) {
    return <div
        role="button"
        tabIndex={0}
        aria-pressed={selected}
        onClick={onToggle}
        onKeyDown={(e) => {
            if (e.target === e.currentTarget && (e.key === "Enter" || e.key === " ")) {
                e.preventDefault();
                onToggle();
            }
        }}
        className={cn(
            "flex cursor-pointer items-center gap-2 rounded-lg border bg-background/40 p-2 select-none outline-none",
            "transition-colors hover:bg-accent/50 focus-visible:ring-[3px] focus-visible:ring-ring/50",
            (selected || focused) && "border-2",
            selected && "border-dashed",
            focused ? "border-primary" : selected && "border-foreground",
            set.completed && !focused && !selected && "opacity-70",
        )}
    >
        <span className="min-w-4 text-xs text-muted-foreground">{set.identifier}</span>
        <div className="min-w-0 grow">
            {set.players.map((name, i) => <div
                key={i}
                className={cn("truncate text-sm", !name && "italic opacity-50")}
            >
                {name || i18n.t("bracket_focus_tbd")}
            </div>)}
        </div>
        <TipButton
            variant="ghost"
            size="icon-sm"
            tip={i18n.t("bracket_focus_this_set")}
            onClick={(e) => {
                e.stopPropagation();
                onFocus();
            }}
        >
            <Focus/>
        </TipButton>
    </div>;
}
