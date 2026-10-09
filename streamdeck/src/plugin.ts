import streamDeck from "@elgato/streamdeck";

import { redrawAll, sendStatus } from "./actions/base.ts";
import { BracketFocusAction, StageStrikeAction } from "./actions/bracket.ts";
import { DisplayAction } from "./actions/display.ts";
import { LoadSetAction, ResetAction, ScoreAction, SwapTeamsAction, TeamColorAction } from "./actions/scoreboard.ts";
import { BattlePlayerAction, BattleResetAction, BattleScoreAction } from "./actions/team-battle.ts";
import { parseAddress } from "./hyperdrive/connection.ts";
import { hyperdrive, type GlobalSettings } from "./plugin-context.ts";

streamDeck.logger.setLevel("info");

for (const action of [
	new ScoreAction(),
	new SwapTeamsAction(),
	new ResetAction(),
	new TeamColorAction(),
	new LoadSetAction(),
	new DisplayAction(),
	new BattleScoreAction(),
	new BattlePlayerAction(),
	new BattleResetAction(),
	new StageStrikeAction(),
	new BracketFocusAction(),
]) {
	streamDeck.actions.registerAction(action);
}

hyperdrive.on("state", redrawAll);
hyperdrive.on("status", (status) => {
	streamDeck.logger.info(`HyperDrive at ${hyperdrive.url}: ${status}`);
	void sendStatus();
});

function applySettings(settings: GlobalSettings): void {
	hyperdrive.connect(parseAddress(settings.host, settings.port));
}

// The address is set from any action's property inspector
streamDeck.settings.onDidReceiveGlobalSettings<GlobalSettings>((ev) => applySettings(ev.settings));

await streamDeck.connect();
applySettings(await streamDeck.settings.getGlobalSettings<GlobalSettings>());
