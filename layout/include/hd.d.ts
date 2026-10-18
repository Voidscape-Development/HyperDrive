// Editor types for the layout runtime (globals.js, render.js,
// characters.js). Not loaded by pages: layout/jsconfig.json points editors
// here, so layout scripts get completion and checks without a build step.

declare const HD: HD.Runtime;
declare const VS: any;

declare namespace HD {
  /** Program state, as HyperDrive sends it (see docs/layout-data.md) */
  type State = Record<string, any>;
  type Target = string | JQuery | HTMLElement;

  /** HTML from HD.html / HD.raw: inserted as is, everything else is text */
  interface Html {
    toString(): string;
  }
  /** What HD.set / HD.render take: text, Html, or lists of them. null, undefined and false are nothing. */
  type Content = Html | string | number | boolean | null | undefined | Content[];

  interface SetOptions {
    duration?: number;
    /** GSAP vars for the new content coming in */
    in?: gsap.TweenVars;
    /** GSAP vars for the old content going out */
    out?: gsap.TweenVars;
    /** Runs once the new content is in */
    after?: () => void;
    /** Swap even if unchanged */
    force?: boolean;
  }

  /** One side of the scoreboard (.p1 / .p2) */
  interface TeamView {
    n: 1 | 2;
    team: Record<string, any>;
    players: Record<string, any>[];
    player: Record<string, any>;
    name: string;
    /** "& .x" or ".x" → ".p1 .x"; "&.x" → ".p1.x" */
    sel(selector?: string): string;
    set(selector: string, content: Content, options?: SetOptions): Promise<void>;
  }

  /** What update(), intro(), start() and outro() get */
  interface Scope {
    data: State;
    /** The state the previous update() ran with ({} the first time) */
    old: State;
    first: boolean;
    /** Scoreboard number (?scoreboardNumber=, default 1) */
    n: number;
    score: Record<string, any>;
    settings: Record<string, any>;
    teams: [TeamView, TeamView];
    isTeams: boolean;
    /** A lodash path ("score.1.team") or a function of the state */
    changed(path: string | (string | number)[] | ((data: State) => any)): boolean;
    /** changed(), inside this scoreboard ("team.1.color") */
    scoreChanged(path: string | (string | number)[] | ((score: any) => any)): boolean;
    set(target: Target, content: Content, options?: SetOptions): Promise<void>;
    /** Work the first show waits for */
    wait<T>(promise: Promise<T>): Promise<T>;
    characters(target: Target, options?: CharacterOptions): Promise<void>;
  }

  interface CharacterOptions {
    /** State path of the team or player, e.g. ["score", 1, "team", 1] */
    source?: string | (string | number)[];
    asset_key?: string;
    custom_zoom?: number;
    custom_center?: [number, number];
    use_dividers?: boolean;
    scale_based_on_parent?: boolean;
    scale_fill_x?: boolean;
    scale_fill_y?: boolean;
    flip_x?: boolean;
    /** [from, to] of each player's characters */
    slice_character?: [number, number];
    /** settings.json section for this game's asset settings */
    load_settings_path?: string;
    in?: gsap.TweenVars;
    out?: gsap.TweenVars;
  }

  /** A theme field a setting follows: [section, field, default, convert?] */
  type ThemeField = [string, string, any, ((value: any) => any)?];

  interface Layout {
    /** Defaults, under settings.json, the theme and page options */
    settings?: Record<string, any>;
    /** The state's top-level keys the layout reads ("score", "game"...): only those are sent. Without it, everything. */
    subscribe?: string[];
    /** Setting path → theme field; only non-default theme values apply */
    theme?: Record<string, ThemeField>;
    /** GSAP plugins from include/gsap/ to load and register ("SplitText", "Flip"...), in order */
    plugins?: string[];
    /** Once, after the settings load, before the first state */
    init?(settings: Record<string, any>): void | Promise<void>;
    /** Each state (coalesced: one at a time, with the latest) */
    update?(s: Scope): void | Promise<void>;
    /** Builds the show animation; played backwards to hide unless outro is set */
    intro?(tl: gsap.core.Timeline, s: Scope): void;
    outro?(s: Scope): void | Promise<void>;
    /** After the intro is built, each show */
    start?(s: Scope): void | Promise<void>;
  }

  interface Runtime {
    layout(layout: Layout): Promise<void>;
    /** Page options for pages sharing a script; win over every setting */
    page(options: Record<string, any>): Record<string, any>;
    /** Shared layouts from include/ (scoreboard, versus, top8...) */
    layouts: Record<string, any>;
    settings: Record<string, any>;
    state(): State;
    scope(): Scope;
    scoreboardNumber(): number;
    theme(section: string, field: string, fallback?: any): any;
    shown(): boolean;
    restart(): Promise<void> | undefined;
    every(seconds: number, fn: (s: Scope) => void): number;
    turns(seconds: number, render: (s: Scope) => void): { pick<T>(items: T[]): T | "" };
    applyDeltas(state: State, deltas: { path: (string | number)[]; action: string; value?: any }[]): State;

    // render.js
    escape(text: unknown): string;
    html(strings: TemplateStringsArray, ...values: Content[]): Html;
    raw(html: string | null | undefined): Html;
    join(items: Content[], separator?: Content): Html;
    set(target: Target, content: Content, options?: SetOptions): Promise<void>;
    render(target: Target, content: Content): JQuery;
    build(target: Target, key: any, content: Content | (() => Content)): boolean;
    img(src: string | null | undefined, attrs?: string): Html | "" | null | undefined;
    fit(target: JQuery): Promise<void>;
    asset(path: string | null | undefined): string;
    players(team: any): Record<string, any>[];
    playerNames(team: any, separator?: string): string;
    teamName(team: any): string;
    text(parts: unknown[], separator?: string): string;
    ordinal(n: number): string;
    stage(data: State, score: any): { name: string; path: string; [k: string]: any } | null;
    custom(person: any, key: string, fallback?: any): any;
    customFile(person: any, key: string, fallback?: any): any;
    ui: {
      flag(place: any, codeClass?: string): Html | undefined;
      chip(kind: string, text: Content, prefix?: Content, icon?: string): Html | "";
      name(player: any, team?: any): Html;
      sponsorLogo(path: string): Html;
      variant(variant: any): Html | "";
    };
    classIntro(tl: gsap.core.Timeline, options?: { duration?: number; distance?: number; each?: number }): void;
    commentators(
      s: Scope,
      container: string,
      fields?: string[],
      show?: Record<string, (commentator: any) => Content>,
    ): void;
    teamColors(s: Scope, props?: string[]): void;

    // characters.js
    characters(target: Target, options: CharacterOptions, s: Scope): Promise<void>;
    characterAsset(character: any, key: string): any;
    assetSettings(key: string, data?: State): Record<string, any>;
    slideToMiddle(way: 1 | -1): { in: gsap.TweenVars; out: gsap.TweenVars };
    centerImage(element: Target, asset: any, options?: Record<string, any>): Promise<void>;
  }
}

// Libraries globals.js loads
declare const $: any;
type JQuery = any;
declare const _: any;
declare const gsap: any;
declare namespace gsap {
  type TweenVars = Record<string, any>;
  namespace core {
    type Timeline = any;
  }
}
declare const ColorThief: any;
declare const io: any;
declare const L: any;
