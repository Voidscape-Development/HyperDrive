import React from "react";
import {CircleAlert, CircleCheck, LayoutDashboard, ListPlus, RefreshCw, Tv} from "lucide-react";
import {Link} from "react-router-dom";
import {shallowEqual, useDispatch, useSelector} from "react-redux";
import i18n from "../i18n/config";
import {BASE_URL} from "../env";
import {ScoreboardTabs} from "./ScoreboardTabs";
import {ScorePanel} from "./ScorePanel";
import {TeamColumn} from "./TeamColumn";
import UpcomingSets from "./UpcomingSets";
import {api} from "./api";
import {useSaveStatus} from "./saveStatus";
import websocketInit from "./websocketInit";
import {dashboard} from "../Dashboard/api";
import {PinGate} from "../Dashboard/PinGate";
import {useStatus} from "../Dashboard/status";
import {OptionsBar, PageBody, Stepper} from "../Dashboard/ui";
import {hdStateSlice} from "../redux/hdState";
import {selectedScoreboardSlice} from "../redux/uiState";
import type {ReduxState} from "../redux/store";
import type {HDScoreInfo} from "../backendDataTypes";
import {Badge} from "@/components/ui/badge";
import {Button} from "@/components/ui/button";
import {Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle} from "@/components/ui/sheet";
import {cn} from "@/lib/utils";

const countOf = (obj: object) => Object.keys(obj ?? {}).length;

/** Whether the changes made on this page have reached HyperDrive. */
function SaveStatus() {
    const status = useSaveStatus();
    if (status === "idle") {
        return null;
    }
    const chip = {
        saving: {icon: <RefreshCw className="animate-spin"/>, label: i18n.t("saving"), className: "text-muted-foreground"},
        saved: {icon: <CircleCheck/>, label: i18n.t("saved"), className: "border-pick/50 text-pick"},
        error: {icon: <CircleAlert/>, label: i18n.t("save_failed"), className: "border-destructive/50 text-destructive"},
    }[status];
    return <Badge variant="outline" className={chip.className}>{chip.icon}{chip.label}</Badge>;
}

const TRACKING: Record<string, string> = {
    stream: "Tracking its stream",
    station: "Tracking its station",
    set: "Keeping this set updated",
};

/** The scoreboard follows a stream, a station or a set, from the desktop app */
function TrackingBar({scoreboardNumber, mode}: {scoreboardNumber: number; mode?: string}) {
    if (!mode || !TRACKING[mode]) {
        return null;
    }
    return (
        <div className="flex flex-wrap items-center gap-3 rounded-xl border bg-card px-4 py-2.5 text-[13px]">
            <span aria-hidden className="size-2 rounded-full bg-live"/>
            <span className="font-semibold">{TRACKING[mode]}</span>
            <span className="text-muted-foreground">New sets load by themselves.</span>
            <div className="flex-1"/>
            <Button variant="outline" size="sm" onClick={() => dashboard.scoreboards.stopTracking(scoreboardNumber).catch(() => {})}>
                Stop
            </Button>
        </div>
    );
}

/** The players per team and characters per player of a scoreboard */
function CardOptions({scoreboardNumber, score}: {scoreboardNumber: number; score: HDScoreInfo}) {
    const teams = Object.values(score?.team ?? {});
    const players = Math.max(1, ...teams.map((t) => countOf(t?.player)));
    const firstPlayer = Object.values(teams[0]?.player ?? {})[0];
    const characters = countOf(firstPlayer?.character);
    return (
        <OptionsBar>
            <Stepper label={i18n.t("players_per_team")} value={players} min={1} max={8}
                onChange={(value) => api.setInfo(scoreboardNumber, {players: value}).catch(() => {})}/>
            <Stepper label={i18n.t("characters_per_player")} value={characters} min={0} max={8}
                onChange={(value) => api.setInfo(scoreboardNumber, {characters: value}).catch(() => {})}/>
        </OptionsBar>
    );
}

/**
 * The Scoreboard section: a tab per scoreboard, then the selected one's
 * teams on either side of its score, as in the desktop app's Scoreboard
 * Manager. On phones the score comes first, then each team.
 */
