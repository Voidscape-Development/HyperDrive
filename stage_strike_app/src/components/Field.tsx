import type {ReactNode} from "react";
import {Label} from "@/components/ui/label";
import {cn} from "@/lib/utils";

/** A form control with its label above it */
export function Field({label, htmlFor, className, children}: {
  label: ReactNode;
  htmlFor?: string;
  className?: string;
  children: ReactNode;
}) {
  return <div className={cn("flex min-w-0 flex-col gap-1.5", className)}>
    <Label htmlFor={htmlFor} className="text-xs text-muted-foreground">{label}</Label>
    {children}
  </div>;
}
