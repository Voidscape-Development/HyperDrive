LoadEverything().then(() => {
  gsap.config({ nullTargetWarn: false, trialWarn: false });

  Start = async (event) => {};

  Update = async (event) => {
    let data = event.data;
    let oldData = event.oldData;

    if (!SSD_HasChanged(data, oldData)) return;

    try {
      const state = SSD_GetState(data);

      $(".column_game").html(`Game ${state.game}`);

      // Edge color marks who struck the stage
      let bansHtml = state.bans
        .map(
          (ban) => `
            <div class="ban_line fit" data-key="ban-${SSD_Escape(ban.stage.codename)}"
              style="--by-color: ${ban.team ? ban.team.color : "var(--ssd-neutral)"}">
              <div class="text">${SSD_StageName(ban.stage)}</div>
            </div>
          `
        )
        .join("");

      let pickHtml = "";
      if (state.pick) {
        $(".pick_label").html(state.pick.gentlemans ? "Gentleman's" : "Picked");
        pickHtml = `
          <div class="pick_line fit" data-key="pick-${SSD_Escape(state.pick.stage.codename)}">
            <div class="text">${SSD_StageName(state.pick.stage)}</div>
          </div>
        `;
      } else {
        $(".pick_label").html(state.turn ? state.turn.verb : "Picked");
        pickHtml = `
          <div class="pick_line pending fit" data-key="pick-pending"
            style="--turn-color: ${state.turn ? state.turn.team.color : "var(--ssd-neutral)"}">
            <div class="text">${state.turn ? SSD_Escape(state.turn.team.name) : "TBD"}</div>
          </div>
        `;
      }

      $(".bans_section").toggle(state.bans.length > 0);
      $(".pick_section").toggleClass("pending", !state.pick);
      SSD_Render(".bans", bansHtml, { y: -8 });
      SSD_Render(".pick", pickHtml, { scale: 1.1 });
      SSD_SetVisible(".ssd_column", state.hasContent);
    } catch (e) {
      console.log(e);
    }
  };
});
