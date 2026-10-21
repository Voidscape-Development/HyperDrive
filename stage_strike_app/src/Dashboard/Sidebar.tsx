import {Database, Eye, EyeOff, Lock, PanelLeftClose, PanelLeftOpen} from "lucide-react";
import {NavLink, useLocation} from "react-router-dom";
import {useSelector} from "react-redux";
import {BASE_URL} from "../env";
import {EventControls, useCompletedSetsText, DOT_CLASS} from "./EventControls";
import {GROUP_LABELS, OVERVIEW, SECTIONS, toggleHidden, useHidden, type SectionGroup} from "./sections";
import {lock} from "./session";
import {useStatus} from "./status";
import type {ReduxState} from "../redux/store";
import {Button} from "@/components/ui/button";
import {Tooltip, TooltipContent, TooltipTrigger} from "@/components/ui/tooltip";
import {cn} from "@/lib/utils";

const GROUP_TITLE = "px-3 pt-4 pb-1 text-[11px] font-bold tracking-wider text-muted-foreground uppercase";
const NAV_ITEM = "flex min-h-9 min-w-0 flex-1 items-center gap-2.5 rounded-lg px-2.5 text-[13px] font-medium outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 [&_svg]:size-[17px] [&_svg]:shrink-0";

function Brand({collapsed, onToggle}: {collapsed: boolean; onToggle?: () => void}) {
    return (
        <div className={cn("flex shrink-0 items-center gap-2.5 px-3.5 pt-3.5 pb-2.5", collapsed && "flex-col px-0")}>
            <img alt="" src={`${BASE_URL}/assets/icons/icon.png`} className="size-7"/>
            {!collapsed && <span className="flex-1 font-black tracking-wide italic">HYPERDRIVE</span>}
            {onToggle && (
                <Button
                    variant="ghost"
                    size="icon"
                    className="text-muted-foreground"
                    aria-label={collapsed ? "Expand the sidebar" : "Collapse the sidebar"}
                    title={collapsed ? "Expand the sidebar" : "Collapse the sidebar"}
                    onClick={onToggle}
                >
                    {collapsed ? <PanelLeftOpen/> : <PanelLeftClose/>}
                </Button>
            )}
        </div>
    );
}

function Footer({collapsed}: {collapsed: boolean}) {
    const connected = useSelector((s: ReduxState) => s.websocketInfo.status === "connected");
    const pinSet = useStatus()?.pinSet;
    const connection = connected ? "Connected to HyperDrive" : "Reconnecting to HyperDrive…";

    return (
        <div className={cn("flex shrink-0 flex-col gap-0.5 border-t p-2", collapsed && "items-center")}>
            <a
                href="/admin/"
                target="_blank"
                rel="noreferrer"
                title="Player database (opens in a new tab)"
                className={cn(NAV_ITEM, "flex-none hover:bg-accent", collapsed && "justify-center px-0")}
            >
                <Database/>
                {!collapsed && <><span className="flex-1">Player database</span><span className="text-xs text-muted-foreground">↗</span></>}
            </a>
            <div className={cn("flex min-h-9 items-center gap-2 pl-2.5 text-xs text-muted-foreground", collapsed && "justify-center pl-0")}>
                <span aria-hidden className={cn("size-2 shrink-0 rounded-full", connected ? "bg-live" : "bg-warning")}/>
                {collapsed ? <span className="sr-only">{connection}</span> : <span className="flex-1">{connection}</span>}
                {pinSet && !collapsed && (
                    <Button variant="ghost" size="icon-sm" aria-label="Lock this browser" title="Lock this browser (asks for the PIN again)" onClick={lock}>
                        <Lock/>
                    </Button>
                )}
            </div>
        </div>
    );
}

