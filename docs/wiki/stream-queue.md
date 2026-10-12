# Stream queue

The [Stream Queue](hyperdrive://open/stream-queue) tab lists the sets coming up on each
stream, shows when each one should start, and can load the next one onto the scoreboard
when a set ends.

It needs a start.gg event (see [Tournaments](tournaments.md)).

## Streams

Streams in start.gg's stream queue are added automatically (turn off **Add start.gg's
streams automatically** to pick them yourself). **+** adds a stream by hand: type its name,
e.g. the Twitch channel. A stream with the same name as one in start.gg's stream queue gets
its queue.

For each stream:

| Option | What it does |
| - | - |
| **Scoreboard** | The scoreboard showing this stream's sets |
| **Load next set** | Loads the queue's next set into that scoreboard now |
| **After a set** | What happens when the set on the scoreboard is over (reported, or finished on start.gg): *Do nothing*, *Ask to load the next set* or *Load the next set* |

## The queue

Each set shows its station, its status (*In progress*, *Called*, *Finished*) and when it
**Starts**: an estimate, from how long the event's last sets took.

The buttons under the queue:

| Button | What it does |
| - | - |
| **Load into scoreboard** | Loads the selected set into the stream's scoreboard |
| **▲**, **▼** | Moves the set up or down |
| **Remove** | Takes the set out of this queue (start.gg's queue isn't changed) |
| **Add set…** | Adds a set of the event |
| **Add custom…** | Adds a set that isn't on start.gg, e.g. an exhibition |
| **Reset** | Back to start.gg's queue, undoing the changes made here |

Right-click a set for **Load into scoreboard**, **Move to the top** and **Remove**.

Changes made here only change HyperDrive's queue, not start.gg's.

### Calling sets and assigning streams on start.gg

With a start.gg API token from an admin of the tournament (in
[Settings › API Keys](hyperdrive://open/settings/api-keys)), right-click a set and open
**On start.gg** to:

- **Call the set**, which notifies the players.
- **Assign to** the stream, or **Assign to station**.
- **Update the streams and stations** from start.gg.

## Updating

The queues update by themselves; **Update every** sets how often. **Update the queues now**
updates them immediately.

## Layouts

- `stream_queue/index.html`: the next sets of the stream linked to the layout's scoreboard.
- `stream_queue/index-multistream.html`: every stream's queue.
- `stream_queue/index-stations.html`: a station's queue.
- `stream_queue/next_match.html`, `stream_queue_simple/`: just the next set.

`layout/stream_queue/readme.md` explains which queue each one shows and its options.
