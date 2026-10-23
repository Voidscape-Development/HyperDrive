import React from "react";
import {Link, useNavigate} from "react-router-dom";
import {LayoutDashboard} from "lucide-react";
import {toast} from "sonner";
import {BASE_URL} from "../env";
import {PinGate} from "../Dashboard/PinGate";
import {PageBody, PageHeader} from "../Dashboard/ui";
import {useStatus} from "../Dashboard/status";
import websocketInit from "../ScoreboardPage/websocketInit";
import AdminPage from "./AdminPage";
import ApprovalPage from "./ApprovalPage";
import {dashboardStationApi} from "./api";
import {StationContent} from "./StationPage";
import {Button} from "@/components/ui/button";

/*
 * The reporting pages: in the dashboard's sidebar, and on their own at
 * /report-admin and /report-approval (behind the dashboard's PIN) and
 * /report (the players' station, see StationPage).
 */

export {default as StationPage} from "./StationPage";

/** A toast when players send a result, on every dashboard page */
export function usePendingToasts(approvalPath: string) {
    const pending = useStatus()?.reporting?.pending;
    const previous = React.useRef<number | undefined>(undefined);
    const navigate = useNavigate();
    React.useEffect(() => {
        if (pending === undefined) {
            return;
        }
        if (previous.current !== undefined && pending > previous.current) {
            const added = pending - previous.current;
            toast(`${added === 1 ? "A result was" : `${added} results were`} sent from a reporting station`, {
                description: `${pending} waiting for approval`,
                action: {label: "Review", onClick: () => navigate(approvalPath)},
            });
        }
        previous.current = pending;
    }, [pending, approvalPath, navigate]);
}

export function AdminSection() {
    return <AdminPage approvalPath="/dashboard/reporting-approval"/>;
}

export function ApprovalSection() {
    return <ApprovalPage/>;
}

/** The players' station inside the dashboard, e.g. on the TO's own laptop */
export function StationSection() {
    return (
        <PageBody className="max-w-3xl">
            <PageHeader title="Player reporting" description="What players see at a reporting station (/report). Results sent here wait for approval too."/>
            <StationContent api={dashboardStationApi}/>
        </PageBody>
    );
}

function Standalone({title, children}: {title: string; children: React.ReactNode}) {
    React.useEffect(() => {
        document.title = `${title} · HyperDrive`;
        websocketInit();
    }, [title]);
    return (
        <PinGate>
            <div className="flex h-dvh flex-col bg-background text-foreground">
                <header className="flex items-center gap-3 border-b bg-card px-4 py-2.5">
                    <img alt="" src={`${BASE_URL}/assets/icons/icon.png`} className="size-8"/>
                    <span className="flex-1 font-semibold">{title}</span>
                    <Button variant="ghost" asChild>
                        <Link to="/report-admin">Reporting</Link>
                    </Button>
                    <Button variant="ghost" asChild>
                        <Link to="/report-approval">Approval</Link>
                    </Button>
                    <Button variant="ghost" asChild>
                        <Link to="/"><LayoutDashboard/>Dashboard</Link>
                    </Button>
                </header>
                <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
            </div>
        </PinGate>
    );
}

function StandaloneToasts() {
    usePendingToasts("/report-approval");
    return null;
}

/** /report-admin */
export function AdminStandalone() {
    return (
        <Standalone title="Reporting">
            <StandaloneToasts/>
            <AdminPage approvalPath="/report-approval"/>
        </Standalone>
    );
}

/** /report-approval */
export function ApprovalStandalone() {
    return (
        <Standalone title="Approval">
            <StandaloneToasts/>
            <ApprovalPage/>
        </Standalone>
    );
}
