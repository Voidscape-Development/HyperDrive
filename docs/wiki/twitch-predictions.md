# Twitch predictions

HyperDrive can run a Twitch prediction for the set on stream: "Who wins?" opens when a set is
loaded on the stream's scoreboard, and it's resolved with the winner once the set is over
(or cancelled, if another set is loaded first).

## Setting it up

The channel must be a Twitch **affiliate or partner**.

1. Get a user access token of your channel with the `channel:manage:predictions` scope,
   e.g. from a token generator for Twitch's API.
2. Paste it in [Settings › Twitch predictions](hyperdrive://open/settings/twitch-predictions)
   (or [API keys](hyperdrive://open/settings/api-keys)), under *Twitch token*.
3. On the same page, turn on **Run predictions for the set on stream**.

| Setting | |
| - | - |
| Scoreboard on stream | The number of the stream's scoreboard |
| Start one when a set loads | Otherwise start them by hand (below) |
| Pay out to the winner when the set ends | Otherwise resolve them by hand |
| Title | `{team1}`, `{team2}` and `{round}` are replaced. Twitch allows 45 characters |
| Time viewers have to predict | From 30 seconds to 30 minutes |

## Running them by hand

Open these links (e.g. from a Stream Deck's *Website* action):

| Link | |
| - | - |
| `/twitch/prediction/start` | Opens one for the stream's scoreboard |
| `/twitch/prediction/lock` | Locks it |
| `/twitch/prediction/cancel` | Cancels it |
| `/twitch/prediction/resolve/<team>` | Team 1 or 2 won |
| `/twitch/prediction` | Its state |

The state is also sent to the layouts as `twitch_prediction`.
