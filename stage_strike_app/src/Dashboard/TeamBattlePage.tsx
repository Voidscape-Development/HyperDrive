import React from "react";
import {Pencil, Undo2} from "lucide-react";
import {toast} from "sonner";
import Player from "../ScoreboardPage/Player";
import {saveOnCommit, useAutoSaveForm} from "../ScoreboardPage/useAutoSaveForm";
import {dashboard, type TeamBattleOptions} from "./api";
import {useHd, type TeamBattleState} from "./stateTypes";
import {OptionsBar, PageBody, PageHeader, Stepper, useRemoteOptions} from "./ui";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {Switch} from "@/components/ui/switch";
import {cn} from "@/lib/utils";

type Team = NonNullable<TeamBattleState["team"]>[string];

const failed = (what: string) => () => toast.error(`Couldn't ${what}.`);

function TeamCard({number, team, mode, total}: {number: 1 | 2; team?: Team; mode: TeamBattleOptions["mode"]; total: number}) {
    const [editing, setEditing] = React.useState(false);
    const {values, setField, flush} = useAutoSaveForm(
        {name: team?.sponsor ?? ""},
        (v) => dashboard.teamBattle.setTeam(number, {name: v.name}),
        900,
    );
    const players = Object.keys(team?.player ?? {}).sort((a, b) => Number(a) - Number(b));
    const stockPool = mode === "STOCK_POOL";

    return (
        <section aria-label={values.name || `Team ${number}`} className="flex min-w-0 flex-col overflow-hidden rounded-xl border bg-card">
            <div className="flex items-center gap-3 border-b px-4 py-3" style={{boxShadow: `inset 0 3px 0 ${team?.color || "var(--muted-foreground)"}`}}>
                <Input
                    aria-label={`Team ${number} name`}
                    placeholder={`Team ${number}`}
                    value={values.name}
                    onChange={(e) => setField("name", e.target.value)}
                    {...saveOnCommit(flush)}
                    className="font-bold"
                />
                <span className="flex flex-col items-end leading-tight">
                    <span className="text-2xl font-black tabular-nums">{total}</span>
                    <span className="text-[11px] text-muted-foreground">{stockPool ? "stocks left" : "players left"}</span>
                </span>
            </div>

            <div className="flex flex-wrap items-center gap-2 border-b px-4 py-2.5">
                <Button onClick={() => dashboard.teamBattle.scoreUp(number).catch(failed("score"))}>
                    {stockPool ? "Took a stock" : "Won a game"}
                </Button>
                <Button variant="ghost" aria-label="Undo the last point" title="Undo the last point" onClick={() => dashboard.teamBattle.scoreDown(number).catch(failed("undo"))}>
                    <Undo2/>Undo
                </Button>
                <div className="flex-1"/>
                <Button variant="ghost" size="sm" aria-pressed={editing} onClick={() => setEditing(!editing)}>
                    <Pencil/>{editing ? "Done" : "Edit players"}
                </Button>
            </div>

            {players.map((key) => {
                const p = team!.player![key];
                const out = !!p.dead;
                const status = p.active ? "Active" : out ? "Eliminated" : "Waiting";
                return (
                    <div key={key} className={cn("flex flex-col border-b last:border-0", p.active && "bg-accent", out && !p.active && "opacity-60")}>
                        <div className="flex min-h-14 items-center gap-3 px-4">
                            <span className="w-5 text-xs font-bold text-muted-foreground">{key}</span>
                            <span className="flex min-w-0 flex-1 flex-col leading-snug">
                                <span className="truncate font-semibold">{p.mergedName || p.name || `Player ${key}`}</span>
                                <span className="truncate text-xs text-muted-foreground">
                                    {Object.values(p.character ?? {}).map((c) => c?.display_name ?? c?.name).filter(Boolean).join(", ")}
                                </span>
                            </span>
                            <span className={cn(
                                "rounded-full px-2 py-0.5 text-[11px] font-bold",
                                p.active ? "bg-brand text-primary-foreground" : out ? "bg-destructive/20 text-destructive" : "border text-muted-foreground",
                            )}>{status}</span>
                            <span className="w-14 text-right text-sm tabular-nums" title={stockPool ? "Stocks left" : "Games won"}>
                                <b>{String(p.dynamicSpinner ?? 0)}</b> <span className="text-xs text-muted-foreground">{stockPool ? "stk" : "W"}</span>
                            </span>
                            {!p.active && !out && (
                                <Button variant="outline" size="sm" onClick={() => dashboard.teamBattle.setActive(number, Number(key)).catch(failed("change the active player"))}>
                                    Make active
                                </Button>
                            )}
                        </div>
                        {editing && (
                            <div className="px-4 pb-4">
                                <Player
                                    scoreboardNumber={0}
                                    hdTeamId="0"
                                    teamId={`team-battle-${number}`}
                                    teamKey={key}
                                    player={p}
                                    showHeading={false}
                                    onSave={(data) => dashboard.teamBattle.setPlayer(number, Number(key), data)}
                                />
                            </div>
                        )}
                    </div>
                );
            })}
        </section>
    );
}

