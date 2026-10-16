import {CircleAlert, CircleCheck, RefreshCw} from "lucide-react";
import {shallowEqual, useSelector} from "react-redux";
import i18n from "../i18n/config";
import {useSaveStatus} from "./saveStatus";
import {BASE_URL} from "../env";
import {GameIcon} from "../GameIcon";
import type {ReduxState} from "../redux/store";
import type {HDGameInfo} from "../backendDataTypes";
import {Badge} from "@/components/ui/badge";
import {Select, SelectContent, SelectItem, SelectTrigger, SelectValue} from "@/components/ui/select";
import {cn} from "@/lib/utils";

/** Whether the changes made on this page have reached HyperDrive. */
const SaveStatus = () => {
    const status = useSaveStatus();
    if (status === "idle") {
        return null;
    }
    const chip = {
        saving: {icon: <RefreshCw className="animate-spin"/>, label: i18n.t("saving"), className: "text-muted-foreground"},
        saved: {icon: <CircleCheck/>, label: i18n.t("saved"), className: "border-pick/50 text-pick"},
        error: {icon: <CircleAlert/>, label: i18n.t("save_failed"), className: "border-destructive/50 text-destructive"},
    }[status];
    return <Badge variant={"outline"} className={cn("lg:order-last", chip.className)}>
        {chip.icon}
        {chip.label}
    </Badge>;
};

interface HeaderProps {
    onSelectedGameChange: (codename: string) => void;
    scoreboards: number[];
    selectedScoreboard: number;
    onSelectedScoreboardChange: (scoreboard: number) => void;
}

export const Header = ({onSelectedGameChange, scoreboards, selectedScoreboard, onSelectedScoreboardChange}: HeaderProps) => {
    const {hdState, games} = useSelector((state: ReduxState) => ({
        hdState: state.hdState.hdState,
        games: state.hdGames.value,
    }), shallowEqual);
    const current = games[hdState.game?.codename];
    const event = [hdState.tournamentInfo?.tournamentName, hdState.tournamentInfo?.eventName].filter(Boolean).join(" · ");

    return (
        <header className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b bg-card px-4 py-2.5 lg:px-6">
            <div className="flex min-w-0 flex-1 items-center gap-3 lg:flex-none">
                <img alt="HyperDrive logo" src={`${BASE_URL}/assets/icons/icon.png`} className="size-9"/>
                <div className="min-w-0">
                    <h1 className="truncate text-sm font-semibold tracking-tight lg:text-base">Web Scoreboard</h1>
                    {event && <div className="truncate text-xs text-muted-foreground lg:hidden">{event}</div>}
                </div>
            </div>

            <SaveStatus/>

            <div className="flex w-full items-center gap-2 lg:w-auto lg:flex-1">
                <Select value={current ? current.codename : undefined} onValueChange={onSelectedGameChange}>
                    <SelectTrigger
                        aria-label="Game"
                        className="h-10 min-w-32 data-[size=default]:h-10"
                        id={"header-game-select"}
                    >
                        <SelectValue>{current && <GameIcon game={current}/>}</SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                        {Object.values(games).map((game: HDGameInfo) =>
                            <SelectItem key={game.codename} value={game.codename}>
                                <GameIcon game={game} className="h-6 w-12 object-contain"/>
                                {game.name}
                            </SelectItem>
                        )}
                    </SelectContent>
                </Select>

                {event && <span className="hidden min-w-0 truncate text-sm text-muted-foreground lg:block">{event}</span>}

                {scoreboards.length > 1 && (
                    <Select value={String(selectedScoreboard)} onValueChange={(v) => onSelectedScoreboardChange(Number(v))}>
                        <SelectTrigger
                            aria-label={i18n.t("scoreboard")}
                            className="ml-auto h-10 font-semibold data-[size=default]:h-10"
                        >
                            <SelectValue/>
                        </SelectTrigger>
                        <SelectContent align="end">
                            {scoreboards.map((sb) =>
                                <SelectItem key={sb} value={String(sb)}>{i18n.t("scoreboard_n", {value: sb})}</SelectItem>
                            )}
                        </SelectContent>
                    </Select>
                )}
            </div>
        </header>
    );
};
