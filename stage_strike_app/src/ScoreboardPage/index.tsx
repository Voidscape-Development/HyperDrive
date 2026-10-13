import React from "react";
import {shallowEqual, useDispatch, useSelector} from "react-redux";
import i18n from "../i18n/config";
import CurrentSet from "./CurrentSet";
import UpcomingSets from "./UpcomingSets";
import {Header} from "./Header";
import {hdStore, type ReduxState} from "../redux/store";
import {hdStateSlice} from "../redux/hdState";
import websocketInit from "./websocketInit";
import websocketConnection from "../websocketConnection";
import {selectedScoreboardSlice} from "../redux/uiState";
import type {HDState} from "../backendDataTypes";
import {Card, CardContent} from "@/components/ui/card";
import {Spinner} from "@/components/ui/spinner";
import {Tabs, TabsContent, TabsList, TabsTrigger} from "@/components/ui/tabs";

/**
 * Main page for the scoreboard. This whole contraption is powered by HyperDrive's python-side
 * program state. In order to do that, we subscribe to updates that get sent out and update
 * our state piecemeal. Each update has a number so that we can tell if our updates are stale
 * or out of order and request a full state send-over.
 */
export default function ScoreboardPage() {
    const dispatch = useDispatch();
    const {loading, errored, selectedScoreboard, scoreboards} = useSelector((state: ReduxState) => ({
        loading: (
            state.hdState.initializing
            || state.hdCharacters.initializing
            || state.hdPlayers.initializing
            || state.hdGames.initializing
            || state.hdCountries.initializing
        ),
        errored: state.websocketInfo.status === "errored",
        scoreboards: state.hdState.hdState.score,
        selectedScoreboard: state.selectedScoreboard.value
    }), shallowEqual);

    React.useEffect(() => {
        document.title = `HyperDrive ${i18n.t("scoreboard")}`;
        websocketInit();
    }, []);

    const onSelectedSetChanged = () => {
        dispatch(hdStateSlice.actions.loadingNewData({}));
    };

    const onSelectedGameChanged = (newGame: string) => {
        websocketConnection.instance().emit('update_game', {codename: newGame});
    };

    let body;
    if (errored || loading) {
        body = (
            <Card className="m-4 py-4">
                <CardContent className="flex items-center gap-3 text-sm">
                    {errored ? i18n.t("failed_to_connect") : <><Spinner/>{i18n.t("loading")}</>}
                </CardContent>
            </Card>
        );
    } else {
        body = (
            <>
                <Header onSelectedGameChange={onSelectedGameChanged}/>
                {/* Extra margin at the bottom allows for mobile users to see the bottom of the page better. */}
                <div className="mx-auto mb-48 flex w-full max-w-6xl flex-col gap-8 px-4 pt-3 pb-4">
                    <Tabs
                        value={String(selectedScoreboard)}
                        onValueChange={(value) =>
                            hdStore.dispatch(selectedScoreboardSlice.actions.setSelectedScoreboard(Number(value)))}
                    >
                        <div className="overflow-x-auto">
                            <TabsList>
                                {scoreboardKeys(scoreboards).map(sbName =>
                                    <TabsTrigger key={sbName} value={String(sbName)}>
                                        {i18n.t("scoreboard_n", {value: sbName})}
                                    </TabsTrigger>
                                )}
                            </TabsList>
                        </div>
                        <TabsContent value={String(selectedScoreboard)}>
                            <CurrentSet scoreboardNumber={selectedScoreboard}/>
                        </TabsContent>
                    </Tabs>
                    <UpcomingSets onSelectedSetChanged={onSelectedSetChanged} scoreboardNumber={selectedScoreboard}/>
                </div>
            </>
        );
    }

    return <div className="flex h-dvh flex-col overflow-auto bg-background text-foreground">{body}</div>;
}

const scoreboardKeys = (scoreboards: HDState['score']) => {
    if (scoreboards) {
        return Object.keys(scoreboards)
            .filter(k => k.match(/^\d+$/))
            .map(k => Number.parseInt(k));
    } else {
        return [];
    }
};