export function ScoreboardSection() {
    const dispatch = useDispatch();
    const status = useStatus();
    const {selected, scores} = useSelector((s: ReduxState) => ({
        selected: s.selectedScoreboard.value,
        scores: s.hdState.hdState?.score,
    }), shallowEqual);
    const [loadOpen, setLoadOpen] = React.useState(false);

    const scoreboards = status?.scoreboards ?? [{number: 1, name: i18n.t("scoreboard_n", {value: 1})}];
    // A scoreboard removed elsewhere: back to the first one
    const number = scoreboards.some((s) => s.number === selected) ? selected : scoreboards[0].number;
    const select = (n: number) => dispatch(selectedScoreboardSlice.actions.setSelectedScoreboard(n));
    const score: HDScoreInfo = scores?.[number];
    const tracking = (score as unknown as {auto_update?: string})?.auto_update;

    return (
        <PageBody>
            <ScoreboardTabs scoreboards={scoreboards} selected={number} onSelect={select}/>

            <header className="flex flex-wrap items-center gap-3">
                {/* On phones the tab shows the name */}
                <h1 className="min-w-0 flex-1 truncate text-2xl font-bold tracking-tight max-lg:sr-only">
                    {scoreboards.find((s) => s.number === number)?.name}
                </h1>
                <SaveStatus/>
                <Button variant="secondary" onClick={() => setLoadOpen(true)}><ListPlus/>Load a set…</Button>
                <Button variant="secondary" title={i18n.t("load_stream_set")} onClick={() => api.pullStreamSet(number).catch(() => {})}>
                    <Tv/>{i18n.t("stream_set_short")}
                </Button>
            </header>

            <TrackingBar scoreboardNumber={number} mode={tracking}/>

            {!score?.team?.[1] || !score?.team?.[2]
                ? <p className="text-lg font-medium">{i18n.t("no_set")}</p>
                : (
                    <>
                        <CardOptions scoreboardNumber={number} score={score}/>
                        <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-[minmax(0,1fr)_19rem_minmax(0,1fr)]">
                            <TeamColumn key={`${number}-1`} scoreboardNumber={number} teamNumber={1} team={score.team[1]} className="order-2 lg:order-1"/>
                            <ScorePanel key={number} scoreboardNumber={number} score={score} onLoadNext={() => setLoadOpen(true)} className="order-1 lg:order-2 lg:sticky lg:top-4"/>
                            <TeamColumn key={`${number}-2`} scoreboardNumber={number} teamNumber={2} team={score.team[2]} className="order-3"/>
                        </div>
                    </>
                )}

            <Sheet open={loadOpen} onOpenChange={setLoadOpen}>
                <SheetContent side="right" className="w-full gap-0 sm:max-w-md">
                    <SheetHeader className="border-b">
                        <SheetTitle>Load a set</SheetTitle>
                        <SheetDescription>Into {scoreboards.find((s) => s.number === number)?.name}</SheetDescription>
                    </SheetHeader>
                    <div className="min-h-0 flex-1 overflow-y-auto p-4">
                        <UpcomingSets
                            scoreboardNumber={number}
                            currentSetId={score?.set_id}
                            onSetLoaded={() => {
                                dispatch(hdStateSlice.actions.loadingNewData({}));
                                setLoadOpen(false);
                            }}
                        />
                    </div>
                </SheetContent>
            </Sheet>
        </PageBody>
    );
}

/**
 * /scoreboard: the same section on its own, full screen, for a producer who
 * only runs the score. Behind the dashboard's PIN when there is one.
 */
export default function ScoreboardPage() {
    React.useEffect(() => {
        document.title = `HyperDrive ${i18n.t("scoreboard")}`;
        websocketInit();
    }, []);

    return (
        <PinGate>
            <div className="flex h-dvh flex-col bg-background text-foreground">
                <header className="flex items-center gap-3 border-b bg-card px-4 py-2.5">
                    <img alt="" src={`${BASE_URL}/assets/icons/icon.png`} className="size-8"/>
                    <span className="flex-1 font-semibold">{i18n.t("scoreboard")}</span>
                    <Button variant="ghost" asChild>
                        <Link to="/"><LayoutDashboard/>Dashboard</Link>
                    </Button>
                </header>
                <div className={cn("min-h-0 flex-1 overflow-y-auto")}>
                    <ScoreboardSection/>
                </div>
            </div>
        </PinGate>
    );
}
