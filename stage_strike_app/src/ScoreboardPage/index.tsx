import React from "react";
import {ChevronRight, ListOrdered, Radio} from "lucide-react";
import {shallowEqual, useDispatch, useSelector} from "react-redux";
import i18n from "../i18n/config";
import CurrentSet from "./CurrentSet";
import UpcomingSets from "./UpcomingSets";
import {Header} from "./Header";
import {teamDisplayName, useMediaQuery, WIDE_SCREEN} from "./setProgress";
import {hdStore, type ReduxState} from "../redux/store";
import {hdStateSlice} from "../redux/hdState";
import websocketInit from "./websocketInit";
import websocketConnection from "../websocketConnection";
import {selectedScoreboardSlice} from "../redux/uiState";
import type {HDScoreInfo, HDState} from "../backendDataTypes";
import {Card, CardContent} from "@/components/ui/card";
import {Spinner} from "@/components/ui/spinner";
import {cn} from "@/lib/utils";

type View = "live" | "queue";

/** On phones, the live score above the queue, going back to it when tapped */
function LiveScoreBar({score, onClick}: {score: HDScoreInfo; onClick: () => void}) {
    if (!score?.team?.["1"] || !score?.team?.["2"]) {
        return null;
    }
    const side = (team: 1 | 2) => (
        <span className={cn("flex min-w-0 flex-1 items-center gap-2", team === 2 && "flex-row-reverse")}>
            <span aria-hidden className="size-2 shrink-0 rounded-full" style={{backgroundColor: score.team[team].color || undefined}}/>
            <span className="truncate font-semibold">{teamDisplayName(score.team[team], team)}</span>
        </span>
    );
    return (
        <button
            type="button"
            onClick={onClick}
            aria-label={i18n.t("back_to_live")}
            className="flex h-14 w-full cursor-pointer items-center gap-3 rounded-xl border bg-card px-3 text-left outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
        >
            <span className="flex items-center gap-1.5 text-[11px] font-semibold tracking-wider text-pick uppercase">
                <span aria-hidden className="size-1.5 rounded-full bg-pick"/>{i18n.t("live")}
            </span>
            {side(1)}
            <span className="shrink-0 text-xl font-black tabular-nums">
                {Number(score.team[1].score ?? 0)}–{Number(score.team[2].score ?? 0)}
            </span>
            {side(2)}
            <ChevronRight className="size-4 shrink-0 text-muted-foreground"/>
        </button>
    );
}

/** Live / Up next, at the bottom of the screen on phones */
function BottomNav({view, onChange}: {view: View; onChange: (view: View) => void}) {
    const tab = (value: View, icon: React.ReactNode, label: string) => (
        <button
            type="button"
            aria-current={view === value ? "page" : undefined}
            onClick={() => onChange(value)}
            className={cn(
                "flex cursor-pointer flex-col items-center justify-center gap-1 text-xs outline-none focus-visible:bg-accent [&_svg]:size-5",
                view === value ? "font-semibold text-foreground" : "text-muted-foreground",
            )}
        >
            {icon}{label}
        </button>
    );
    return (
        <nav className="fixed inset-x-0 bottom-0 z-40 grid h-[calc(4.5rem+env(safe-area-inset-bottom))] grid-cols-2 border-t bg-background/95 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden">
            {tab("live", <Radio/>, i18n.t("live"))}
            {tab("queue", <ListOrdered/>, i18n.t("up_next"))}
        </nav>
    );
}

/**
 * Main page for the scoreboard. This whole contraption is powered by HyperDrive's python-side
 * program state. In order to do that, we subscribe to updates that get sent out and update
 * our state piecemeal. Each update has a number so that we can tell if our updates are stale
 * or out of order and request a full state send-over.
 *
 * Wide screens show the scoreboard and the queue side by side; phones switch
 * between them with tabs at the bottom.
 */
