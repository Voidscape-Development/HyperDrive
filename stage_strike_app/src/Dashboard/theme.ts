import React from "react";
import {dashboard, type Theme} from "./api";

/*
 * The dashboard follows the desktop app's theme (Settings > Appearance):
 * its colors become the page's CSS variables (see index.css), so the
 * dashboard looks like HyperDrive whichever theme is picked.
 */

const VARIABLES: Record<string, string> = {
    "--background": "window",
    "--foreground": "text",
    "--card": "surface",
    "--card-foreground": "text",
    "--popover": "raised",
    "--popover-foreground": "text",
    "--primary": "accent",
    "--primary-foreground": "onAccent",
    "--secondary": "raised",
    "--secondary-foreground": "text",
    "--muted": "raised",
    "--muted-foreground": "muted",
    "--accent": "raisedHover",
    "--accent-foreground": "text",
    "--border": "border",
    "--input": "border",
    "--ring": "accent",
    "--brand": "accent",
    "--brand-text": "accentText",
    "--brand-soft": "accentSoft",
};

export function applyTheme(theme: Theme) {
    const style = document.documentElement.style;
    for (const [variable, key] of Object.entries(VARIABLES)) {
        const color = theme.colors[key];
        if (color) {
            style.setProperty(variable, color);
        }
    }
    style.setProperty("--radius", `${Math.max(0, theme.radius + 2) / 16}rem`);
    style.setProperty("color-scheme", theme.dark ? "dark" : "light");
    document.documentElement.classList.toggle("dark", theme.dark);
}

// Checked again when the page comes back to the front, in case it changed
export function useDesktopTheme() {
    React.useEffect(() => {
        const load = () => dashboard.theme().then(applyTheme).catch(() => {});
        load();
        const onVisible = () => document.visibilityState === "visible" && load();
        document.addEventListener("visibilitychange", onVisible);
        return () => document.removeEventListener("visibilitychange", onVisible);
    }, []);
}
