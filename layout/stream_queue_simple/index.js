LoadEverything().then(() => {
    let config = {
        "assets": {
          "default": {}
        },
        "stream": "",
        "default_stream" : "",
        "sets_displayed" : -1,
        "display_first_set": true,
        "station" : -1,
        "currentEventOnly": false,
        "display" : {
            "station" : false,
            "country_flag" : true,
            "state_flag" : true,
            "avatar" : true,
            "stream_name": "multistream",
            "eta": true
        },
        "minimum_determined_players": 1
    }
    
    function isDefault(value){
        return value === "" || value === -1 || value === undefined || value === null
    }

    let window_config = window.config || {}

    function assignDefault(target, source){
        for (k in target){
            let value = source[k]
            if (typeof value === 'object' && value !== null){
                let matchingObject = target[k];
                if (typeof matchingObject != 'object'){
                    matchingObject = value;
                } else {
                    assignDefault(matchingObject, value);
                }
            }
            if (!isDefault(value)){
                target[k] = value
            }
        }
    }

    assignDefault(config, hd_settings);

    if (!config.display){
        config.display = {};
    }

    let first_index = config.display_first_set ? 0 : 1    
    let sets_nb = config.sets_displayed;
    if (sets_nb < 0) sets_nb = undefined;

    gsap.config({ nullTargetWarn: false, trialWarn: false });

    let startingAnimation = gsap.timeline({ paused: true });

    Start = async (event) => {
        startingAnimation.restart();
    };

    /**
     * Wraps content in a .text element to emulate SetInnerHtml's behavior.
     */
    function wrap_text(txt){
        return `
            <div class = "text">${txt}</div>
        `
    }
    
    current_set_nb = 0; // ooooo dirty ass global var
    function resetSetsCount(){
        current_set_nb = 0;
    }

    // Each stream's queue, by stream name: what the Stream Queue widget
    // sends (stream_queue.byName), or the old streamQueue
    function stream_queues(data){
        return _.get(data, "stream_queue.byName") || (data && data.streamQueue) || {};
    }

    // A stream's queue, its name in any case
    function stream_queue(data, streamName){
        let queues = stream_queues(data);
        if (queues[streamName]) return queues[streamName];
        let lname = String(streamName || "").toLowerCase();
        let key = Object.keys(queues).find(k => k.toLowerCase() == lname);
        return key ? queues[key] : undefined;
    }

    // The stream linked to this scoreboard in the Stream Queue widget
    function scoreboard_stream(data){
        let streams = _.get(data, "stream_queue.streams") || [];
        let stream = streams.find(s => String(s.scoreboard) == String(window.scoreboardNumber));
        return stream ? stream.name : null;
    }

    // "~15 min" until the set should start, from the Stream Queue widget
    function eta_text(set){
        if (!config.display.eta || set.eta_minutes === undefined || set.eta_minutes === null) return "";
        if (set.eta_minutes <= 0) return "";
        return `~${set.eta_minutes} min`;
    }


    function online_avatar_html(player, t){
        return `
            <div class = "p${t}_avatar avatar_container">
                ${player.online_avatar ? `<img class="avatar" src='${player.online_avatar}' />` : ""}
            </div>
        `
    }

    async function team_html(set, t, s, isTeams, resolver){

        let team = set.team[""+t];

        if (!team) return `<div class = "p${t} tbd_container"><div class = "TBD">TBD</div></div>`;

        let player = team.player["1"] || {};
        // Sets typed in by hand have no flags
        let country = player.country || {};
        let state = player.state || {};

        resolver.add(`.set${current_set_nb} .p${t} .tag`, 
            isTeams ? (team.teamName || team.name) :
                `
                <span class="sponsor">
                    ${player.team ? player.team : ""}
                </span>
                ${player.name}
                ${team.losers ? "<span class='losers'>L</span>" : ""}
                `
        )

        resolver.add(`.set${current_set_nb} .p${t} .twitter`, 
            (!isTeams) ?  `<span class="twitter_logo"></span>${String(player.twitter)}` : ""  
        )

        return `
            <div class = "p${t} team">
                ${isTeams && !config.display.avatar ? "" : online_avatar_html(player, t)}
                <div class = "flags">
                    ${ isTeams ? "" :
                        (country.asset && config.display.country_flag ? `<img class='flag' src='../../${country.asset.toLowerCase()}' />` : "") +
                        (state.asset && config.display.state_flag? `<img class='flag' src='../../${state.asset}' />` : "")
                    }
                </div>
                <div class = "name">
                    <div class = "tag"></div>
                    <div class = "extra">
                        ${ player.twitter ?
                            ` <div class = "twitter">  </div> ` : ''
                        }
                        ${ player.pronoun ?
                            ` <div class = "pronoun"> ${ wrap_text((!isTeams && true) ?  String(player.pronoun) : "") } </div>` : ''
                        }
                        ${ player.seed ?
                            `<div class = "seed"> ${wrap_text("Seed " + player.seed)} </div> ` : ''
                        }
                       
                        
                    </div>
                </div>
            </div>
        `
    }

    async function queue_html(queue, resolver, display_set_station, station = -1){
        let html = "";

        for (const [s, set] of Object.values(queue).slice(first_index).entries()){
            if (sets_nb && (current_set_nb >= sets_nb)) break;
            if (!set.team) continue;
            if (config.minimum_determined_players > 0 && !set.team[""+config.minimum_determined_players]) continue;

            if (config.currentEventOnly && !set.isCurrentEvent) continue;
            if (station != -1 && station != set.station) continue;

            let isTeams = set.team["1"] && Object.keys(set.team["1"].player).length > 1;

            html += `
                <div class="set${current_set_nb} set">
                    ${ await team_html(set, 1, s + 1 , isTeams, resolver) }
                    <div class = "vs_container">
                        <div class = "vs vs_${config.display.station ? 'small' : 'big'}">VS</div>
                        ${display_set_station && set.station && set.station != -1 ? '<div class = "station"></div>' : ''}
                        <div class = "phase"> </div>
                        <div class = "match"> </div>

                    </div>
                    ${ await team_html(set, 2, s + 1, isTeams, resolver) }
                </div>
            `;

            resolver.add(`.set${current_set_nb} .match`, [set.match, eta_text(set)].filter(Boolean).join(" · "));
            resolver.add(`.set${current_set_nb} .phase`, set.phase);
            resolver.add(`.set${current_set_nb} .station`, "Station " + set.station);

            current_set_nb++;
        }

        return html;
    }

    function stream_name_html(stream){
        return `<div class = "message"><img class = "twitch_logo" src = "./twitch.svg"></img>/${stream}</div>`
    }

    let previous_display = null;

    async function display_allstream(data, oldData){
        console.log("Display AllStream")
        if (previous_display == 1 && oldData && JSON.stringify(stream_queues(data)) == JSON.stringify(stream_queues(oldData))) return;

        previous_display = 1

        let html = ""
        let resolver = new ContentResolver();

        resetSetsCount();

        let queues = stream_queues(data);
        for (let stream in queues){
            if (config.display.stream_name){
                html += stream_name_html(stream)
            }
            html += await queue_html(queues[stream], resolver, config.display.station, config.station)
        }

        update_content(html, resolver);
    }

    async function display_stream(data, oldData, streamName){
        console.log("Display Stream", streamName)

        console.log(previous_display)
        if (previous_display == streamName && oldData && JSON.stringify(stream_queue(data, streamName)) == JSON.stringify(stream_queue(oldData, streamName))) return;

        previous_display = streamName

        let html = ""
        let resolver = new ContentResolver();

        let queue = stream_queue(data, streamName);
        if (queue)  {
            if (config.display.stream_name == true){
                html += stream_name_html(streamName)
            }
    
            resetSetsCount();
            html += await queue_html(queue, resolver, config.display.station, config.station);
        }


        update_content(html, resolver);
    }

    async function display_station(data, oldData){
        console.log("Display Station")
        if (previous_display == 2 && oldData.score && oldData.score[window.scoreboardNumber].station_queue && JSON.stringify(data.score[window.scoreboardNumber].station_queue) == JSON.stringify(oldData.score[window.scoreboardNumber].station_queue)) return;
    
        previous_display = 2

        let html = ""
        let resolver = new ContentResolver();

        let queue = data.score[window.scoreboardNumber].station_queue;
        if (queue) {
            html += await queue_html(queue, resolver, false);
        }

        update_content(html, resolver)
    }


    function update_content(html, resolver){
            //console.log(html);
            $(".stream_queue_content").html(html);
            resolver.resolve()

            let tl = gsap.timeline();
            for (let i = 0; i <= current_set_nb; i++){
                tl.from(
                    $(`.set${i}`),
                    { x: -100, autoAlpha: 0, duration: 0.3, onComplete: () => {console.log("COMPLETED")} },
                    0.2 + 0.2 * i,
                );
            }
            tl.from(
                $(`.message`),
                {autoAlpha: 0, duration : 0.3},
                0.3 + 0.2 * current_set_nb
            );
            tl.resume();
    }

    Update = async (event) => {
        let data = event.data;
        let oldData = event.oldData;


        //let stream = config.stream || data.score[window.scoreboardNumber].station || config.default_stream


        if (!data.score) return;

        if (config.stream && !config.force_multistream){
            
            if (config.stream == "all"){
                display_allstream(data, oldData);
            } else {
                display_stream(data, oldData, config.stream)
            }
        } else {
            let hd_station = data.score[window.scoreboardNumber].station;
            if (hd_station){
                if (data.score[window.scoreboardNumber].auto_update == "station"){
                    display_station(data, oldData);
                } else {
                    display_stream(data, oldData, hd_station)
                }
            } else if (scoreboard_stream(data)) {
                display_stream(data, oldData, scoreboard_stream(data));
            } else if (config.default_stream) {
                display_stream(data, oldData, config.default_stream);
            } else {
                display_allstream(data, oldData);
            }
        }

        /*
        if (
            !oldData.streamQueue ||
            JSON.stringify(data.streamQueue) !=
            JSON.stringify(oldData.score.streamQueue) || 
            ( !hd_settings.stream && oldData.score[window.scoreboardNumber].station != data.score[window.scoreboardNumber].station)
        ) {


            
            if (!stream){
                $(".stream_queue_content").html('<div class = "message">No stream (twitch username) selected. Enter one in HyperDrive or set the "stream" or "default_stream" value in this layout\'s settings.json</div>');
                return;
            }
        }
        */
        

    }
})