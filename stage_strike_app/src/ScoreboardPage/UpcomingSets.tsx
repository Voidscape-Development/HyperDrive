import React from "react";
import {ChevronDown, RefreshCw, Upload} from "lucide-react";
import i18n from "../i18n/config";
import {BACKEND_PORT, PROTOCOL} from "../env";
import {api} from "./api";
import type {HDSet} from "../backendDataTypes";
import {Field} from "@/components/Field";
import {Button} from "@/components/ui/button";
import {Card, CardAction, CardContent, CardHeader, CardTitle} from "@/components/ui/card";
import {Checkbox} from "@/components/ui/checkbox";
import {Collapsible, CollapsibleContent, CollapsibleTrigger} from "@/components/ui/collapsible";
import {Input} from "@/components/ui/input";
import {Label} from "@/components/ui/label";
import {Table, TableBody, TableCell, TableHead, TableHeader, TableRow} from "@/components/ui/table";
import {cn} from "@/lib/utils";

interface UpcomingSetsProps {
    scoreboardNumber: number;
    onSelectedSetChanged?: (setId: number) => void;
}

/** The tournament's sets, to load one into the scoreboard */
export default function UpcomingSets({scoreboardNumber, onSelectedSetChanged}: UpcomingSetsProps) {
    const [isLoading, setIsLoading] = React.useState(true);
    const [setFilter, setSetFilter] = React.useState("");
    const [selectedSet, setSelectedSet] = React.useState<HDSet | null>(null);
    const [showFinished, setShowFinished] = React.useState(false);
    const [expanded, setExpanded] = React.useState(true);
    const [sets, setSets] = React.useState<HDSet[]>([]);

    const fetchSets = React.useCallback(() => {
        setIsLoading(true);
        fetch(PROTOCOL + "//" + window.location.hostname + `:${BACKEND_PORT}/get-sets?_foo=${showFinished ? "&getFinished=true" : ""}&`)
            .then((res) => res.json())
            .then((data: HDSet[]) => setSets(data))
            .catch(console.log)
            .finally(() => setIsLoading(false));
    }, [showFinished]);

    React.useEffect(() => {
        fetchSets();
    }, [fetchSets]);

    const submitNewSet = () => {
        setIsLoading(true);
        // Into the scoreboard being shown, not always scoreboard 1
        api.loadSet(scoreboardNumber ?? 1, selectedSet?.id)
            .then(() => onSelectedSetChanged?.(selectedSet.id))
            .catch(() => {})
            .finally(() => setIsLoading(false));
    };

    const filteredSets = React.useMemo(() => {
        const fs = setFilter.toLocaleLowerCase();
        if (!fs) {
            return sets;
        }
        return sets.filter((set) => (
            set.p1_name.toLocaleLowerCase().includes(fs)
            || set.p2_name.toLocaleLowerCase().includes(fs)
            || set.round_name.toLocaleLowerCase().includes(fs)
            || set.stream?.toLocaleLowerCase().includes(fs)
        ));
    }, [sets, setFilter]);

    return (
        <Collapsible open={expanded} onOpenChange={setExpanded} asChild>
            <Card>
                <CardHeader>
                    <CardTitle className="text-lg">{i18n.t("upcoming_sets")}</CardTitle>
                    <CardAction>
                        <CollapsibleTrigger asChild>
                            <Button variant="ghost" size="icon" aria-label={i18n.t("upcoming_sets")}>
                                <ChevronDown className={cn("transition-transform", !expanded && "-rotate-90")}/>
                            </Button>
                        </CollapsibleTrigger>
                    </CardAction>
                </CardHeader>
                <CollapsibleContent>
                    <CardContent className="flex flex-col gap-4">
                        <div className="flex flex-wrap gap-2">
                            <Button variant={"outline"} onClick={fetchSets} disabled={isLoading}>
                                <RefreshCw className={cn(isLoading && "animate-spin")}/>
                                {i18n.t("refresh_sets")}
                            </Button>
                            <Button onClick={submitNewSet} disabled={!selectedSet || isLoading}>
                                <Upload/>
                                {i18n.t("load_selected_set")}
                            </Button>
                        </div>

                        <div className="flex items-center gap-2">
                            <Checkbox
                                id={"show-finished-sets"}
                                checked={showFinished}
                                onCheckedChange={(checked) => setShowFinished(checked === true)}
                            />
                            <Label htmlFor={"show-finished-sets"}>{i18n.t("show_finished_sets")}</Label>
                        </div>
                        <Field label={i18n.t("filter")} htmlFor={"upcoming-sets-filter"}>
                            <Input
                                id={"upcoming-sets-filter"}
                                value={setFilter}
                                onChange={(e) => setSetFilter(e.target.value)}
                            />
                        </Field>

                        <div className="rounded-md border">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>{i18n.t("p1")}</TableHead>
                                        <TableHead>{i18n.t("p2")}</TableHead>
                                        <TableHead>{i18n.t("phase")}</TableHead>
                                        <TableHead>{i18n.t("match")}</TableHead>
                                        <TableHead>{i18n.t("stream")}</TableHead>
                                        <TableHead>{i18n.t("station")}</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {filteredSets.map((set) => (
                                        <TableRow
                                            key={set.id}
                                            className="cursor-pointer"
                                            data-state={selectedSet?.id === set.id ? "selected" : undefined}
                                            onClick={() => setSelectedSet(set)}
                                        >
                                            {/*
                                              * It's unclear if the backend will translate things like
                                              * "Losers Round 5" for us. Stuff exists to support it in the
                                              * python side of things, but using it browser-side is definitely
                                              * a yak that needs shaving.
                                              */}
                                            <TableCell>{set.p1_name}</TableCell>
                                            <TableCell>{set.p2_name}</TableCell>
                                            <TableCell>{set.tournament_phase}</TableCell>
                                            <TableCell>{set.round_name}</TableCell>
                                            <TableCell>{set.stream}</TableCell>
                                            <TableCell>{set.station}</TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </div>
                    </CardContent>
                </CollapsibleContent>
            </Card>
        </Collapsible>
    );
}
