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
    return <Badge variant={"outline"} className={cn("sm:ml-auto", chip.className)}>
        {chip.icon}
        {chip.label}
    </Badge>;
};

export const Header = ({onSelectedGameChange}: {onSelectedGameChange: (codename: string) => void}) => {
    const {hdState, games} = useSelector((state: ReduxState) => ({
        hdState: state.hdState.hdState,
        games: state.hdGames.value,
    }), shallowEqual);
    const current = games[hdState.game?.codename];

    return (
        <header className="flex flex-col items-center gap-2 border-b bg-card px-4 py-3 sm:flex-row sm:gap-6 sm:px-8">
            <div className="flex items-center gap-3">
                <img alt="HyperDrive logo" src={`${BASE_URL}/assets/icons/icon.png`} className="size-10"/>
                <h1 className="text-lg font-semibold tracking-tight whitespace-nowrap">Web Scoreboard</h1>
            </div>

            <div className="flex items-center gap-2 text-sm">
                <span className="text-muted-foreground">Game</span>
                <Select value={current ? current.codename : undefined} onValueChange={onSelectedGameChange}>
                    <SelectTrigger className="h-11 min-w-32 data-[size=default]:h-11" id={"header-game-select"}>
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
            </div>

            <div className="max-w-full truncate text-sm">
                <span className="text-muted-foreground">Event </span>
                <span>{hdState.tournamentInfo?.tournamentName}: </span>
                <span>{hdState.tournamentInfo?.eventName}</span>
            </div>

            <SaveStatus/>
        </header>
    );
};
