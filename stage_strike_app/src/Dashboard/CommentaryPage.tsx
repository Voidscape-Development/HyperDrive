import React from "react";
import {toast} from "sonner";
import CommentaryDashboardPage from "../CommentaryDashboardPage";
import Player from "../ScoreboardPage/Player";
import {dashboard} from "./api";
import {useHd} from "./stateTypes";
import {OptionsBar, PageBody, PageHeader, Stepper, useRemoteOptions} from "./ui";
import type {HDPlayerInfo} from "../backendDataTypes";
import {cn} from "@/lib/utils";

type View = "commentators" | "desk";

const emptyPlayer = {name: "", character: {}} as unknown as HDPlayerInfo;

function Commentators() {
    const commentary = useHd((s) => s.commentary);
    const {options, change} = useRemoteOptions(dashboard.commentary.options, dashboard.commentary.setOptions);
    const count = options?.commentators ?? Object.keys(commentary ?? {}).filter((k) => /^\d+$/.test(k)).length;

    return (
        <>
            {options && (
                <OptionsBar>
                    <Stepper label="Commentators" value={options.commentators} min={1} max={8} onChange={(v) => change({commentators: v})}/>
                    <Stepper label="Characters per commentator" value={options.characters} min={0} max={4} onChange={(v) => change({characters: v})}/>
                </OptionsBar>
            )}
            <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
                {Array.from({length: count}, (_, i) => i + 1).map((n) => (
                    <section key={n} aria-label={`Commentator ${n}`} className="flex flex-col gap-3 rounded-xl border bg-card p-4">
                        <span className="text-[11px] font-bold tracking-wider text-muted-foreground uppercase">Commentator {n}</span>
                        <Player
                            scoreboardNumber={0}
                            hdTeamId="0"
                            teamId={`commentary-${n}`}
                            teamKey={String(n)}
                            player={commentary?.[n] ?? emptyPlayer}
                            showHeading={false}
                            onSave={(data) => dashboard.commentary.setData(n, data).catch((e) => {
                                toast.error("Couldn't save the commentator.");
                                throw e;
                            })}
                        />
                    </section>
                ))}
            </div>
        </>
    );
}

/**
 * Commentary: the commentators shown on stream (the desktop app's
 * Commentary tab), and the desk view the commentators look at.
 */
export default function CommentaryPage() {
    const [view, setView] = React.useState<View>("commentators");

    const tab = (value: View, label: string) => (
        <button
            type="button"
            role="tab"
            aria-selected={view === value}
            onClick={() => setView(value)}
            className={cn(
                "min-h-8 cursor-pointer rounded-md px-3.5 text-[13px] outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50",
                view === value ? "bg-accent font-semibold text-foreground" : "text-muted-foreground hover:text-foreground",
            )}
        >
            {label}
        </button>
    );

    return (
        <>
            <PageBody className={view === "desk" ? "pb-0" : undefined}>
                <PageHeader title="Commentary" description={view === "desk" ? "What the commentators see: the players, their stats and what's up next." : undefined}>
                    <div role="tablist" aria-label="Commentary views" className="flex rounded-lg border bg-card p-0.5">
                        {tab("commentators", "Commentators")}
                        {tab("desk", "Desk view")}
                    </div>
                </PageHeader>
                {view === "commentators" && <Commentators/>}
            </PageBody>
            {view === "desk" && <CommentaryDashboardPage/>}
        </>
    );
}
