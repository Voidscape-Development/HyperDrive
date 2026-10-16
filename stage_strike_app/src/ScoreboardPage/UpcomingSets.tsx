import React from "react";
import {Check, RefreshCw, Search, Tv} from "lucide-react";
import {toast} from "sonner";
import i18n from "../i18n/config";
import {BACKEND_PORT, PROTOCOL} from "../env";
import {api} from "./api";
import type {HDSet} from "../backendDataTypes";
import {Badge} from "@/components/ui/badge";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {Spinner} from "@/components/ui/spinner";
import {cn} from "@/lib/utils";

interface UpcomingSetsProps {
    scoreboardNumber: number;
    // The set the scoreboard has, marked in the list
    currentSetId?: number;
    onSetLoaded?: (setId: number) => void;
    searchRef?: React.Ref<HTMLInputElement>;
}

type Which = "stream" | "all";

const Chip = ({pressed, onClick, children}: {pressed: boolean; onClick: () => void; children: React.ReactNode}) => (
    <button
        type="button"
        aria-pressed={pressed}
        onClick={onClick}
        className={cn(
            "h-9 cursor-pointer rounded-full border px-3.5 text-[13px] font-semibold outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50",
            pressed ? "border-primary bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground",
        )}
    >
        {children}
    </button>
);

const setName = (set: HDSet) => `${set.p1_name || i18n.t("tbd")} ${i18n.t("vs")} ${set.p2_name || i18n.t("tbd")}`;

/** The tournament's sets, each loaded into the scoreboard with one tap */
export default function UpcomingSets({scoreboardNumber, currentSetId, onSetLoaded, searchRef}: UpcomingSetsProps) {
    const [isLoading, setIsLoading] = React.useState(true);
    const [setFilter, setSetFilter] = React.useState("");
    const [showFinished, setShowFinished] = React.useState(false);
    // null until picked: the stream sets when there are some, else all of them
    const [which, setWhich] = React.useState<Which | null>(null);
    const [loadingId, setLoadingId] = React.useState<number | null>(null);
    const [sets, setSets] = React.useState<HDSet[]>([]);

    const fetchSets = React.useCallback(() => {
        setIsLoading(true);
        fetch(PROTOCOL + "//" + window.location.hostname + `:${BACKEND_PORT}/get-sets?_foo=${showFinished ? "&getFinished=true" : ""}&`)
            .then((res) => res.json())
            .then((data: HDSet[]) => setSets(Array.isArray(data) ? data : []))
            .catch(console.log)
            .finally(() => setIsLoading(false));
    }, [showFinished]);

    React.useEffect(() => {
        fetchSets();
    }, [fetchSets]);

    const hasStreamSets = sets.some((s) => s.stream);
    const shown: Which = which ?? (hasStreamSets ? "stream" : "all");

    const filteredSets = React.useMemo(() => {
        const fs = setFilter.trim().toLocaleLowerCase();
        return sets.filter((set) => (
            (shown === "all" || set.stream)
            && (!fs
                || set.p1_name?.toLocaleLowerCase().includes(fs)
                || set.p2_name?.toLocaleLowerCase().includes(fs)
                || set.round_name?.toLocaleLowerCase().includes(fs)
                || set.tournament_phase?.toLocaleLowerCase().includes(fs)
                || set.stream?.toLocaleLowerCase().includes(fs)
                || set.station?.toLocaleLowerCase().includes(fs))
        ));
    }, [sets, setFilter, shown]);

    const load = (set: HDSet) => {
        setLoadingId(set.id);
        // Into the scoreboard being shown, not always scoreboard 1
        api.loadSet(scoreboardNumber ?? 1, set.id)
            .then(() => {
                toast.success(i18n.t("set_loaded", {set: setName(set), value: scoreboardNumber}));
                onSetLoaded?.(set.id);
            })
            .catch(() => toast.error(i18n.t("set_load_failed")))
            .finally(() => setLoadingId(null));
    };

    return (
        <section aria-labelledby="up-next-title" className="flex flex-col gap-3">
            <div className="flex items-center gap-2">
                <h2 id="up-next-title" className="flex-1 text-2xl font-bold tracking-tight">{i18n.t("up_next")}</h2>
                <Button
                    variant="outline"
                    size="icon"
                    className="size-11 rounded-xl"
                    aria-label={i18n.t("refresh_sets")}
                    onClick={fetchSets}
                    disabled={isLoading}
                >
                    <RefreshCw className={cn(isLoading && "animate-spin")}/>
                </Button>
            </div>

            <div className="relative">
                <Search aria-hidden className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"/>
                <Input
                    ref={searchRef}
                    type="search"
                    aria-label={i18n.t("filter")}
                    placeholder={i18n.t("search_sets")}
                    value={setFilter}
                    onChange={(e) => setSetFilter(e.target.value)}
                    className="h-11 pl-9 text-base md:text-sm"
                />
            </div>

            <div className="flex flex-wrap gap-2">
                <Chip pressed={shown === "stream"} onClick={() => setWhich("stream")}>{i18n.t("on_stream")}</Chip>
                <Chip pressed={shown === "all"} onClick={() => setWhich("all")}>{i18n.t("all_sets")}</Chip>
                <Chip pressed={showFinished} onClick={() => setShowFinished(!showFinished)}>{i18n.t("show_finished_sets")}</Chip>
            </div>

            {filteredSets.length === 0
                ? (
                    <p className="flex items-center gap-2 rounded-xl border border-dashed px-4 py-6 text-sm text-muted-foreground">
                        {isLoading
                            ? <><Spinner/>{i18n.t("loading")}</>
                            : (shown === "stream" && !setFilter ? i18n.t("no_stream_sets") : i18n.t("no_sets"))}
                    </p>
                )
                : (
                    <ul className="flex flex-col divide-y overflow-hidden rounded-xl border bg-card">
                        {filteredSets.map((set) => {
                            const current = set.id === currentSetId;
                            const meta = [set.tournament_phase, set.round_name, set.station && i18n.t("station_n", {value: set.station})]
                                .filter(Boolean)
                                .join(" · ");
                            return (
                                <li key={set.id} className={cn("flex items-center gap-3 py-2.5 pr-2.5 pl-3.5", current && "bg-muted/40")}>
                                    <div className="min-w-0 flex-1">
                                        <div className="truncate font-semibold">
                                            {set.p1_name || i18n.t("tbd")}
                                            <span className="px-1.5 text-sm font-normal text-muted-foreground">{i18n.t("vs")}</span>
                                            {set.p2_name || i18n.t("tbd")}
                                        </div>
                                        <div className="flex min-w-0 items-center gap-2 pt-0.5">
                                            {set.stream && (
                                                <Badge variant="outline" className="shrink-0 gap-1">
                                                    <Tv/>{set.stream}
                                                </Badge>
                                            )}
                                            <span className="truncate text-xs text-muted-foreground">{meta}</span>
                                        </div>
                                    </div>
                                    {current
                                        ? (
                                            <span className="flex h-11 items-center gap-1.5 px-2 text-sm text-pick">
                                                <Check className="size-4"/>{i18n.t("loaded")}
                                            </span>
                                        )
                                        : (
                                            <Button
                                                variant="outline"
                                                className="h-11 rounded-xl px-4"
                                                aria-label={i18n.t("load_set_named", {set: setName(set)})}
                                                disabled={loadingId !== null}
                                                onClick={() => load(set)}
                                            >
                                                {loadingId === set.id ? <Spinner/> : i18n.t("load")}
                                            </Button>
                                        )}
                                </li>
                            );
                        })}
                    </ul>
                )}
        </section>
    );
}
