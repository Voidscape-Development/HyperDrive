import {ArrowLeftRight, RotateCcw, Trash2, Tv} from "lucide-react";
import {useSelector} from "react-redux";
import i18n from "../i18n/config";
import ScoreBar from "./ScoreBar";
import MatchInfo from "./MatchInfo";
import Team from "./Team";
import {api} from "./api";
import type {ReduxState} from "../redux/store";
import type {HDScoreInfo} from "../backendDataTypes";
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
    AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {Button} from "@/components/ui/button";

/** Buttons for the things done between and during sets. */
function QuickActions({scoreboardNumber}: {scoreboardNumber: number}) {
    const run = (call: (sb: number) => Promise<unknown>) => () => call(scoreboardNumber).catch(() => {});

    return (
        <div className="flex flex-wrap justify-center gap-2">
            <Button variant={"outline"} onClick={run(api.swapTeams)}>
                <ArrowLeftRight/>
                {i18n.t("swap_teams")}
            </Button>
            <Button variant={"outline"} onClick={run(api.resetScores)}>
                <RotateCcw/>
                {i18n.t("reset_score")}
            </Button>
            <Button variant={"outline"} onClick={run(api.pullStreamSet)}>
                <Tv/>
                {i18n.t("load_stream_set")}
            </Button>
            <AlertDialog>
                <AlertDialogTrigger asChild>
                    <Button variant={"outline"} className="border-destructive/50 text-destructive hover:text-destructive">
                        <Trash2/>
                        {i18n.t("clear_scoreboard")}
                    </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>{i18n.t("clear_scoreboard")}</AlertDialogTitle>
                        <AlertDialogDescription>{i18n.t("clear_scoreboard_confirm")}</AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>{i18n.t("cancel")}</AlertDialogCancel>
                        <AlertDialogAction
                            className="bg-destructive text-white hover:bg-destructive/90"
                            onClick={() => api.clearAll(scoreboardNumber).catch(() => {})}
                        >
                            {i18n.t("clear")}
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </div>
    );
}

/**
 * The scoreboard being controlled: the score (kept at the top while
 * scrolling), quick actions, the set's details and both teams.
 */
export default function CurrentSet({scoreboardNumber}: {scoreboardNumber: number}) {
    const score: HDScoreInfo = useSelector((state: ReduxState) => state.hdState.hdState?.score?.[scoreboardNumber]);

    const hasTeams = !!score?.team && Object.keys(score.team).length >= 2;
    if (!hasTeams) {
        return <p className="p-4 text-lg font-medium">{i18n.t("no_set")}</p>;
    }

    return (
        <div className="flex flex-col gap-4">
            <ScoreBar scoreboardNumber={scoreboardNumber} score={score}/>
            <QuickActions scoreboardNumber={scoreboardNumber}/>
            <MatchInfo scoreboardNumber={scoreboardNumber} score={score}/>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                {["1", "2"].map((teamKey) => (
                    <Team
                        key={`s-${scoreboardNumber}-t-${teamKey}`}
                        scoreboardNumber={scoreboardNumber}
                        hdTeamId={teamKey}
                        team={score.team[teamKey]}
                    />
                ))}
            </div>
        </div>
    );
}
