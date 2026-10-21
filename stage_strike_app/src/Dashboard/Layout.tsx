import React from "react";
import {Menu} from "lucide-react";
import {Outlet, useLocation} from "react-router-dom";
import websocketInit from "../ScoreboardPage/websocketInit";
import {OVERVIEW, SECTIONS} from "./sections";
import {Sidebar} from "./Sidebar";
import {Button} from "@/components/ui/button";
import {Sheet, SheetContent, SheetDescription, SheetTitle} from "@/components/ui/sheet";

const COLLAPSED_KEY = "hyperdrive-dashboard-collapsed";

function useCollapsed(): [boolean, () => void] {
    const [collapsed, setCollapsed] = React.useState(() => {
        try {
            return window.localStorage.getItem(COLLAPSED_KEY) === "1";
        } catch {
            return false;
        }
    });
    const toggle = () => setCollapsed((was) => {
        try {
            window.localStorage.setItem(COLLAPSED_KEY, was ? "0" : "1");
        } catch {
            // Kept for this page only
        }
        return !was;
    });
    return [collapsed, toggle];
}

/**
 * The dashboard: the sidebar on the left, the section on the right. On
 * phones the sidebar is a drawer opened from a top bar. Ctrl+B collapses
 * it to a rail of icons.
 */
export default function DashboardLayout() {
    const [collapsed, toggleCollapsed] = useCollapsed();
    const [drawerOpen, setDrawerOpen] = React.useState(false);
    const location = useLocation();

    const section = [OVERVIEW, ...SECTIONS].find((s) => s.path === location.pathname);

    React.useEffect(() => {
        websocketInit();
    }, []);

    React.useEffect(() => {
        document.title = `${section?.label ?? "Dashboard"} · HyperDrive`;
    }, [section]);

    React.useEffect(() => {
        const onKeyDown = (e: KeyboardEvent) => {
            if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "b") {
                e.preventDefault();
                toggleCollapsed();
            }
        };
        window.addEventListener("keydown", onKeyDown);
        return () => window.removeEventListener("keydown", onKeyDown);
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    return (
        <div className="flex h-dvh bg-background text-foreground">
            <Sidebar collapsed={collapsed} onToggle={toggleCollapsed} className="hidden shrink-0 lg:flex"/>

            <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
                <SheetContent side="left" className="w-80 max-w-[85vw] gap-0 p-0" showCloseButton={false}>
                    <SheetTitle className="sr-only">Menu</SheetTitle>
                    <SheetDescription className="sr-only">HyperDrive's sections and what's loaded</SheetDescription>
                    <Sidebar className="w-full border-r-0" onNavigate={() => setDrawerOpen(false)}/>
                </SheetContent>
            </Sheet>

            <div className="flex min-w-0 flex-1 flex-col">
                <header className="flex items-center gap-2 border-b bg-card px-2.5 py-2 lg:hidden">
                    <Button variant="ghost" size="icon-lg" aria-label="Open the menu" onClick={() => setDrawerOpen(true)}>
                        <Menu className="size-5"/>
                    </Button>
                    <span className="flex-1 truncate text-base font-bold">{section?.label ?? "Dashboard"}</span>
                </header>
                <main className="min-h-0 flex-1 overflow-y-auto">
                    <Outlet/>
                </main>
            </div>
        </div>
    );
}