export default function ScoreboardPage() {
    const dispatch = useDispatch();
    const {loading, errored, selectedScoreboard, scoreboards} = useSelector((state: ReduxState) => ({
        loading: (
            state.hdState.initializing
            || state.hdCharacters.initializing
            || state.hdPlayers.initializing
            || state.hdGames.initializing
            || state.hdCountries.initializing
        ),
        errored: state.websocketInfo.status === "errored",
        scoreboards: state.hdState.hdState.score,
        selectedScoreboard: state.selectedScoreboard.value
    }), shallowEqual);
    const wide = useMediaQuery(WIDE_SCREEN);
    const [view, setView] = React.useState<View>("live");
    const scrollRef = React.useRef<HTMLDivElement>(null);
    const searchRef = React.useRef<HTMLInputElement>(null);

    React.useEffect(() => {
        document.title = `HyperDrive ${i18n.t("scoreboard")}`;
        websocketInit();
    }, []);

    const changeView = (next: View) => {
        setView(next);
        scrollRef.current?.scrollTo({top: 0});
    };

    const onSetLoaded = () => {
        dispatch(hdStateSlice.actions.loadingNewData({}));
        changeView("live");
    };

    const onLoadNext = () => {
        if (wide) {
            searchRef.current?.focus();
        } else {
            changeView("queue");
        }
    };

    const onSelectedGameChanged = (newGame: string) => {
        websocketConnection.instance().emit('update_game', {codename: newGame});
    };

    const score = scoreboards?.[selectedScoreboard];

    let body;
    if (errored || loading) {
        body = (
            <Card className="m-4 py-4">
                <CardContent className="flex items-center gap-3 text-sm">
                    {errored ? i18n.t("failed_to_connect") : <><Spinner/>{i18n.t("loading")}</>}
                </CardContent>
            </Card>
        );
    } else {
        body = (
            <>
                <Header
                    onSelectedGameChange={onSelectedGameChanged}
                    scoreboards={scoreboardKeys(scoreboards)}
                    selectedScoreboard={selectedScoreboard}
                    onSelectedScoreboardChange={(sb) =>
                        hdStore.dispatch(selectedScoreboardSlice.actions.setSelectedScoreboard(sb))}
                />
                {/* Room at the bottom for the tab bar on phones */}
                <div className="mx-auto grid w-full max-w-7xl grid-cols-1 items-start gap-6 px-4 pt-4 pb-28 lg:grid-cols-[minmax(0,1fr)_22rem] lg:px-6 lg:pb-8 xl:grid-cols-[minmax(0,1fr)_26rem]">
                    <main className={cn("min-w-0", view !== "live" && "hidden lg:block")}>
                        <CurrentSet scoreboardNumber={selectedScoreboard} wide={wide} onLoadNext={onLoadNext}/>
                    </main>
                    <aside className={cn(
                        "flex min-w-0 flex-col gap-4 lg:sticky lg:top-4 lg:max-h-[calc(100dvh-7rem)] lg:overflow-y-auto lg:rounded-2xl lg:border lg:bg-card/50 lg:p-4",
                        view !== "queue" && "hidden lg:flex",
                    )}>
                        {!wide && <LiveScoreBar score={score} onClick={() => changeView("live")}/>}
                        <UpcomingSets
                            scoreboardNumber={selectedScoreboard}
                            currentSetId={score?.set_id}
                            onSetLoaded={onSetLoaded}
                            searchRef={searchRef}
                        />
                    </aside>
                </div>
                <BottomNav view={view} onChange={changeView}/>
            </>
        );
    }

    return <div ref={scrollRef} className="flex h-dvh flex-col overflow-auto bg-background text-foreground">{body}</div>;
}

const scoreboardKeys = (scoreboards: HDState['score']) => {
    if (scoreboards) {
        return Object.keys(scoreboards)
            .filter(k => k.match(/^\d+$/))
            .map(k => Number.parseInt(k));
    } else {
        return [];
    }
};
