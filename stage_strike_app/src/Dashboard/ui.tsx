import React from "react";
import {Link} from "react-router-dom";
import {Minus, Plus} from "lucide-react";
import {Button} from "@/components/ui/button";
import {Spinner} from "@/components/ui/spinner";
import {cn} from "@/lib/utils";
import {useHdReady} from "./stateTypes";

/*
 * Pieces shared by the dashboard's pages, so they all look the same.
 */

export function PageHeader({title, description, children}: {
    title: React.ReactNode;
    description?: React.ReactNode;
    // Buttons on the right
    children?: React.ReactNode;
}) {
    return (
        <header className="flex flex-wrap items-center gap-3">
            <div className="min-w-60 flex-1">
                {/* On phones the top bar shows the title */}
                <h1 className="text-2xl font-bold tracking-tight max-lg:sr-only">{title}</h1>
                {description && <p className="mt-1 text-[13px] text-muted-foreground">{description}</p>}
            </div>
            {children}
        </header>
    );
}

/** A page's content, padded, with room at the bottom on phones */
export function PageBody({children, className}: {children: React.ReactNode; className?: string}) {
    const ready = useHdReady();
    return (
        <div className={cn("mx-auto flex w-full max-w-[100rem] flex-col gap-4 p-4 pb-16 lg:p-7", className)}>
            {ready ? children : <div className="flex items-center gap-2 text-sm text-muted-foreground"><Spinner/>Connecting to HyperDrive…</div>}
        </div>
    );
}

export function Panel({title, action, children, className, bodyClassName}: {
    title?: React.ReactNode;
    // A link or button at the right of the title
    action?: React.ReactNode;
    children: React.ReactNode;
    className?: string;
    bodyClassName?: string;
}) {
    return (
        <section className={cn("flex min-w-0 flex-col rounded-xl border bg-card text-card-foreground", className)}>
            {title && (
                <div className="flex items-center gap-2.5 border-b px-4 py-3">
                    <h2 className="flex-1 text-[15px] font-semibold">{title}</h2>
                    {action}
                </div>
            )}
            <div className={cn("flex flex-col p-4", bodyClassName)}>{children}</div>
        </section>
    );
}

export function PanelLink({to, children}: {to: string; children: React.ReactNode}) {
    return <Link to={to} className="text-[13px] font-semibold text-brand-text hover:underline">{children} →</Link>;
}

/** A bar of options above a page's content */
export function OptionsBar({children}: {children: React.ReactNode}) {
    return (
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2.5 rounded-xl border bg-card px-4 py-3 text-[13px] text-muted-foreground">
            {children}
        </div>
    );
}

/** − value + */
export function Stepper({label, value, min = 0, max = 99, onChange}: {
    label: string;
    value: number;
    min?: number;
    max?: number;
    onChange: (value: number) => void;
}) {
    return (
        <span className="flex items-center gap-2">
            {label}
            <span className="flex items-center rounded-md border">
                <Button variant="ghost" size="icon-sm" aria-label={`Fewer: ${label}`} disabled={value <= min} onClick={() => onChange(value - 1)}>
                    <Minus/>
                </Button>
                <span className="w-7 text-center font-semibold text-foreground tabular-nums">{value}</span>
                <Button variant="ghost" size="icon-sm" aria-label={`More: ${label}`} disabled={value >= max} onClick={() => onChange(value + 1)}>
                    <Plus/>
                </Button>
            </span>
        </span>
    );
}

export function EmptyState({children, action}: {children: React.ReactNode; action?: React.ReactNode}) {
    return (
        <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed px-6 py-10 text-center text-sm text-muted-foreground">
            <p className="max-w-md">{children}</p>
            {action}
        </div>
    );
}

/**
 * A value HyperDrive has, changed here: shows the change right away, until
 * HyperDrive's own value catches up (or a few seconds pass, if it refused).
 */
export function useOptimistic<T>(server: T): [T, (value: T) => void] {
    const [pending, setPending] = React.useState<{value: T; at: number} | null>(null);
    React.useEffect(() => {
        if (pending && (pending.value === server || Date.now() - pending.at > 3000)) {
            setPending(null);
        }
    }, [server, pending]);
    React.useEffect(() => {
        if (!pending) {
            return;
        }
        const timer = setTimeout(() => setPending(null), 3000);
        return () => clearTimeout(timer);
    }, [pending]);
    return [pending ? pending.value : server, (value: T) => setPending({value, at: Date.now()})];
}

/** Options loaded from HyperDrive that a page changes, sent back as they change */
export function useRemoteOptions<T extends object>(load: () => Promise<T>, save: (changes: Partial<T>) => Promise<unknown>) {
    const [options, setOptions] = React.useState<T | null>(null);

    const reload = React.useCallback(() => {
        load().then(setOptions).catch(() => {});
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    React.useEffect(() => {
        reload();
    }, [reload]);

    const change = (changes: Partial<T>) => {
        setOptions((was) => (was ? {...was, ...changes} : was));
        return save(changes).catch(() => reload());
    };

    return {options, change, reload};
}
