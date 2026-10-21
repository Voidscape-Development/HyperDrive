import React from "react";
import {ChevronDown, ChevronRight, Copy} from "lucide-react";
import {toast} from "sonner";
import Player from "../ScoreboardPage/Player";
import {saveOnCommit, useAutoSaveForm} from "../ScoreboardPage/useAutoSaveForm";
import {dashboard, type PlayerListOptions, type ResultsText} from "./api";
import {useStatus} from "./status";
import {useHd, type PlayerListSlot} from "./stateTypes";
import {OptionsBar, PageBody, PageHeader, Panel, Stepper, useRemoteOptions} from "./ui";
import {Button} from "@/components/ui/button";
import {Checkbox} from "@/components/ui/checkbox";
import {Input} from "@/components/ui/input";
import {Switch} from "@/components/ui/switch";
import {cn} from "@/lib/utils";

const ordinal = (n: number) => {
    const s = ["th", "st", "nd", "rd"];
    const v = n % 100;
    return n + (s[(v - 20) % 10] || s[v] || s[0]);
};

function Slot({number, slot, showScores, open, onToggle}: {
    number: number;
    slot: PlayerListSlot;
    showScores: boolean;
    open: boolean;
    onToggle: () => void;
}) {
    const {values, setField, flush} = useAutoSaveForm(
        {name: slot?.name ?? "", score: String(slot?.score ?? 0)},
        (v, changed) => dashboard.playerList.setSlot(number, Object.fromEntries(changed.map((k) => [k, k === "score" ? Number(v.score) || 0 : v[k]]))),
        900,
    );
    const players = Object.keys(slot?.player ?? {}).sort((a, b) => Number(a) - Number(b));
    const tags = players.map((k) => slot.player[k]?.name).filter(Boolean).join(" / ");

    return (
        <div className={cn("border-b last:border-0", open && "bg-background/40")}>
            <div className="flex min-h-12 items-center gap-2.5 px-3">
                <Button variant="ghost" size="icon-sm" aria-expanded={open} aria-label={`${open ? "Collapse" : "Expand"} ${ordinal(number)} place`} onClick={onToggle}>
                    {open ? <ChevronDown/> : <ChevronRight/>}
                </Button>
                <span className="w-10 font-bold text-brand-text">{ordinal(number)}</span>
                <Input
                    aria-label={`${ordinal(number)} place: team name`}
                    placeholder={tags || "Team name"}
                    value={values.name}
                    onChange={(e) => setField("name", e.target.value)}
                    {...saveOnCommit(flush)}
                    className="h-8"
                />
                {showScores && (
                    <Input
                        aria-label={`${ordinal(number)} place: score`}
                        type="number"
                        inputMode="numeric"
                        value={values.score}
                        onChange={(e) => setField("score", e.target.value)}
                        {...saveOnCommit(flush)}
                        className="h-8 w-20"
                    />
                )}
            </div>
            {open && (
                <div className="grid grid-cols-1 gap-5 px-4 pt-1 pb-5 md:grid-cols-2">
                    {players.map((key) => (
                        <Player
                            key={key}
                            scoreboardNumber={0}
                            hdTeamId="0"
                            teamId={`player-list-${number}`}
                            teamKey={key}
                            player={slot.player[key]}
                            showHeading={players.length > 1}
                            onSave={(data) => dashboard.playerList.setPlayer(number, Number(key), data)}
                        />
                    ))}
                </div>
            )}
        </div>
    );
}

const SIMPLE_OPTIONS: [string, string][] = [
    ["show_date", "Date"],
    ["show_game", "Game"],
    ["show_bracket_link", "Bracket link"],
    ["show_seed", "Seed"],
    ["show_country", "Country"],
    ["show_characters", "Characters"],
    ["show_variants", "Character variants"],
    ["show_twitter", "Twitter"],
    ["show_pronoun", "Pronouns"],
    ["show_commentators", "Commentators"],
];

const TEMPLATE_PARTS: [string, string][] = [
    ["template_header", "Header"],
    ["template_entry", "Each placement"],
    ["template_player", "Each player"],
    ["template_footer", "Footer"],
];

