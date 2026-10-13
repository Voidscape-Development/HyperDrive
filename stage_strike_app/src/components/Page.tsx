import type {ReactNode} from "react";

/** A whole screen of the app: a top bar, the content, and maybe a bottom bar */
export function Page({children}: {children: ReactNode}) {
  return <div className="flex h-dvh flex-col bg-background text-foreground">{children}</div>;
}
