import React from "react";
import {BASE_URL} from "../env";
import {ApiError, dashboard} from "./api";
import {setLocked, setToken, useLocked} from "./session";
import {useDesktopTheme} from "./theme";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {Spinner} from "@/components/ui/spinner";

/** The PIN screen, when HyperDrive has a dashboard PIN and this browser doesn't have it yet */
function PinScreen() {
    const [pin, setPin] = React.useState("");
    const [error, setError] = React.useState<string | null>(null);
    const [busy, setBusy] = React.useState(false);

    const submit = (e: React.FormEvent) => {
        e.preventDefault();
        setBusy(true);
        setError(null);
        dashboard.unlock(pin)
            .then(({token}) => setToken(token))
            .catch((err) => {
                setPin("");
                if (err instanceof ApiError && err.status === 429) {
                    setError("Too many wrong PINs. Wait a moment and try again.");
                } else if (err instanceof ApiError && err.status === 401) {
                    setError("That's not the PIN.");
                } else {
                    setError("HyperDrive didn't answer. Is it running?");
                }
            })
            .finally(() => setBusy(false));
    };

    return (
        <main className="flex min-h-dvh flex-col items-center justify-center gap-7 bg-background p-6 text-foreground">
            <div className="flex flex-col items-center gap-3">
                <img alt="" src={`${BASE_URL}/assets/icons/icon.png`} className="size-14"/>
                <span className="font-black tracking-wide italic">HYPERDRIVE</span>
            </div>
            <form onSubmit={submit} className="flex w-full max-w-80 flex-col gap-3.5 rounded-2xl border bg-card p-5">
                <h1 className="text-lg font-bold">Enter the dashboard PIN</h1>
                <p className="text-sm text-muted-foreground">
                    It's in HyperDrive's Settings › General on the streaming computer. This browser will remember it.
                </p>
                <label className="flex flex-col gap-1.5 text-xs font-semibold text-muted-foreground">
                    PIN
                    <Input
                        type="password"
                        autoComplete="one-time-code"
                        autoFocus
                        value={pin}
                        onChange={(e) => setPin(e.target.value)}
                        aria-invalid={!!error}
                        className="h-12 text-xl tracking-[0.4em]"
                    />
                </label>
                {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
                <Button type="submit" disabled={!pin || busy} className="h-12 text-base font-bold">
                    {busy ? <Spinner/> : "Unlock"}
                </Button>
            </form>
            <p className="max-w-72 text-center text-xs text-muted-foreground">
                Player pages like stage strike and character select don't need a PIN.
            </p>
        </main>
    );
}

/**
 * The dashboard's pages, behind the PIN when HyperDrive has one. The theme
 * is applied first, so the PIN screen already looks like HyperDrive.
 */
export function PinGate({children}: {children: React.ReactNode}) {
    useDesktopTheme();
    const locked = useLocked();
    const [failed, setFailed] = React.useState(false);

    React.useEffect(() => {
        dashboard.session()
            .then(({pinRequired, unlocked}) => setLocked(pinRequired && !unlocked))
            .catch(() => setFailed(true));
    }, []);

    if (failed) {
        return (
            <main className="flex min-h-dvh items-center justify-center bg-background p-6 text-sm text-foreground">
                HyperDrive didn't answer. Is it running? Reload the page to try again.
            </main>
        );
    }
    if (locked === "unknown") {
        return <main className="flex min-h-dvh items-center justify-center bg-background"><Spinner/></main>;
    }
    return locked ? <PinScreen/> : <>{children}</>;
}
