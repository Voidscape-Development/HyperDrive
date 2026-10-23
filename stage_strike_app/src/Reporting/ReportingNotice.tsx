import {AlertTriangle} from "lucide-react";
import {Alert, AlertDescription, AlertTitle} from "@/components/ui/alert";

/*
 * Why the reporting pages can't do their job right now, if they can't.
 */

const MESSAGES: Record<string, [string, string]> = {
    NO_TOURNAMENT: ["No tournament loaded", "Load a start.gg event in HyperDrive (or from the dashboard's sidebar) to report its sets."],
    NOT_STARTGG: ["Not a start.gg event", "Reporting from the web pages only works with start.gg events."],
    STATIONS_DISABLED: ["Reporting stations are off", "Turn them on in HyperDrive's Settings › Web Reporting."],
    OFFLINE: ["HyperDrive didn't answer", "Is it running? This page keeps trying."],
};

export function ReportingNotice({error, data}: {
    error: {code: string; message: string} | null;
    data?: {error?: string; hasToken?: boolean} | null;
}) {
    let notice: [string, string] | null = null;
    if (error) {
        notice = MESSAGES[error.code] ?? ["Couldn't get the sets", error.message];
    } else if (data?.error) {
        notice = ["start.gg couldn't be reached", `${data.error}. The sets shown may be out of date.`];
    } else if (data && data.hasToken === false) {
        notice = ["No start.gg API token", "Set one in HyperDrive's Settings › API Keys, from an account that's an admin of the tournament, to report sets."];
    }
    if (!notice) {
        return null;
    }
    return (
        <Alert className="border-warning/50">
            <AlertTriangle className="text-warning"/>
            <AlertTitle>{notice[0]}</AlertTitle>
            <AlertDescription>{notice[1]}</AlertDescription>
        </Alert>
    );
}
