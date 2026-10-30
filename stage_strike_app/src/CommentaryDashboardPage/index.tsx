import {useCallback, useEffect, useState} from "react";
import {shallowEqual, useSelector} from "react-redux";
import {useSearchParams} from "react-router-dom";
import i18n from "../i18n/config";
import {BASE_URL} from "../env";
import websocketInit from "../ScoreboardPage/websocketInit";
import type {ReduxState} from "../redux/store";
import type {DashboardState, Scoreboard} from "./types";
import {TeamColumn} from "./TeamColumn";
import {BracketStakes, GameLog, RefreshStatsButton, SetSummary} from "./Match";
import {HeadToHead} from "./Stats";
import {RecentResults, UpNext} from "./UpNext";
import {teamName, teamPlayers} from "./util";
import {Badge} from "@/components/ui/badge";
import {Card, CardContent} from "@/components/ui/card";
import {Spinner} from "@/components/ui/spinner";
import {Tabs, TabsList, TabsTrigger} from "@/components/ui/tabs";
import {cn} from "@/lib/utils";

const SCOREBOARD_KEY = "hd_commentary_scoreboard";

function readStoredScoreboard() {
    try {
        return Number.parseInt(localStorage.getItem(SCOREBOARD_KEY) ?? "") || 1;
    } catch {
        return 1;
    }
}

/**
 * The scoreboard the dashboard follows. ?scoreboard=<n> locks it (e.g. a link
 * for a second stream's commentators); without it, it's the last one picked
 * on this device.
 */
function useScoreboard() {
    const [params] = useSearchParams();
    const fromUrl = Number.parseInt(params.get("scoreboard") ?? "");
    const locked = fromUrl > 0;
    const [picked, setPicked] = useState(readStoredScoreboard);

    const pick = useCallback((number: number) => {
        try {
            localStorage.setItem(SCOREBOARD_KEY, String(number));
        } catch {}
        setPicked(number);
    }, []);

    return {scoreboard: locked ? fromUrl : picked, pick, locked};
}

/**
 * For the commentators: who's playing (their info, notes and stats), the set
 * (score, games, what's at stake in the bracket), and what's up next on the
 * stream. It only reads HyperDrive's program state, which it gets live like
 * the remote scoreboard.
 */
