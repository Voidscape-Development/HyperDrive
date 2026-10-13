import {Ban, Check, Handshake, X, type LucideIcon} from "lucide-react";
import i18n from "../i18n/config";
import {cn} from "@/lib/utils";
import {PLAYER_BG} from "./playerColors";

interface StageCardProps {
  stageName: string;
  stageImage: string;
  isSelected: boolean;
  onClick: () => void;
  isStriked: boolean;
  isBanned: boolean;
  strikedBy: string | null;
  strikedByPlayer: number;
  isGentlemanEnabled: boolean;
  selectedBy: string | null;
  selectedByPlayer: number;
  disabled: boolean;
}

export function StageCard({
  stageName,
  stageImage,
  isSelected,
  onClick,
  isStriked,
  isBanned,
  strikedBy,
  strikedByPlayer,
  isGentlemanEnabled,
  selectedBy,
  selectedByPlayer,
  disabled,
}: StageCardProps) {
  // The marker over the picture: an icon in a round badge, ringed in its color
  let marker: {Icon: LucideIcon; className: string} | null = null;
  let label: string | null = null;
  let labelClass = "";

  if (isSelected) {
    marker = {Icon: isGentlemanEnabled ? Handshake : Check, className: "text-pick ring-pick"};
    label = isGentlemanEnabled ? i18n.t("gentlemans") : selectedBy;
    labelClass = isGentlemanEnabled ? "bg-pick" : PLAYER_BG[selectedByPlayer];
  } else if (isStriked) {
    marker = {Icon: X, className: "text-ban ring-ban"};
    label = strikedBy;
    labelClass = strikedByPlayer >= 0 ? PLAYER_BG[strikedByPlayer] : "";
  } else if (isBanned) {
    marker = {Icon: Ban, className: "text-ban ring-ban"};
    label = i18n.t("dsr");
    labelClass = "bg-ban text-white";
  }

  const restricted = isStriked || isBanned;

  return <button
    type="button"
    className={cn(
      "group relative block aspect-[3/2] w-full overflow-hidden rounded-xl border-2 bg-card text-left shadow-sm transition-all duration-200 outline-none",
      "focus-visible:ring-[3px] focus-visible:ring-ring/50",
      !disabled && "cursor-pointer hover:-translate-y-0.5 hover:border-foreground/30",
      disabled && "cursor-default",
      restricted && "border-ban/40",
      isSelected && (restricted
        ? "border-ban shadow-[0_0_16px] shadow-ban/50"
        : "border-pick shadow-[0_0_16px] shadow-pick/50"),
    )}
    onClick={disabled ? undefined : onClick}
    disabled={disabled}
    aria-pressed={isSelected}
    aria-label={stageName}
  >
    <img
      className={cn(
        "absolute inset-0 size-full object-cover transition-[filter] duration-300",
        restricted && "brightness-40 grayscale",
      )}
      src={stageImage}
      alt=""
      loading="lazy"
    />
    {marker &&
      <span
        className={cn(
          "ss-marker absolute top-[46%] left-1/2 flex aspect-square w-[min(28%,64px)] -translate-x-1/2 -translate-y-1/2 items-center justify-center",
          "rounded-full bg-zinc-950/85 shadow-[0_4px_18px_rgba(0,0,0,0.6)] ring-2 backdrop-blur-sm",
          marker.className,
        )}
      >
        <marker.Icon className="size-[55%]" strokeWidth={2.75} aria-hidden />
      </span>
    }
    {label &&
      <span
        className={cn(
          "absolute inset-x-0 top-0 truncate bg-white/85 px-2 py-0.5 text-xs font-semibold tracking-wide text-zinc-950 uppercase",
          labelClass,
        )}
      >
        {label}
      </span>
    }
    <span className="absolute inset-x-0 bottom-0 truncate bg-gradient-to-t from-black/90 to-transparent px-2 pt-4 pb-1.5 text-center text-[clamp(10px,1.4vw,14px)] font-semibold tracking-wider text-white uppercase">
      {stageName}
    </span>
  </button>;
}
