import {TriangleAlert} from "lucide-react";
import i18n from "../i18n/config";
import {Card, CardContent} from "@/components/ui/card";
import {Spinner} from "@/components/ui/spinner";

export function NoRulesetError({loading, connected, missingScoreboard}: {
  loading?: boolean;
  connected: boolean;
  // A page locked to a scoreboard that isn't open in HyperDrive
  missingScoreboard?: number | null;
}) {
  let content;
  if (connected && missingScoreboard) {
    content = <>
      <TriangleAlert className="size-10 text-warning" aria-hidden />
      <h2 className="text-lg font-semibold">{i18n.t("scoreboard_missing_title", {value: missingScoreboard})}</h2>
      <p className="text-sm text-muted-foreground">{i18n.t("scoreboard_missing")}</p>
    </>;
  } else if (!connected || loading) {
    content = <>
      <Spinner className="size-8 text-muted-foreground" />
      <p className="text-sm text-muted-foreground">{i18n.t(connected ? "loading" : "connecting")}</p>
    </>;
  } else {
    content = <>
      <TriangleAlert className="size-10 text-warning" aria-hidden />
      <h2 className="text-lg font-semibold">{i18n.t("no_ruleset_title")}</h2>
      <p className="text-sm text-muted-foreground">{i18n.t("no_ruleset_error")}</p>
    </>;
  }

  return <div className="flex flex-1 items-center justify-center p-4">
    <Card className="w-full max-w-md">
      <CardContent className="flex flex-col items-center gap-3 py-4 text-center">
        {content}
      </CardContent>
    </Card>
  </div>;
}