/** The sections, grouped, each with its show/hide eye */
function Sections({collapsed, onNavigate}: {collapsed: boolean; onNavigate?: () => void}) {
    const hidden = useHidden();
    const {pathname} = useLocation();
    const groups: SectionGroup[] = ["on_air", "tournament_data"];

    // A plain className, not NavLink's function: the rail's tooltips merge
    // their props into the link, which would turn a function into text
    const link = (path: string, label: string, Icon: typeof OVERVIEW.icon, dim = false) => {
        const active = pathname === path;
        return (
        <NavLink
            to={path}
            end
            onClick={onNavigate}
            className={cn(
                NAV_ITEM,
                active ? "bg-accent text-foreground [&_svg]:text-brand" : "hover:bg-accent/60",
                dim && !active && "text-muted-foreground",
                collapsed && "size-10 flex-none shrink-0 justify-center px-0",
            )}
        >
            <Icon/>
            {collapsed ? <span className="sr-only">{label}</span> : <span className="min-w-0 flex-1 truncate">{label}</span>}
        </NavLink>
        );
    };

    const withTooltip = (label: string, node: React.ReactNode) => collapsed ? (
        <Tooltip key={label}>
            <TooltipTrigger asChild>{node}</TooltipTrigger>
            <TooltipContent side="right">{label}</TooltipContent>
        </Tooltip>
    ) : node;

    return (
        <nav aria-label="Sections" className={cn("flex shrink-0 flex-col px-2", collapsed && "items-center")}>
            <div className="pt-2">{withTooltip(OVERVIEW.label, link(OVERVIEW.path, OVERVIEW.label, OVERVIEW.icon))}</div>
            {groups.map((group) => (
                <div key={group} className={cn("flex flex-col gap-px", collapsed && "items-center border-t pt-2 mt-2")}>
                    {!collapsed && <div className={GROUP_TITLE}>{GROUP_LABELS[group]}</div>}
                    {SECTIONS.filter((s) => s.group === group).map((section) => {
                        const isHidden = hidden.includes(section.id);
                        if (collapsed) {
                            return isHidden ? null : withTooltip(section.label, link(section.path, section.label, section.icon));
                        }
                        return (
                            <div key={section.id} className="flex items-center rounded-lg pr-0.5">
                                {link(section.path, section.label, section.icon, isHidden)}
                                <Button
                                    variant="ghost"
                                    size="icon-sm"
                                    className="text-muted-foreground"
                                    aria-label={`${isHidden ? "Show" : "Hide"} ${section.label} in this browser`}
                                    title={`${isHidden ? "Show" : "Hide"} ${section.label} in this browser`}
                                    onClick={() => toggleHidden(section.id)}
                                >
                                    {isHidden ? <EyeOff/> : <Eye/>}
                                </Button>
                            </div>
                        );
                    })}
                </div>
            ))}
        </nav>
    );
}

/** The completed sets' light, for the collapsed sidebar */
function SyncDot() {
    const {dot, text} = useCompletedSetsText();
    return (
        <Tooltip>
            <TooltipTrigger asChild>
                <span tabIndex={0} className="grid size-10 place-items-center rounded-lg outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50">
                    <span className={cn("size-2 rounded-full", DOT_CLASS[dot])}/>
                    <span className="sr-only">Completed sets: {text}</span>
                </span>
            </TooltipTrigger>
            <TooltipContent side="right">Completed sets: {text}</TooltipContent>
        </Tooltip>
    );
}

interface SidebarProps {
    collapsed?: boolean;
    onToggle?: () => void;
    // Closes the phone drawer once a section is picked
    onNavigate?: () => void;
    className?: string;
}

export function Sidebar({collapsed = false, onToggle, onNavigate, className}: SidebarProps) {
    return (
        <aside
            aria-label="HyperDrive dashboard"
            className={cn(
                "flex h-full flex-col overflow-y-auto border-r bg-card text-card-foreground",
                collapsed ? "w-17" : "w-68",
                className,
            )}
        >
            <Brand collapsed={collapsed} onToggle={onToggle}/>
            {collapsed ? (
                <div className="flex justify-center"><SyncDot/></div>
            ) : (
                <>
                    <div className={GROUP_TITLE + " pt-1"}>Event</div>
                    <div className="px-2"><EventControls/></div>
                </>
            )}
            <Sections collapsed={collapsed} onNavigate={onNavigate}/>
            <div className="flex-1"/>
            <Footer collapsed={collapsed}/>
        </aside>
    );
}
