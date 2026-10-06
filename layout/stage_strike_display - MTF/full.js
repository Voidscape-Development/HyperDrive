LoadEverything().then(() => {
  gsap.config({ nullTargetWarn: false, trialWarn: false });

  Start = async (event) => {};

  let lastBackdrop = null;

  // Chip naming who made the call, tinted with their team color.
  // Player chips get .team so a theme can recolor them.
  function ByChip(label, name, color, isTeam = false) {
    return `
      <div class="by_chip ${isTeam ? "team" : ""}" style="--by-color: ${color}">
        <div class="by_label">${label}</div>
        <div class="by_name fit"><div class="text">${SSD_Escape(name)}</div></div>
      </div>
    `;
  }

  Update = async (event) => {
    let data = event.data;
    let oldData = event.oldData;

    if (!SSD_HasChanged(data, oldData)) return;

    try {
      const state = SSD_GetState(data);

      SSD_ApplyMtfColors(data);

      $(".header_game").html(`Game ${state.game}`);

      let status = "";
      if (state.pick) {
        status = state.pick.gentlemans ? "Gentleman's agreement" : "Stage locked in";
      } else if (state.turn) {
        status = `${SSD_Escape(state.turn.team.name)} ${state.turn.verb.toLowerCase()}`;
      }
      $(".header_status .text").html(status);
      FitText($(".header_status"));

      let bansHtml = state.bans
        .map(
          (ban) => `
            <div class="card ban" data-key="ban-${SSD_Escape(ban.stage.codename)}">
              <div class="card_image" style="background-image: ${SSD_StageImage(ban.stage)}"></div>
              <div class="strike_x"></div>
              ${
                ban.team
                  ? ByChip("Banned by", ban.team.name, ban.team.color, true)
                  : ByChip("Banned", ban.reason || "Ruleset", "var(--ssd-neutral)")
              }
              <div class="card_name fit"><div class="text">${SSD_StageName(ban.stage)}</div></div>
            </div>
          `
        )
        .join("");

      // Variants with body.show-available also list the stages nobody has struck yet.
      // Once a stage is locked in it's marked .chosen in place; the rest are .out
      const showAvailable = $("body").hasClass("show-available");
      const OpenCardState = (stage) =>
        !state.pick ? "" : stage.codename === state.pick.stage.codename ? "chosen" : "out";
      if (showAvailable) {
        bansHtml += state.available
          .map(
            (stage) => `
              <div class="card open ${OpenCardState(stage)}" data-key="open-${SSD_Escape(stage.codename)}">
                <div class="card_image" style="background-image: ${SSD_StageImage(stage)}"></div>
                <div class="card_name fit"><div class="text">${SSD_StageName(stage)}</div></div>
              </div>
            `
          )
          .join("");
      }

      let pickHtml = "";
      if (state.pick) {
        pickHtml = `
          <div class="card picked" data-key="pick-${SSD_Escape(state.pick.stage.codename)}">
            <div class="card_image" style="background-image: ${SSD_StageImage(state.pick.stage)}"></div>
            ${
              state.pick.team
                ? ByChip("Picked by", state.pick.team.name, state.pick.team.color, true)
                : ByChip("Picked", "Gentleman's", "var(--ssd-pick-color)")
            }
            <div class="card_name fit"><div class="text">${SSD_StageName(state.pick.stage)}</div></div>
          </div>
        `;
      } else {
        pickHtml = `
          <div class="card picked pending" data-key="pick-pending">
            <div class="pending_mark">?</div>
            ${state.turn ? ByChip(state.turn.verb, state.turn.team.name, state.turn.team.color, true) : ""}
            <div class="card_name fit"><div class="text">TBD</div></div>
          </div>
        `;
      }

      SSD_Render(".bans", bansHtml, { y: 24 });
      SSD_Render(".pick", pickHtml, { scale: 1.06 });

      // Variants with body.pick-center put the picked card in the middle,
      // with the first half of the stage cards on its left and the rest on its right
      if ($("body").hasClass("pick-center")) {
        const $stageCards = $(".bans .card");
        const half = Math.ceil($stageCards.length / 2);
        $stageCards.each((i, el) => $(el).addClass(i < half ? "left" : "right"));
      }

      // Blurred picked stage behind the whole panel
      const backdrop = state.pick ? SSD_StageImage(state.pick.stage) : "none";
      if (backdrop !== lastBackdrop) {
        lastBackdrop = backdrop;
        gsap.fromTo(
          ".backdrop",
          { autoAlpha: 0 },
          {
            autoAlpha: state.pick ? 1 : 0,
            duration: 0.6,
            onStart: () => $(".backdrop").css("background-image", backdrop),
          }
        );
      }

      SSD_SetVisible(".ssd_panel", state.hasContent || (showAvailable && state.available.length > 0));
    } catch (e) {
      console.log(e);
    }
  };
});