/** Crew/Team Battle: two teams, one matchup at a time, until a team runs out */
export default function TeamBattlePage() {
    const battle = useHd((s) => s.team_battle);
    const {options, change, reload} = useRemoteOptions<TeamBattleOptions>(dashboard.teamBattle.options, dashboard.teamBattle.setOptions);
    const mode = options?.mode ?? "STOCK_POOL";

    const total = (n: 1 | 2) => {
        const players = Object.values(battle?.team?.[n]?.player ?? {});
        return mode === "STOCK_POOL"
            ? players.reduce((sum, p) => sum + (Number(p.dynamicSpinner) || 0), 0)
            : players.filter((p) => !p.dead).length;
    };

    return (
        <PageBody>
            <PageHeader title="Crew/Team Battle" description={[battle?.phase, battle?.match].filter(Boolean).join(" · ") || "Two teams, one matchup at a time, until a team runs out"}>
                <Button variant="outline" onClick={() => window.confirm("Reset every player's stocks or wins?") && dashboard.teamBattle.resetStocks().catch(failed("reset"))}>
                    Reset player values
                </Button>
                <Button variant="outline" className="border-destructive/50 text-destructive hover:text-destructive"
                    onClick={() => window.confirm("Reset the whole battle?") && dashboard.teamBattle.reset().catch(failed("reset"))}>
                    Reset battle
                </Button>
            </PageHeader>

            {options && (
                <OptionsBar>
                    <span className="flex items-center gap-2">
                        Mode
                        <span role="radiogroup" aria-label="Mode" className="flex rounded-lg bg-muted p-[3px]">
                            {([["STOCK_POOL", "Stock Pool"], ["FIRST_TO", "First To"]] as const).map(([value, label]) => (
                                <button key={value} type="button" role="radio" aria-checked={mode === value} onClick={() => change({mode: value})}
                                    className={cn("h-8 cursor-pointer rounded-md px-3 text-[13px]", mode === value ? "bg-primary font-semibold text-primary-foreground" : "hover:text-foreground")}>
                                    {label}
                                </button>
                            ))}
                        </span>
                    </span>
                    {/* Plays change with these in the app, so they're loaded again */}
                    <label className="flex items-center gap-2">
                        <Switch checked={options.limited} onCheckedChange={(on) => change({limited: on}).then(reload)}/>Limited plays
                    </label>
                    <Stepper label="Players per team" value={options.players} min={1} max={16} onChange={(v) => change({players: v}).then(reload)}/>
                    {options.limited && (
                        <Stepper label="Plays" value={options.plays} min={1} max={options.players} onChange={(v) => change({plays: v})}/>
                    )}
                    <Stepper label={mode === "STOCK_POOL" ? "Starting stocks" : "Games to win"} value={options.battleValue} min={1} max={99} onChange={(v) => change({battleValue: v})}/>
                    <Stepper label="Characters" value={options.characters} min={0} max={4} onChange={(v) => change({characters: v})}/>
                    <label className="flex items-center gap-2">
                        <Switch checked={options.autoAdvance} onCheckedChange={(on) => change({autoAdvance: on})}/>Auto advance
                    </label>
                </OptionsBar>
            )}

            <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-2">
                <TeamCard number={1} team={battle?.team?.[1]} mode={mode} total={total(1)}/>
                <TeamCard number={2} team={battle?.team?.[2]} mode={mode} total={total(2)}/>
            </div>
        </PageBody>
    );
}
