import i18n from "../i18n/config";
import type {Scoreboard} from "./types";
import {PlayerIdentity, PlayerNotes} from "./PlayerCard";
import {LastSets, PastEvents} from "./Stats";
import {Empty, numbered, teamName, teamPlayers} from "./util";
import {Badge} from "@/components/ui/badge";
import {Card, CardContent, CardHeader, CardTitle} from "@/components/ui/card";
import {Separator} from "@/components/ui/separator";

/** A team of the scoreboard: who its players are, their notes and, in 1v1, their stats */
export function TeamColumn({scoreboard, team}: {scoreboard: Scoreboard; team: 1 | 2}) {
    const data = scoreboard.team?.[String(team)];
    const players = teamPlayers(data).filter((p) => p.name);
    const singles = teamPlayers(scoreboard.team?.["1"]).length === 1 && teamPlayers(scoreboard.team?.["2"]).length === 1;
    const color = data?.color || (team === 1 ? "var(--p1)" : "var(--p2)");

    return <Card className="gap-4 overflow-hidden py-0">
        <CardHeader className="flex items-center gap-2 border-b px-4 py-3 [.border-b]:pb-3" style={{boxShadow: `inset 0 3px 0 ${color}`}}>
            <CardTitle className="min-w-0 flex-1 truncate">{teamName(data) || i18n.t("team_n", {value: team})}</CardTitle>
            {data?.losers ? <Badge variant="outline" className="border-ban/60 text-ban">{i18n.t("losers_short")}</Badge> : null}
        </CardHeader>
        <CardContent className="flex flex-col gap-5 px-4 pb-4">
            {players.length === 0 ? <Empty>{i18n.t("no_players_loaded")}</Empty> : null}
            {players.map((player, i) => <div key={i} className="flex flex-col gap-4">
                {i > 0 ? <Separator/> : null}
                <PlayerIdentity person={player} color={color}/>
                <PlayerNotes person={player}/>
            </div>)}
            {players.length > 0 && singles ? <>
                <LastSets sets={numbered(scoreboard.last_sets?.[String(team)])}/>
                <PastEvents sets={numbered(scoreboard.history_sets?.[String(team)])}/>
            </> : null}
            {players.length > 1 ? <Empty>{i18n.t("stats_singles_only")}</Empty> : null}
        </CardContent>
    </Card>;
}
