import React from "react";
import {CircleCheck} from "lucide-react";
import {toast} from "sonner";
import {BASE_URL} from "../env";
import {dashboard} from "./api";
import {useStatus} from "./status";
import {useHd} from "./stateTypes";
import {PageBody, PageHeader, Panel} from "./ui";
import {saveOnCommit, useAutoSaveForm} from "../ScoreboardPage/useAutoSaveForm";
import {Field} from "@/components/Field";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";

const failed = (what: string) => () => toast.error(`Couldn't ${what}.`);

/**
 * Tournament Info: what the layouts show about the event. Filled in when an
 * event is loaded; anything can be changed afterwards.
 */
export default function TournamentInfoPage() {
    const info = useHd((s) => s.tournamentInfo as Record<string, unknown> | undefined) ?? {};
    const loaded = useStatus()?.tournament.loaded;
    // Bumped to show a new icon, which keeps its file name
    const [iconVersion, setIconVersion] = React.useState(() => Date.now());

    const {values, setField, flush} = useAutoSaveForm(
        {
            tournamentName: String(info.tournamentName ?? ""),
            eventName: String(info.eventName ?? ""),
            address: String(info.address ?? ""),
            numEntrants: String(info.numEntrants ?? ""),
            shortLink: String(info.shortLink ?? ""),
        },
        (v, changed) => dashboard.tournamentInfo.set(Object.fromEntries(changed.map((k) => [k, v[k]]))),
        900,
    );

    const text = (key: keyof typeof values, label: string, props: React.ComponentProps<typeof Input> = {}) => (
        <Field label={label} htmlFor={`ti-${key}`}>
            <Input id={`ti-${key}`} value={values[key]} onChange={(e) => setField(key, e.target.value)} {...saveOnCommit(flush)} {...props}/>
        </Field>
    );

    const icon = (action: "download-icon" | "default-icon", what: string) => () =>
        dashboard.tournamentInfo.action(action).then(() => setIconVersion(Date.now())).catch(failed(what));

    return (
        <PageBody>
            <PageHeader title="Tournament Info" description="What the layouts show about the event. Filled in when an event is loaded; you can change anything.">
                <Button variant="secondary" disabled={!loaded} onClick={() => dashboard.tournamentInfo.action("load").catch(failed("load it from the tournament"))}>
                    Load from tournament
                </Button>
                <Button variant="outline" className="border-destructive/50 text-destructive hover:text-destructive"
                    onClick={() => window.confirm("Clear the tournament info?") && dashboard.tournamentInfo.action("clear").catch(failed("clear it"))}>
                    Clear
                </Button>
            </PageHeader>

            <div className="grid max-w-6xl grid-cols-1 items-start gap-4 lg:grid-cols-[3fr_2fr]">
                <Panel bodyClassName="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <div className="sm:col-span-2">{text("tournamentName", "Tournament name")}</div>
                    <div className="sm:col-span-2">{text("eventName", "Event name")}</div>
                    <div className="sm:col-span-2">{text("address", "Address")}</div>
                    <Field label="Date" htmlFor="ti-date">
                        <Input
                            id="ti-date"
                            type="date"
                            onChange={(e) => e.target.value && dashboard.tournamentInfo.set({startAt: e.target.value}).catch(failed("change the date"))}
                        />
                        {info.startAt ? <span className="text-xs text-muted-foreground">On the layouts: {String(info.startAt)}</span> : null}
                    </Field>
                    {text("numEntrants", "Entrants", {type: "number", min: 0, inputMode: "numeric"})}
                    <div className="sm:col-span-2">{text("shortLink", "Short link")}</div>
                    <p className="flex items-center gap-2 text-xs text-live sm:col-span-2">
                        <CircleCheck className="size-3.5"/>Changes go to the layouts as you type
                    </p>
                </Panel>

                <Panel title="Tournament icon">
                    <div className="flex flex-col gap-3">
                        <div className="grid h-44 place-items-center rounded-lg border border-dashed bg-background">
                            <img alt="The tournament's icon" src={`${BASE_URL}/layout/logo.png?v=${iconVersion}`} className="max-h-36 max-w-[80%] object-contain"/>
                        </div>
                        <Button variant="secondary" disabled={!loaded} onClick={icon("download-icon", "download the icon")}>Download from start.gg</Button>
                        <Button variant="outline" onClick={icon("default-icon", "use the default icon")}>Default icon</Button>
                        <p className="text-xs text-muted-foreground">
                            To use an image of yours, use Load local file in HyperDrive's Tournament Info. The logo and banner from start.gg also go to the layouts.
                        </p>
                    </div>
                </Panel>
            </div>
        </PageBody>
    );
}
