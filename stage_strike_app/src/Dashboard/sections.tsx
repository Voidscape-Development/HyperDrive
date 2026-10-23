import {useSyncExternalStore} from "react";
import {
    ClipboardCheck,
    ClipboardList,
    Crosshair,
    Flag,
    Info,
    Eye,
    Home,
    List,
    ListOrdered,
    ListVideo,
    Mic,
    Network,
    Send,
    UserRound,
    UsersRound,
    type LucideIcon,
} from "lucide-react";

/*
 * The dashboard's sections, in the sidebar's order. Each browser can hide
 * the ones it doesn't use (a commentator's tablet showing only Commentary);
 * that's kept in the browser, not in HyperDrive.
 */

export type SectionGroup = "on_air" | "tournament_data" | "reporting";

export interface Section {
    id: string;
    label: string;
    path: string;
    icon: LucideIcon;
    group: SectionGroup;
}

export const OVERVIEW = {id: "overview", label: "Overview", path: "/", icon: Home};

export const SECTIONS: Section[] = [
    {id: "scoreboard", label: "Scoreboard", path: "/dashboard/scoreboard", icon: List, group: "on_air"},
    {id: "stage-strike", label: "Stage strike", path: "/dashboard/stage-strike", icon: Flag, group: "on_air"},
    {id: "character-select", label: "Character select", path: "/dashboard/character-select", icon: UserRound, group: "on_air"},
    {id: "commentary", label: "Commentary", path: "/dashboard/commentary", icon: Mic, group: "on_air"},
    {id: "display-controls", label: "Display Controls", path: "/dashboard/display-controls", icon: Eye, group: "on_air"},
    {id: "team-battle", label: "Crew/Team Battle", path: "/dashboard/team-battle", icon: UsersRound, group: "on_air"},
    {id: "stream-queue", label: "Stream Queue", path: "/dashboard/stream-queue", icon: ListVideo, group: "tournament_data"},
    {id: "bracket", label: "Bracket", path: "/dashboard/bracket", icon: Network, group: "tournament_data"},
    {id: "bracket-focus", label: "Bracket focus", path: "/dashboard/bracket-focus", icon: Crosshair, group: "tournament_data"},
    {id: "player-list", label: "Player List", path: "/dashboard/player-list", icon: ListOrdered, group: "tournament_data"},
    {id: "tournament-info", label: "Tournament Info", path: "/dashboard/tournament-info", icon: Info, group: "tournament_data"},
    {id: "reporting", label: "Reporting", path: "/dashboard/reporting", icon: ClipboardList, group: "reporting"},
    {id: "reporting-approval", label: "Approval", path: "/dashboard/reporting-approval", icon: ClipboardCheck, group: "reporting"},
    {id: "player-reporting", label: "Player reporting", path: "/dashboard/player-reporting", icon: Send, group: "reporting"},
];

export const GROUP_LABELS: Record<SectionGroup, string> = {
    on_air: "On air",
    tournament_data: "Tournament data",
    reporting: "start.gg reporting",
};

const HIDDEN_KEY = "hyperdrive-dashboard-hidden";

const readHidden = (): string[] => {
    try {
        const value = JSON.parse(window.localStorage.getItem(HIDDEN_KEY) ?? "[]");
        return Array.isArray(value) ? value.filter((v) => typeof v === "string") : [];
    } catch {
        return [];
    }
};

let hidden = readHidden();
const listeners = new Set<() => void>();

export function toggleHidden(id: string) {
    hidden = hidden.includes(id) ? hidden.filter((h) => h !== id) : [...hidden, id];
    try {
        window.localStorage.setItem(HIDDEN_KEY, JSON.stringify(hidden));
    } catch {
        // Kept for this page only
    }
    listeners.forEach((l) => l());
}

export function useHidden() {
    return useSyncExternalStore((listener) => {
        listeners.add(listener);
        return () => listeners.delete(listener);
    }, () => hidden);
}
