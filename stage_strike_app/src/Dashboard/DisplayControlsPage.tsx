import React from "react";
import {Link2, RefreshCw, Search, X} from "lucide-react";
import {toast} from "sonner";
import {BASE_URL} from "../env";
import {dashboard} from "./api";
import {useHd} from "./stateTypes";
import {EmptyState, PageBody, PageHeader, Panel, useOptimistic} from "./ui";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {Popover, PopoverContent, PopoverTrigger} from "@/components/ui/popover";
import {Switch} from "@/components/ui/switch";

/** The links a Stream Deck or Companion uses for one folder or group */
function LinksMenu({kind, name}: {kind: "folder" | "group"; name: string}) {
    const base = `${BASE_URL}/display/${kind}/${encodeURIComponent(name)}`;
    const copy = (label: string, url: string) => {
        navigator.clipboard.writeText(url)
            .then(() => toast.success(`${label} copied`))
            .catch(() => toast(url));
    };
    return (
        <Popover>
            <PopoverTrigger asChild>
                <Button variant="ghost" size="icon-sm" className="text-muted-foreground" aria-label={`Links for ${name}`} title="Copy a link to show, hide or toggle it">
                    <Link2/>
                </Button>
            </PopoverTrigger>
            <PopoverContent align="end" className="w-56 p-1">
                {([["Toggle link", "/toggle"], ["Show link", "/show"], ["Hide link", "/hide"], ["State link", ""]] as const).map(([label, path]) => (
                    <button
                        key={label}
                        type="button"
                        className="flex min-h-9 w-full cursor-pointer items-center rounded-md px-2.5 text-left text-sm hover:bg-accent"
                        onClick={() => copy(label, base + path)}
                    >
                        Copy {label.toLowerCase()}
                    </button>
                ))}
            </PopoverContent>
        </Popover>
    );
}

function Row({kind, name, shown: serverShown, detail}: {kind: "folder" | "group"; name: string; shown: boolean; detail?: React.ReactNode}) {
    const [shown, setShown] = useOptimistic(serverShown);
    return (
        <div className="flex min-h-13 items-center gap-3 border-b px-4 last:border-0">
            <Switch
                aria-label={`Show ${name}`}
                checked={shown}
                onCheckedChange={(on) => {
                    setShown(on);
                    dashboard.display.set(kind, name, on ? "show" : "hide").catch(() => toast.error("Couldn't change it."));
                }}
            />
            <span className="flex min-w-0 flex-1 flex-col leading-snug">
                <span className={kind === "folder" ? "truncate font-mono text-[13px] font-semibold" : "truncate text-[13px] font-semibold"}>{name}</span>
                {detail && <span className="text-xs text-muted-foreground">{detail}</span>}
            </span>
            <span className={shown ? "text-xs font-semibold text-live" : "text-xs text-muted-foreground"}>{shown ? "Shown" : "Hidden"}</span>
            {kind === "group" ? (
                <>
                    <LinksMenu kind={kind} name={name}/>
                    <Button
                        variant="ghost"
                        size="icon-sm"
                        className="text-muted-foreground"
                        aria-label={`Remove group ${name}`}
                        title="Remove group"
                        onClick={() => dashboard.display.removeGroup(name).catch(() => toast.error("Couldn't remove it."))}
                    >
                        <X/>
                    </Button>
                </>
            ) : <LinksMenu kind={kind} name={name}/>}
        </div>
    );
}

/**
 * Display Controls: turns layouts on and off. Off plays the layout's hide
 * animation instead of the source disappearing from OBS.
 */
export default function DisplayControlsPage() {
    const display = useHd((s) => s.display);
    const [filter, setFilter] = React.useState("");
    const [newGroup, setNewGroup] = React.useState("");

    const match = (name: string) => name.toLowerCase().includes(filter.trim().toLowerCase());
    const folders = Object.entries(display?.folders ?? {}).filter(([name]) => match(name));
    const groups = Object.entries(display?.groups ?? {}).filter(([name]) => match(name));

    const addGroup = (e: React.FormEvent) => {
        e.preventDefault();
        if (!newGroup.trim()) {
            return;
        }
        dashboard.display.addGroup(newGroup.trim()).then(() => setNewGroup("")).catch(() => toast.error("Couldn't add it."));
    };

    return (
        <PageBody>
            <PageHeader title="Display Controls" description="Turn layouts on and off. Off plays the layout's hide animation.">
                <label className="relative">
                    <Search aria-hidden className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"/>
                    <Input aria-label="Filter layouts and groups" placeholder="Filter" value={filter} onChange={(e) => setFilter(e.target.value)} className="w-56 pl-9"/>
                </label>
                <Button variant="secondary" onClick={() => dashboard.display.all("show").catch(() => {})}>Show all</Button>
                <Button variant="secondary" onClick={() => dashboard.display.all("hide").catch(() => {})}>Hide all</Button>
            </PageHeader>

            <div className="grid grid-cols-1 items-start gap-4 xl:grid-cols-[3fr_2fr]">
                <Panel
                    title="Layouts"
                    bodyClassName="p-0"
                    action={
                        <Button variant="outline" size="sm" onClick={() => dashboard.display.refreshFolders().catch(() => {})}>
                            <RefreshCw/>Look for new layout folders
                        </Button>
                    }
                >
                    {folders.length === 0
                        ? <div className="p-4"><EmptyState>No layout folders{filter ? " match the filter" : ""}.</EmptyState></div>
                        : folders.map(([name, shown]) => <Row key={name} kind="folder" name={name} shown={shown}/>)}
                </Panel>

                <Panel title="Groups" bodyClassName="p-0">
                    <p className="border-b px-4 py-3 text-xs text-muted-foreground">
                        Add <code className="text-foreground">?display=group</code> to a layout's URL in OBS to turn it off with its group. Groups show up once a page using them is open.
                    </p>
                    {groups.map(([name, shown]) => <Row key={name} kind="group" name={name} shown={shown}/>)}
                    <form onSubmit={addGroup} className="flex gap-2 p-4">
                        <Input aria-label="New group name" placeholder="New group" value={newGroup} onChange={(e) => setNewGroup(e.target.value)}/>
                        <Button type="submit" variant="secondary" disabled={!newGroup.trim()}>Add group</Button>
                    </form>
                </Panel>
            </div>
        </PageBody>
    );
}