/** The results written out, e.g. to post on social media */
function ResultsTextPanel() {
    const slots = useHd((s) => s.player_list?.slot);
    const [mode, setMode] = React.useState<"simple" | "template">("simple");
    const [results, setResults] = React.useState<ResultsText | null>(null);

    const load = React.useCallback(() => {
        dashboard.playerList.results(mode).then(setResults).catch(() => {});
    }, [mode]);

    // Again when the list changes
    React.useEffect(() => {
        const timer = setTimeout(load, 300);
        return () => clearTimeout(timer);
    }, [load, slots]);

    const setOption = (key: string, value: string | boolean) => {
        setResults((r) => (r ? {...r, options: {...r.options, [key]: value}} : r));
        dashboard.playerList.setResultsOptions({options: {[key]: value, mode}}).then(load).catch(() => {});
    };

    const textArea = (key: string, label: string, rows = 2) => (
        <label key={key} className="flex flex-col gap-1.5 text-xs text-muted-foreground">
            {label}
            <textarea
                rows={rows}
                defaultValue={String(results?.options[key] ?? "")}
                onBlur={(e) => e.target.value !== String(results?.options[key] ?? "") && setOption(key, e.target.value)}
                className="rounded-md border bg-background px-3 py-2 font-mono text-xs text-foreground outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
            />
        </label>
    );

    return (
        <Panel title="Results text">
            <div className="flex flex-col gap-3">
                <div role="tablist" aria-label="Results text" className="flex w-fit rounded-lg border p-0.5">
                    {(["simple", "template"] as const).map((m) => (
                        <button key={m} type="button" role="tab" aria-selected={mode === m} onClick={() => setMode(m)}
                            className={cn("min-h-8 cursor-pointer rounded-md px-3 text-[13px]", mode === m ? "bg-accent font-semibold" : "text-muted-foreground")}>
                            {m === "simple" ? "Simple" : "Template"}
                        </button>
                    ))}
                </div>
                {results && mode === "simple" && (
                    <div key="simple" className="flex flex-col gap-3">
                        <div className="grid grid-cols-2 gap-2">
                            {SIMPLE_OPTIONS.map(([key, label]) => (
                                <label key={key} className="flex items-center gap-2 text-[13px]">
                                    <Checkbox checked={!!results.options[key]} onCheckedChange={(on) => setOption(key, on === true)}/>{label}
                                </label>
                            ))}
                        </div>
                        {textArea("header_text", "Text at the top")}
                        {textArea("footer_text", "Text at the bottom")}
                    </div>
                )}
                {results && mode === "template" && (
                    <div key="template" className="flex flex-col gap-3">
                        <p className="text-xs text-muted-foreground">
                            {"{name}"} is replaced by the value. A part in [[ ]] is only shown when every value in it is filled in, e.g. [[ ({"{twitter}"})]].
                        </p>
                        {TEMPLATE_PARTS.map(([key, label]) => textArea(key, label, key.includes("entry") || key.includes("player") ? 2 : 4))}
                        <Button variant="outline" className="w-fit" onClick={() => dashboard.playerList.setResultsOptions({resetTemplates: true}).then(() => {
                            setResults(null);
                            load();
                        })}>
                            Reset templates
                        </Button>
                    </div>
                )}
                <pre className="max-h-96 overflow-auto rounded-lg border bg-background p-3 font-mono text-xs leading-relaxed whitespace-pre-wrap">
                    {results?.text ?? "…"}
                </pre>
                <Button
                    disabled={!results?.text}
                    onClick={() => navigator.clipboard.writeText(results?.text ?? "").then(() => toast.success("Copied")).catch(() => toast.error("Couldn't copy. Select the text instead."))}
                >
                    <Copy/>Copy text
                </Button>
            </div>
        </Panel>
    );
}

/**
 * The Player List: the players for the top 8 and top N layouts, from the
 * event's standings or filled in by hand.
 */
export default function PlayerListPage() {
    const slots = useHd((s) => s.player_list?.slot);
    const loaded = useStatus()?.tournament.loaded;
    const {options, change} = useRemoteOptions<PlayerListOptions>(dashboard.playerList.options, dashboard.playerList.setOptions);
    const [open, setOpen] = React.useState<Set<number>>(() => new Set([1]));

    const numbers = Object.keys(slots ?? {}).map(Number).filter((n) => n > 0).sort((a, b) => a - b);
    const toggle = (n: number) => setOpen((was) => {
        const next = new Set(was);
        if (next.has(n)) {
            next.delete(n);
        } else {
            next.add(n);
        }
        return next;
    });

    return (
        <PageBody>
            <PageHeader title="Player List" description="For the top_8, top_8_single_elim and top_n_list layouts">
                <Button disabled={!loaded} onClick={() => dashboard.playerList.loadStandings().then(() => toast.success("Loading the standings")).catch(() => toast.error("Couldn't load the standings."))}>
                    Load tournament standings
                </Button>
            </PageHeader>

            {options && (
                <OptionsBar>
                    <Stepper label="Slots" value={options.slots} min={1} max={64} onChange={(v) => change({slots: v})}/>
                    <Stepper label="Players per slot" value={options.playersPerSlot} min={1} max={8} onChange={(v) => change({playersPerSlot: v})}/>
                    <Stepper label="Characters per player" value={options.charactersPerPlayer} min={0} max={8} onChange={(v) => change({charactersPerPlayer: v})}/>
                    <label className="flex items-center gap-2">
                        <Switch checked={options.showScores} onCheckedChange={(on) => change({showScores: on})}/>Show scores
                    </label>
                </OptionsBar>
            )}

            <div className="grid grid-cols-1 items-start gap-4 xl:grid-cols-[3fr_2fr]">
                <Panel
                    title="Slots"
                    bodyClassName="p-0"
                    action={
                        <div className="flex gap-1.5">
                            <Button variant="outline" size="sm" onClick={() => setOpen(new Set())}>Collapse all</Button>
                            <Button variant="outline" size="sm" onClick={() => setOpen(new Set(numbers))}>Expand all</Button>
                        </div>
                    }
                >
                    {numbers.map((n) => (
                        <Slot key={n} number={n} slot={slots![n]} showScores={!!options?.showScores} open={open.has(n)} onToggle={() => toggle(n)}/>
                    ))}
                </Panel>
                <ResultsTextPanel/>
            </div>
        </PageBody>
    );
}
