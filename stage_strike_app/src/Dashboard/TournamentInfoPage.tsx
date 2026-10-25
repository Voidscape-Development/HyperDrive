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
import {Select, SelectContent, SelectItem, SelectTrigger, SelectValue} from "@/components/ui/select";

const failed = (what: string) => () => toast.error(`Couldn't ${what}.`);

// tournamentInfo.locationType, "" for not set (a select item can't be "")
const LOCATION_TYPES = [
    ["none", "Not set"],
    ["offline", "In person"],
    ["online", "Online"],
    ["hybrid", "Hybrid"],
] as const;

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
            tagline: String(info.tagline ?? ""),
            address: String(info.address ?? ""),
            cityState: String(info.cityState ?? ""),
            numEntrants: String(info.numEntrants ?? ""),
            numAttendees: String(info.numAttendees ?? ""),
            shortLink: String(info.shortLink ?? ""),
            timezone: String(info.timezone ?? ""),
            hashtag: String(info.hashtag ?? ""),
            discord: String(info.discord ?? ""),
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
                    <div className="sm:col-span-2">{text("tagline", "Tagline", {placeholder: "e.g. Top 8 · Sunday 6 PM"})}</div>
                    {text("address", "Address")}
                    {text("cityState", "City, state", {placeholder: "e.g. Springfield, IL"})}
                    <Field label="Date" htmlFor="ti-date">
                        <Input
                            id="ti-date"
                            type="date"
                            onChange={(e) => e.target.value && dashboard.tournamentInfo.set({startAt: e.target.value}).catch(failed("change the date"))}
                        />
                        {info.startAt ? <span className="text-xs text-muted-foreground">On the layouts: {String(info.startAt)}</span> : null}
                    </Field>
                    {text("numEntrants", "Entrants", {type: "number", min: 0, inputMode: "numeric"})}
                    <Field label="In person or online" htmlFor="ti-locationType">
                        <Select
                            value={String(info.locationType || "none")}
                            onValueChange={(v) => dashboard.tournamentInfo.set({locationType: v === "none" ? "" : v}).catch(failed("change it"))}
                        >
                            <SelectTrigger id="ti-locationType"><SelectValue/></SelectTrigger>
                            <SelectContent>
                                {LOCATION_TYPES.map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}
                            </SelectContent>
                        </Select>
                    </Field>
                    {text("numAttendees", "Attendees", {type: "number", min: 0, inputMode: "numeric"})}
                    {text("shortLink", "Short link")}
                    {text("timezone", "Time zone", {placeholder: "America/New_York"})}
                    {text("hashtag", "Hashtag", {placeholder: "without the #"})}
                    {text("discord", "Discord", {placeholder: "https://discord.gg/…"})}
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
