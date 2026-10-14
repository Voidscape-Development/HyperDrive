// Character art: s.characters(target, options) shows the characters of a
// team or player in the target, each image zoomed and centered on the
// character's eyesight, and fades them over when they change.
"use strict";

(() => {
  // The biggest asset a character has
  function biggestAsset(character) {
    let best = null;
    let bestSize = -1;
    for (const asset of Object.values(character.assets || {})) {
      const size = asset.average_size ? asset.average_size.x + asset.average_size.y : 0;
      if (best === null || size > bestSize) {
        best = asset;
        bestSize = size;
      }
    }
    return best;
  }

  // The asset under key (or the first of a list of keys it has), else the
  // biggest one
  HD.characterAsset = (character, key) => {
    for (const k of [].concat(key || [])) {
      if (Object.prototype.hasOwnProperty.call(character.assets, k)) return character.assets[k];
    }
    return biggestAsset(character);
  };

  // More zoom for uncropped (full body) art, for some focus on the face
  function recommendedZoom(asset, width, height) {
    const edge = asset.uncropped_edge || "";
    const has = (c) => edge.includes(c);
    if (has("u") && has("d") && has("l") && has("r")) return 1.2;
    if (has("l") !== has("r") && width > height) return width / height;
    if (has("u") !== has("d") && height > width) return height / width;
    return 1;
  }

  // Positions (0-1) for several characters in one container without
  // dividers: around the center, alternating sides
  function multicharacterPositions(count, center = [0.5, 0.5], radius = 0.3) {
    if (count === 1) radius = 0;
    const rad = (deg) => (deg * Math.PI) / 180;
    const start = rad(count === 2 ? 45 : 90);
    const positions = [];
    let pendulum = 1;
    for (let i = 0; i < count; i += 1) {
      let j = i;
      if (i > 1) {
        pendulum = i % 2 === 0 ? -pendulum : -pendulum + 1;
        j = pendulum;
      }
      const angle = start + rad(360 / count) * j;
      positions.push([center[0] + Math.cos(angle) * radius, center[1] + Math.sin(angle) * radius]);
    }
    return positions;
  }

  // settings.json's asset settings for the game being played: assets.default
  // under assets.<game codename> (or under another key, with
  // load_settings_path)
  function assetSettings(key, data) {
    const game = _.get(data, "game.codename", "default");
    const settings = HD.settings;
    return _.defaultsDeep({}, _.get(settings, [key, game], {}), _.get(settings, [key, "default"], {}));
  }
  HD.assetSettings = (key, data = HD.state()) => assetSettings(key, data);

  // The characters to show from a team or a player, by player
  function charactersAt(state, source, options) {
    const at = _.get(state, source);
    const players = at && at.player ? Object.values(at.player) : [at || {}];
    const [from, to] = options.slice_character || [0, Infinity];
    return players.map((p) =>
      Object.values(_.get(p, "character", {}))
        .filter((c) => c && Object.values(c.assets || {}).length > 0)
        .slice(from, to),
    );
  }

  // options: { source (path of the team or player), asset_key, custom_zoom,
  // custom_center, use_dividers, scale_based_on_parent, scale_fill_x/y,
  // flip_x, slice_character ([from, to] of each player's), load_settings_path, in, out }
  // and settings.json's asset settings for the game under them
  HD.characters = async (target, options, s) => {
    const el = $(target);
    const element = el.get(0);
    if (!element) return;

    let settings = assetSettings(options.load_settings_path || "assets", s.data);
    if (options.load_settings_path) settings = _.defaultsDeep(settings, assetSettings("assets", s.data));
    settings = _.defaultsDeep({}, options, settings);

    const characters = charactersAt(s.data, settings.source, settings);
    const first = !el.hasClass("hd_character_container_active");
    if (!first && _.isEqual(characters, charactersAt(s.old, settings.source, settings))) return;
    el.addClass("hd_character_container hd_character_container_active");

    const animIn = { autoAlpha: 1, duration: 0.5, stagger: 0.1, ...settings.in };
    const animOut = { autoAlpha: 0, duration: 0.5, stagger: 0.1, ...settings.out, overwrite: true };

    const show = async () => {
      el.html("");
      // Each with the number of characters its player has, minus its index
      // overall, as z-index: earlier ones on top
      const all = characters.flatMap((list) =>
        list.filter((c) => c.codename).map((character) => ({ character, count: list.length })),
      );
      const loads = all.map(({ character, count }, index) => {
        const div = $("<div class='hd_character' style='opacity: 0;'><div class='hd_character_img'></div></div>");
        el.append(div);
        const options = { ...settings, z_index: count - index };
        if (settings.use_dividers === false) {
          options.custom_center = multicharacterPositions(all.length, settings.custom_center)[index];
        }
        const asset = settings.asset_key ? HD.characterAsset(character, settings.asset_key) : biggestAsset(character);
        if (!options.custom_zoom) options.custom_zoom = recommendedZoom(asset, el.width(), el.height());
        if (settings.flip_x) div.find(".hd_character_img").css("transform", "scaleX(-1)");
        return asset.asset.endsWith(".webm")
          ? centerVideo(div.children(".hd_character_img"), asset)
          : HD.centerImage(div.children(".hd_character_img"), asset, options);
      });
      await Promise.allSettled(loads);

      const shown = el.children(".hd_character");
      if (shown.length === 0) return;
      if (document.hidden) {
        gsap.killTweensOf(shown);
        shown.css({ opacity: 1, visibility: "inherit" });
      } else {
        gsap.fromTo(shown, animOut, animIn);
      }
    };

    const old = el.children(".hd_character");
    if (first || document.hidden || old.length === 0) {
      gsap.killTweensOf(old);
      await show();
    } else {
      // Fade out, then change them and fade in
      await gsap.fromTo(old, animIn, { ...animOut, onComplete: show });
    }
  };

  // Character options that slide them 20px toward the middle as they fade,
  // one after the other: way 1 for the left side, -1 for the right
  HD.slideToMiddle = (way) => ({
    out: { autoAlpha: 0, x: `${-20 * way}px`, stagger: way * 0.2, duration: 0.4 },
    in: { autoAlpha: 1, x: "0px", stagger: way * 0.2, duration: 0.4 },
  });

  // -------------------------------------------------------------------
  // Images zoomed and centered on the character's eyesight, done again
  // when their element is resized

  const resizeObserver = new ResizeObserver((entries) => {
    for (const entry of entries) centerImage($(entry.target));
  });

  // options: { custom_zoom, custom_center, scale_based_on_parent,
  // scale_fill_x, scale_fill_y, use_dividers, z_index }
  HD.centerImage = async (element, asset, options = {}) => {
    if (!asset) return;
    const el = $(element);
    el.data({
      custom_zoom: 1,
      custom_center: [0.5, 0.5],
      scale_based_on_parent: false,
      scale_fill_x: false,
      scale_fill_y: false,
      ...options,
      asset_data: asset,
    });
    await centerImage(el);
    if (!el.hasClass("hd-center-image")) {
      el.addClass("hd-center-image");
      resizeObserver.observe(el.get(0));
    }
  };

  function centerImage(el) {
    const o = el.data();
    const asset = o.asset_data;
    if (!asset) return Promise.resolve();
    const container = o.scale_based_on_parent ? el.parent().parent() : el;

    return new Promise((resolve) => {
      const img = new Image();
      // A missing file would otherwise leave the caller waiting forever
      img.onerror = () => resolve();
      img.onload = () => {
        // Another asset was set while this one loaded
        if (el.data("asset_data") !== asset) return resolve();

        const w = container.innerWidth();
        const h = container.innerHeight();
        const nw = img.naturalWidth;
        const nh = img.naturalHeight;
        const eyesight = asset.eyesight || { x: nw / 2, y: nh / 2 };
        const edge = asset.uncropped_edge && asset.uncropped_edge !== "undefined" ? asset.uncropped_edge : "";
        const has = (c) => edge.includes(c);
        const rescale = asset.rescaling_factor || 1;

        const proportional = asset.average_size
          ? Math.max((w / asset.average_size.x) * 1.2, (h / asset.average_size.y) * 1.2)
          : 1;
        // Cropped art fills the container
        const zoomX = w / nw;
        const zoomY = h / nh;

        let minZoom;
        if (!edge) minZoom = Math.max(zoomX, zoomY) * rescale;
        else if (has("u") && has("d") && has("l") && has("r")) minZoom = o.custom_zoom * proportional * rescale;
        else if (!has("l") && !has("r")) minZoom = zoomX * rescale;
        else if (!has("u") && !has("d")) minZoom = zoomY * rescale;
        else minZoom = o.custom_zoom * proportional * rescale;

        if (o.scale_fill_x && o.scale_fill_y) minZoom = Math.max(zoomX, zoomY);
        else if (o.scale_fill_x) minZoom = zoomX;
        else if (o.scale_fill_y) minZoom = zoomY;

        const zoom = Math.max(minZoom, o.custom_zoom * minZoom);
        const center = o.custom_center || [0.5, 0.5];

        // Centered on the eyesight, without showing past a cropped edge
        // (or more than 10% past an uncropped one)
        const place = (eye, size, natural, space, low, high) => {
          let pos = -eye * zoom + size * center[low === "l" ? 0 : 1];
          const max = size - natural * zoom;
          pos = Math.min(pos, has(low) ? space * 0.1 : 0);
          return Math.max(pos, has(high) ? max - space * 0.1 : max);
        };
        const x = place(eyesight.x, el.innerWidth(), nw, w, "l", "r");
        const y = place(eyesight.y, el.innerHeight(), nh, h, "u", "d");

        if (o.use_dividers === false) el.parent().css("position", "absolute");
        el.parent().css("z-index", o.z_index || 0);
        el.css({ position: "relative" });
        el.find("img.hd-img").remove();
        // The image already loaded, rather than a new one for the same src
        el.append(
          $(img)
            .addClass("hd-img")
            .css({
              position: "absolute",
              left: `${x}px`,
              top: `${y}px`,
              width: `${nw * zoom}px`,
              height: `${nh * zoom}px`,
            }),
        );
        resolve();
      };
      img.src = HD.asset(asset.asset);
    });
  }

  // A video asset (.webm), muted, in place of the image
  function centerVideo(el, asset) {
    return new Promise((resolve) => {
      const video = $("<video />", { src: HD.asset(asset.asset), autoplay: true });
      video[0].muted = true; // Autoplay needs the property
      video.css({ height: "100%", "min-width": 0, "min-height": 0, position: "absolute" });
      el.replaceWith(video);
      // Resolves even if the video can't load or play
      video.on("error", () => resolve());
      video.on("loadedmetadata", () => video[0].play().catch(console.log).finally(resolve));
      video[0].load();
    });
  }
})();
