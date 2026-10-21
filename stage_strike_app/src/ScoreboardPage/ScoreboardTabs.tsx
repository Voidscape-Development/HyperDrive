import React from "react";
import {Minus, Pencil, Plus} from "lucide-react";
import {toast} from "sonner";
import i18n from "../i18n/config";
import {dashboard} from "../Dashboard/api";
import {refreshStatus} from "../Dashboard/status";
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
import {Input} from "@/components/ui/input";
import {cn} from "@/lib/utils";

// HyperDrive runs up to this many scoreboards (MAX_SCOREBOARDS)
const MAX_SCOREBOARDS = 10;

interface ScoreboardTabsProps {
    scoreboards: {number: number; name: string}[];
    selected: number;
    onSelect: (number: number) => void;
}

/** A tab's name, typed in place of the tab */
function RenameInput({number, name, onDone}: {number: number; name: string; onDone: () => void}) {
    const [value, setValue] = React.useState(name);
    const save = () => {
        onDone();
        if (value.trim() !== name) {
            dashboard.scoreboards.rename(number, value.trim()).then(refreshStatus).catch(() => toast.error(i18n.t("save_failed")));
        }
    };
    return (
        <Input
            autoFocus
            aria-label={i18n.t("scoreboard_n", {value: number})}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onBlur={save}
            onKeyDown={(e) => {
                if (e.key === "Enter") {
                    save();
                } else if (e.key === "Escape") {
                    onDone();
                }
            }}
            className="h-8 w-40"
        />
    );
}

/**
 * The scoreboards, one tab each, as in the desktop app's Scoreboard Manager:
 * double-click (or the pencil) renames one, + adds one, − removes the last.
 */
export function ScoreboardTabs({scoreboards, selected, onSelect}: ScoreboardTabsProps) {
    const [renaming, setRenaming] = React.useState<number | null>(null);
    const last = scoreboards[scoreboards.length - 1];

    const add = () => dashboard.scoreboards.add()
        .then(({amount}) => {
            onSelect(amount);
            refreshStatus();
        })
        .catch(() => toast.error(i18n.t("save_failed")));

    const remove = () => dashboard.scoreboards.remove()
        .then(({amount}) => {
            if (selected > amount) {
                onSelect(amount);
            }
            refreshStatus();
        })
        .catch(() => toast.error(i18n.t("save_failed")));

    return (
        <div className="flex flex-wrap items-center gap-1 border-b">
            <div role="tablist" aria-label={i18n.t("scoreboard")} className="flex min-w-0 flex-wrap items-center">
                {scoreboards.map(({number, name}) => {
                    const active = number === selected;
                    return renaming === number
                        ? <div key={number} className="px-1 py-1.5"><RenameInput number={number} name={name} onDone={() => setRenaming(null)}/></div>
                        : (
                            <button
                                key={number}
                                type="button"
                                role="tab"
                                aria-selected={active}
                                title="Double-click to rename"
                                onClick={() => onSelect(number)}
                                onDoubleClick={() => setRenaming(number)}
                                className={cn(
                                    "flex min-h-11 cursor-pointer items-center gap-2 px-3 text-[13px] whitespace-nowrap outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50",
                                    active ? "font-semibold text-foreground shadow-[inset_0_-2px_0_var(--brand)]" : "text-muted-foreground hover:text-foreground",
                                )}
                            >
                                <span className={cn(
                                    "grid size-[18px] place-items-center rounded text-[11px] font-bold",
                                    active ? "bg-brand text-primary-foreground" : "bg-secondary",
                                )}>{number}</span>
                                {name}
                            </button>
                        );
                })}
            </div>
            <Button
                variant="ghost"
                size="icon-sm"
                className="text-muted-foreground"
                aria-label={`Rename ${scoreboards.find((s) => s.number === selected)?.name ?? ""}`}
                title="Rename"
                onClick={() => setRenaming(selected)}
            >
                <Pencil/>
            </Button>
            <div className="flex-1"/>
            <AlertDialog>
                <AlertDialogTrigger asChild>
                    <Button variant="ghost" size="sm" disabled={scoreboards.length <= 1} title="Remove the last scoreboard" aria-label="Remove the last scoreboard">
                        <Minus/>
                    </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Remove {last?.name}?</AlertDialogTitle>
                        <AlertDialogDescription>
                            The last scoreboard is removed, with its players and score, as in the desktop app.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction className="bg-destructive text-white hover:bg-destructive/90" onClick={remove}>Remove</AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
            <Button
                variant="outline"
                size="sm"
                className="border-dashed"
                disabled={scoreboards.length >= MAX_SCOREBOARDS}
                title="Add a scoreboard, for another stream or station"
                onClick={add}
            >
                <Plus/>{i18n.t("scoreboard")}
            </Button>
        </div>
    );
}