export default function CommentaryDashboardPage() {
    const {loading, status, state} = useSelector((s: ReduxState) => ({
        loading: s.hdState.initializing || s.hdCharacters.initializing || s.hdPlayers.initializing || s.hdCountries.initializing,
        status: s.websocketInfo.status,
        state: s.hdState.hdState as unknown as DashboardState,
    }), shallowEqual);
    const {scoreboard: wanted, pick, locked} = useScoreboard();

    useEffect(() => {
        document.title = `HyperDrive ${i18n.t("commentary_dashboard")}`;
        websocketInit();
    }, []);

    const numbers = Object.keys(state.score ?? {}).filter((k) => /^\d+$/.test(k)).map(Number).sort((a, b) => a - b);
    // A scoreboard removed in HyperDrive: the first one there is, unless the link asks for that one
    const scoreboardNumber = locked || numbers.includes(wanted) ? wanted : numbers[0] ?? 1;
    const scoreboard: Scoreboard | undefined = state.score?.[String(scoreboardNumber)];

    let body;
    if (status === "errored" || loading) {
        body = <Card className="m-4 py-4">
            <CardContent className="flex items-center gap-3 text-sm">
                {status === "errored" ? i18n.t("failed_to_connect") : <><Spinner/>{i18n.t("loading")}</>}
            </CardContent>
        </Card>;
    } else if (!scoreboard) {
        body = <Card className="m-4 py-4">
            <CardContent className="text-sm">{i18n.t("dashboard_scoreboard_missing", {value: scoreboardNumber})}</CardContent>
        </Card>;
    } else {
        const named = (team: 1 | 2) => teamPlayers(scoreboard.team?.[String(team)]).filter((p) => p.name);
        const singles = named(1).length === 1 && named(2).length === 1;
        const recent = scoreboard.recent_sets;
        const h2h = !singles ? null : recent?.state === "done" ? recent.sets ?? [] : recent ? undefined : [];

        body = <main className="mx-auto flex w-full max-w-[120rem] flex-col gap-4 p-4 fit:min-h-0 fit:flex-1 wide:flex-row">
            <div className="grid grid-cols-[minmax(0,1fr)] gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(22rem,28rem)_minmax(0,1fr)] fit:min-h-0 fit:flex-1 fit:grid-rows-[minmax(0,1fr)] wide:grid-cols-[minmax(0,1fr)_minmax(20rem,24rem)_minmax(0,1fr)]">
                <div className="flex min-w-0 flex-col gap-4 lg:order-2">
                    <SetSummary scoreboard={scoreboard}/>
                    <Card className="py-0 fit:min-h-0 fit:flex-1">
                        <CardContent className="flex flex-col gap-5 p-4 fit:scroll-panel">
                            {singles ? <HeadToHead
                                sets={h2h}
                                loading={recent?.state === "loading"}
                                names={[teamName(scoreboard.team?.["1"]), teamName(scoreboard.team?.["2"])]}
                                colors={[scoreboard.team?.["1"]?.color, scoreboard.team?.["2"]?.color]}
                            /> : null}
                            <BracketStakes state={state} scoreboard={scoreboard}/>
                            <GameLog scoreboard={scoreboard}/>
                        </CardContent>
                    </Card>
                </div>
                <div className="min-w-0 lg:order-1"><TeamColumn scoreboard={scoreboard} team={1}/></div>
                <div className="min-w-0 lg:order-3"><TeamColumn scoreboard={scoreboard} team={2}/></div>
            </div>
            {/* Under the players, or a column of its own on wide screens */}
            <div className="grid grid-cols-[minmax(0,1fr)] gap-4 lg:grid-cols-2 fit:h-[clamp(11rem,32%,20rem)] fit:shrink-0 fit:grid-rows-[minmax(0,1fr)] wide:h-auto wide:w-[26rem] wide:grid-cols-[minmax(0,1fr)] wide:grid-rows-[minmax(0,3fr)_minmax(0,2fr)]">
                <UpNext state={state} scoreboardNumber={scoreboardNumber}/>
                <RecentResults state={state}/>
            </div>
        </main>;
    }

    // On big enough screens, the page is the window's size and its panels scroll instead
    return <div className="min-h-dvh bg-background text-foreground fit:flex fit:h-dvh fit:flex-col fit:overflow-hidden">
        <header className="sticky top-0 z-10 flex shrink-0 flex-wrap items-center gap-x-6 gap-y-2 border-b bg-card/95 px-4 py-2 backdrop-blur">
            <div className="flex items-center gap-3">
                <img alt="HyperDrive logo" src={`${BASE_URL}/assets/icons/icon.png`} className="size-8"/>
                <h1 className="font-semibold tracking-tight whitespace-nowrap">{i18n.t("commentary_dashboard")}</h1>
            </div>
            <div className="min-w-0 truncate text-sm">
                <span>{state.tournamentInfo?.tournamentName}</span>
                {state.tournamentInfo?.eventName ? <span className="text-muted-foreground"> · {state.tournamentInfo.eventName}</span> : null}
                {state.tournamentInfo?.numEntrants ? <span className="text-muted-foreground"> · {i18n.t("entrants_n", {value: state.tournamentInfo.numEntrants})}</span> : null}
            </div>
            <div className="ml-auto flex flex-wrap items-center justify-end gap-3">
                {scoreboard ? <RefreshStatsButton scoreboardNumber={scoreboardNumber}/> : null}
                {!locked && numbers.length > 1 ? <Tabs value={String(scoreboardNumber)} onValueChange={(v) => pick(Number(v))}>
                    <TabsList>
                        {numbers.map((n) => <TabsTrigger key={n} value={String(n)}>{i18n.t("scoreboard_n", {value: n})}</TabsTrigger>)}
                    </TabsList>
                </Tabs> : locked ? <Badge variant="secondary">{i18n.t("scoreboard_n", {value: scoreboardNumber})}</Badge> : null}
                <Badge variant="outline" className={cn(status === "connected" ? "border-pick/50 text-pick" : "border-ban/50 text-ban")}>
                    {status === "connected" ? i18n.t("live") : i18n.t("connecting")}
                </Badge>
            </div>
        </header>
        {body}
    </div>;
}
