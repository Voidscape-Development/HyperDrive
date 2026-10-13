import type {ComponentProps, ReactNode} from "react";
import {Handshake, Redo2, RotateCcw, Undo2, Users} from "lucide-react";
import i18n from "../i18n/config";
import {RestartStageStrike, SetGentlemans, Undo, Redo, type StrikeTarget} from "./postActions";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {Button} from "@/components/ui/button";
import {cn} from "@/lib/utils";

interface FooterButtonProps extends ComponentProps<typeof Button> {
  icon: ReactNode;
  label: string;
  active?: boolean;
}

function FooterButton({icon, label, active, className, ...props}: FooterButtonProps) {
  return <Button
    variant="outline"
    className={cn(
      "h-auto min-w-0 flex-col gap-0.5 px-1 py-1.5 text-[10px] sm:h-9 sm:flex-row sm:gap-2 sm:px-3 sm:text-sm",
      active && "border-pick bg-pick text-zinc-950 hover:bg-pick/90 hover:text-zinc-950 dark:border-pick dark:bg-pick dark:hover:bg-pick/90",
      className,
    )}
    {...props}
  >
    {icon}
    <span className="block max-w-full truncate">{label}</span>
  </Button>;
}

interface FooterControlsProps {
  target: StrikeTarget;
  teamMode: boolean;
  isGentlemans: boolean;
  canToggleGentlemans?: boolean;
  canUndo: boolean;
  canRedo: boolean;
  onCharacters: () => void;
  missingCharacters: boolean;
}

export function FooterControls({
  target,
  teamMode,
  isGentlemans,
  canToggleGentlemans = true,
  canUndo,
  canRedo,
  onCharacters,
  missingCharacters,
}: FooterControlsProps) {
  return <div className={cn(
    "mx-auto grid w-full max-w-[1500px] gap-1 sm:gap-2",
    teamMode ? "grid-cols-4" : "grid-cols-5",
  )}>
    <FooterButton
      icon={<Undo2 />}
      label={i18n.t("undo")}
      disabled={!canUndo}
      onClick={() => Undo(target)}
    />
    <FooterButton
      icon={<Redo2 />}
      label={i18n.t("redo")}
      disabled={!canRedo}
      onClick={() => Redo(target)}
    />
    <FooterButton
      icon={<Handshake />}
      label={i18n.t("gentlemans_pick")}
      active={isGentlemans}
      aria-pressed={isGentlemans}
      disabled={!canToggleGentlemans}
      onClick={() => SetGentlemans(target, !isGentlemans)}
    />
    <FooterButton
      icon={<span className="relative">
        <Users className="size-4" />
        {missingCharacters &&
          <span className="absolute -top-0.5 -right-1 size-2 rounded-full bg-warning" />
        }
      </span>}
      label={i18n.t("characters")}
      onClick={onCharacters}
    />
    {/* Restarting is left to the page for both teams */}
    {!teamMode &&
      <AlertDialog>
        <AlertDialogTrigger asChild>
          <FooterButton icon={<RotateCcw />} label={i18n.t("restart_all")} />
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{i18n.t("restart_all")}</AlertDialogTitle>
            <AlertDialogDescription>{i18n.t("restart_confirm")}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{i18n.t("cancel")}</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-white hover:bg-destructive/90"
              onClick={() => RestartStageStrike(target)}
            >
              {i18n.t("restart_all")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    }
  </div>;
}
