LoadEverything().then(() => {
  gsap.config({ nullTargetWarn: false, trialWarn: false });

  Start = async (event) => {};

  Update = async (event) => {
    let data = event.data;
    let oldData = event.oldData;

    if (!SSD_HasChanged(data, oldData)) return;

    try {
      const state = SSD_GetState(data);

      $(".label_game").html(`Game ${state.game}`);

      // Each ban carries a thin bar in the color of whoever struck it
      let bansHtml = state.bans
        .map(
          (ban) => `
            <div class="ban_item" data-key="ban-${SSD_Escape(ban.stage.codename)}"
              style="--by-color: ${ban.team ? ban.team.color : "var(--ssd-neutral)"}">
              <div class="thumb">
                <div class="thumb_image" style="background-image: ${SSD_StageImage(ban.stage)}"></div>
                <div class="strike_x"></div>
              </div>
              <div class="stage_name">${SSD_StageName(ban.stage)}</div>
            </div>
          `
        )
        .join("");

      let pickHtml = state.pick
        ? `
          <div class="pick_item" data-key="pick-${SSD_Escape(state.pick.stage.codename)}">
            <div class="thumb" style="background-image: ${SSD_StageImage(state.pick.stage)}"></div>
            <div class="pick_text">
              <div class="pick_label">${state.pick.gentlemans ? "Gentleman's" : "Picked"}</div>
              <div class="stage_name fit"><div class="text">${SSD_StageName(state.pick.stage)}</div></div>
            </div>
          </div>
        `
        : `
          <div class="pick_item pending" data-key="pick-pending">
            <div class="thumb"></div>
            <div class="pick_text">
              <div class="pick_label">${state.turn ? state.turn.verb : "Picked"}</div>
              <div class="stage_name fit"><div class="text">TBD</div></div>
            </div>
          </div>
        `;

      $(".bar_divider").toggle(state.bans.length > 0);
      SSD_Render(".bans", bansHtml, { x: -16 });
      SSD_Render(".pick", pickHtml, { scale: 1.08 });
      SSD_SetVisible(".ssd_bar", state.hasContent);
    } catch (e) {
      console.log(e);
    }
  };
});
