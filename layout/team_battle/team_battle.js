// Shared by the Team Battle layouts, which show the Crew/Team Battle window's
// data (team_battle in docs/layout-data.md). Each page sets window.TB_MODE to
// "STOCK_POOL" or "FIRST_TO" before loading this:
// - Stock Pool: a player's number is their stocks left, the team's is the
//   stocks the whole team has left.
// - First To: a player's number is the games they won against the current
//   opponent, the team's is how many of their players are still in.

const TB_FIRST_TO = "FIRST_TO";
const TB_DEFAULT_COLORS = { 1: "#fe3636", 2: "#2e89ff" };

function TBIsStock() {
  return window.TB_MODE !== TB_FIRST_TO;
}

// A path in program_state (./user_data/...) as a src from a layout page
function TBSrc(path) {
  return path ? `../../${String(path).replace(/^\.\//, "")}` : null;
}

function TBEscape(text) {
  return String(text ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function TBFirstCharacter(player) {
  return Object.values(_.get(player, "character", {})).find(
    (c) => c && c.codename && c.assets && Object.keys(c.assets).length > 0,
  );
}

// The character's stock icon (settings.json "stock_icon" picks the asset)
function TBCharacterIcon(character) {
  if (!character) return null;
  const key = ResolveAssetSetting("stock_icon").asset_key || "base_files/icon";
  const asset = GetCharacterAsset(key, character);
  return asset ? TBSrc(asset.asset) : null;
}

function TBAvatar(player) {
  if (player.avatar) return TBSrc(player.avatar);
  return player.online_avatar || null;
}

// A team, with its players in order and the numbers the layouts show
function TBTeam(data, t) {
  const tb = data.team_battle || {};
  const team = _.get(tb, ["team", String(t)], {}) || {};
  const players = Object.entries(team.player || {})
    .filter(([key, p]) => p)
    .sort(([a], [b]) => Number(a) - Number(b))
    .map(([key, p]) => ({
      key,
      data: p,
      path: `team_battle.team.${t}.player.${key}`,
      name: p.name || "",
      sponsor: p.team || "",
      value: Math.max(Number(p.dynamic_spinner) || 0, 0),
      dead: !!p.dead,
      active:
        team.active_player != null
          ? String(team.active_player) === key
          : !!p.active,
      character: TBFirstCharacter(p),
    }));
  // Players can be given more stocks than the others in the app
  const max = Math.max(Number(tb.battle_value) || 0, ...players.map((p) => p.value), 1);
  const alive = players.filter((p) => !p.dead).length;
  const stocks = players.reduce((sum, p) => sum + (p.dead ? 0 : p.value), 0);
  const name = team.sponsor || "";

  return {
    t,
    name,
    displayName: name || `Team ${t}`,
    color: team.color || TB_DEFAULT_COLORS[t],
    logo: TBSrc(team.logo),
    players,
    max,
    alive,
    stocks,
    score: Number(tb[`team${t}_total-score`]) || 0,
    active: players.find((p) => p.active) || null,
    big: TBIsStock() ? stocks : alive,
    bigLabel: TBIsStock() ? "Stocks" : "Left",
  };
}

function TBTeams(data) {
  return [TBTeam(data, 1), TBTeam(data, 2)];
}

// Team colors as --t1-color and --t2-color
function TBApplyColors(teams) {
  const root = document.querySelector(":root");
  for (const team of teams) {
    if (hd_settings.forceDefaultScoreColors) {
      root.style.removeProperty(`--t${team.t}-color`);
    } else {
      root.style.setProperty(`--t${team.t}-color`, team.color);
    }
  }
}

// "Phase - Match", from the Crew/Team Battle window
function TBPhaseMatch(data) {
  const tb = data.team_battle || {};
  return [tb.phase, tb.match].filter(Boolean).map(TBEscape).join(" &middot; ");
}

// What every player starts with, e.g. "3 Stocks each" or "First to 2"
function TBRuleText(teams) {
  const max = Math.max(teams[0].max, teams[1].max);
  if (TBIsStock()) return `${max} ${max == 1 ? "Stock" : "Stocks"} each`;
  return `First to ${max}`;
}

// A pip per stock (Stock Pool, with the character's stock icon) or per game
// to win (First To). Lit: stocks left, or games won.
function TBPipsHtml(player, team) {
  const icon = TBIsStock() ? TBCharacterIcon(player.character) : null;
  let html = "";
  for (let i = 0; i < team.max; i += 1) {
    const lit = i < player.value;
    html += `<span class="pip ${lit ? "lit" : "spent"}${icon ? " icon" : ""}">${
      icon ? `<img src="${icon}" />` : ""
    }</span>`;
  }
  return html;
}

// Sponsor and tag, as HTML for SetInnerHtml
async function TBNameHtml(player) {
  const name = player.name ? await Transcript(TBEscape(player.name)) : "";
  const sponsor = player.sponsor
    ? `<span class="sponsor">${TBEscape(player.sponsor)}</span>`
    : "";
  return `${sponsor}<span class="tag">${name}</span>`;
}

// Flag and pronouns
function TBChipsHtml(player) {
  const p = player.data;
  const chips = [];
  if (p.country && p.country.asset) {
    chips.push(
      `<span class="chip flag"><img class="flagcountry" src="${TBSrc(p.country.asset)}" />${TBEscape(p.country.code || "")}</span>`,
    );
  }
  if (p.pronoun) {
    chips.push(`<span class="chip pronoun">${TBEscape(p.pronoun)}</span>`);
  }
  return chips.join("");
}

// The team's logo, or its initial when there's none
function TBLogoHtml(team) {
  if (team.logo) return `<img class="logo_img" src="${team.logo}" />`;
  const initial = Array.from(team.displayName.trim())[0] || "?";
  return `<span class="logo_initial">${TBEscape(initial)}</span>`;
}

// Sets innerHTML only when it changed, so images don't load again
function TBSetHtml(element, html) {
  if (!element) return false;
  if (element.dataset.tbHtml === html) return false;
  element.dataset.tbHtml = html;
  element.innerHTML = html;
  return true;
}

// ---------------------------------------------------------------------------
// Animations for changes, played on the second update on
// ---------------------------------------------------------------------------

// A number ticking up or down to its new value, with a pop
function TBAnimateNumber(element, value, animate) {
  if (!element) return;
  const old = Number(element.dataset.value);
  element.dataset.value = value;
  if (!animate || isNaN(old) || old === value) {
    element.textContent = value;
    return;
  }
  const counter = { v: old };
  gsap.to(counter, {
    v: value,
    duration: 0.4,
    ease: "power1.out",
    overwrite: true,
    onUpdate: () => (element.textContent = Math.round(counter.v)),
  });
  gsap.fromTo(
    element,
    { scale: 1.45, filter: "brightness(2)" },
    { scale: 1, filter: "brightness(1)", duration: 0.6, ease: "back.out(3)", overwrite: "auto" },
  );
}

// A player's pips, with the ones that changed flashing
function TBUpdatePips(element, player, team, animate) {
  const before = [...element.querySelectorAll(".pip")].map((p) => p.classList.contains("lit"));
  if (!TBSetHtml(element, TBPipsHtml(player, team)) || !animate) return;
  element.querySelectorAll(".pip").forEach((pip, i) => {
    const lit = pip.classList.contains("lit");
    if (i >= before.length || before[i] === lit) return;
    if (lit) {
      gsap.fromTo(pip, { scale: 2, autoAlpha: 0 }, { scale: 1, autoAlpha: 1, duration: 0.45, ease: "back.out(2.5)" });
    } else {
      gsap.fromTo(
        pip,
        { scale: 1.6, filter: "brightness(3)" },
        { scale: 1, filter: "brightness(1)", duration: 0.5, ease: "power2.out" },
      );
    }
  });
}

// Eliminated: the red X slams onto the card and the card shakes
function TBSetEliminated(card, dead, animate) {
  const was = card.classList.contains("dead");
  card.classList.toggle("dead", dead);
  const x = card.querySelector(".x_mark");
  if (!x) return;
  if (!animate || was === dead) {
    gsap.set(x, { autoAlpha: dead ? 1 : 0, scale: 1, rotate: 0 });
    return;
  }
  if (dead) {
    gsap.fromTo(
      x,
      { autoAlpha: 0, scale: 3, rotate: -25 },
      { autoAlpha: 1, scale: 1, rotate: 0, duration: 0.3, ease: "power4.in", overwrite: true },
    );
    gsap.fromTo(
      card,
      { x: 0 },
      { keyframes: { x: [0, -10, 9, -6, 4, 0] }, duration: 0.35, delay: 0.28, ease: "none", clearProps: "x" },
    );
  } else {
    gsap.to(x, { autoAlpha: 0, scale: 0.6, duration: 0.3, ease: "power2.in", overwrite: true });
  }
}

// A light sweeping across an element's .sweep, which stays inside it
function TBSweep(sweep, delay = 0) {
  if (!sweep) return;
  gsap.fromTo(
    sweep,
    { autoAlpha: 1, backgroundPosition: "100% 0" },
    {
      backgroundPosition: "0% 0",
      duration: 0.7,
      delay,
      ease: "power2.inOut",
      overwrite: true,
      onComplete: () => gsap.set(sweep, { autoAlpha: 0 }),
    },
  );
}

// Active: highlighted, with a sweep across the card when it becomes active
function TBSetActive(card, active, animate) {
  const was = card.classList.contains("active");
  card.classList.toggle("active", active);
  if (!animate || was || !active) return;
  TBSweep(card.querySelector(".sweep"));
  gsap.fromTo(card, { scale: 1.06 }, { scale: 1, duration: 0.5, ease: "back.out(2)", clearProps: "scale" });
}

// Character renders of a card, kept up to date by assetUtils.js
function TBCharacterRender(element, player, event, options = {}) {
  CharacterDisplay(
    $(element),
    {
      source: player.path,
      load_settings_path: "render",
      slice_character: [0, 1],
      ...options,
    },
    event,
  );
}
