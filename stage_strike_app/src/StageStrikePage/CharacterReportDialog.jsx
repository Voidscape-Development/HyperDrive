import {useEffect, useMemo, useState} from "react";
import {
  Alert,
  Box,
  Button,
  ButtonBase,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  InputAdornment,
  Paper,
  Snackbar,
  TextField,
  Typography,
  useMediaQuery,
} from "@mui/material";
import {Add, ArrowBack, Close, Search} from "@mui/icons-material";
import {darkTheme} from "../themes";
import i18n from "../i18n/config";
import {ReportCharacters} from "./postActions";
import {CharacterIcon, CharacterName, FindCharacter} from "./characterAssets";

const slotKey = (team, player) => `${team.team}-${player.player}`;

/** Whether any player has fewer characters set than HyperDrive's character count */
export function MissingCharacters(teams, charactersPerPlayer) {
  const count = charactersPerPlayer ?? 1;
  return (teams ?? []).some((team) => (team?.players ?? []).some((player) => {
    for (let i = 0; i < count; i += 1) {
      if (!player.characters?.[i]) return true;
    }
    return false;
  }));
}

function initialSelections(teams, characters, count) {
  const selections = {};
  (teams ?? []).forEach((team) => {
    (team?.players ?? []).forEach((player) => {
      const slots = [];
      for (let i = 0; i < count; i += 1) {
        const current = player.characters?.[i];
        const character = FindCharacter(characters, current);
        slots.push(character ? {en_name: character.en_name, skin: current.skin ?? 0} : null);
      }
      selections[slotKey(team, player)] = slots;
    });
  });
  return selections;
}

function CharacterTile({character, skin, onClick, onClear, label, highlight}) {
  const icon = character ? CharacterIcon(character, skin) : null;
  return <Box className={`ss-char-slot ${character ? "filled" : ""} ${highlight ? "highlight" : ""}`}>
    <ButtonBase className="ss-char-slot-button" onClick={onClick} focusRipple aria-label={label}>
      {icon
        ? <img src={icon} alt="" />
        : <Add className="ss-char-slot-add" />
      }
      <span className="ss-char-slot-name">{character ? CharacterName(character) : label}</span>
    </ButtonBase>
    {character && onClear &&
      <IconButton
        size="small"
        className="ss-char-slot-clear"
        aria-label={i18n.t("clear")}
        onClick={onClear}
      >
        <Close fontSize="inherit" />
      </IconButton>
    }
  </Box>;
}

function CharacterPicker({characters, current, onPick, onPickSkin}) {
  const [search, setSearch] = useState("");
  const list = useMemo(() => Object.values(characters)
    .filter((c) => !search || CharacterName(c).toLowerCase().includes(search.toLowerCase())
      || c.en_name.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => CharacterName(a).localeCompare(CharacterName(b))), [characters, search]);

  const currentCharacter = current ? characters[current.en_name] : null;
  const skins = currentCharacter?.skins ?? [];

  return <Box className="ss-picker">
    {currentCharacter && skins.length > 1 &&
      <Box className="ss-picker-skins">
        <Typography variant="overline" color="text.secondary">
          {i18n.t("color")} · {CharacterName(currentCharacter)}
        </Typography>
        <Box className="ss-picker-skin-row">
          {skins.map((_, i) =>
            <ButtonBase
              key={i}
              className={`ss-picker-skin ${current.skin === i ? "selected" : ""}`}
              onClick={() => onPickSkin(i)}
              aria-label={`${i18n.t("color")} ${i + 1}`}
            >
              <img src={CharacterIcon(currentCharacter, i)} alt="" />
            </ButtonBase>
          )}
        </Box>
      </Box>
    }
    <TextField
      autoFocus
      fullWidth
      size="small"
      placeholder={i18n.t("search")}
      value={search}
      onChange={(e) => setSearch(e.target.value)}
      slotProps={{input: {startAdornment: <InputAdornment position="start"><Search /></InputAdornment>}}}
    />
    <Box className="ss-picker-grid">
      {list.map((c) =>
        <ButtonBase
          key={c.en_name}
          className={`ss-picker-char ${current?.en_name === c.en_name ? "selected" : ""}`}
          onClick={() => onPick(c)}
          focusRipple
        >
          <img src={CharacterIcon(c, 0)} alt="" loading="lazy" />
          <span>{CharacterName(c)}</span>
        </ButtonBase>
      )}
    </Box>
  </Box>;
}

export function CharacterReportDialog({
  open,
  onClose,
  target,
  myPlayer,
  characterSelect,
  game,
  teams,
  charactersPerPlayer,
  playerNames,
  characters,
  // Shown in the page instead of a dialog (the character select page)
  inline = false,
  // Sends the picks: (target, {team: {player: [[character, skin]]}}) => Response
  report = ReportCharacters,
  title,
  // Called after the picks were sent
  onSent,
}) {
  if (inline) open = true;
  const fullScreen = useMediaQuery(darkTheme.breakpoints.down("sm"));
  const count = Math.max(1, charactersPerPlayer ?? 1);
  const [selections, setSelections] = useState({});
  const [edited, setEdited] = useState(false);
  const [picking, setPicking] = useState(null);
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState(null);

  // Follows HyperDrive until something is changed here
  useEffect(() => {
    if (open && !edited) {
      setSelections(initialSelections(teams, characters, count));
    }
  }, [open, edited, teams, characters, count]);

  useEffect(() => {
    if (!open) {
      setEdited(false);
      setPicking(null);
    }
  }, [open]);

  const setSlot = (key, slot, value) => {
    setEdited(true);
    setSelections((prev) => {
      const slots = [...(prev[key] ?? Array(count).fill(null))];
      slots[slot] = value;
      return {...prev, [key]: slots};
    });
  };

  // A page for one team only sees and sends its own team's characters
  const teamMode = myPlayer !== undefined && myPlayer !== -1;
  const visibleTeams = (teams ?? []).map((team, t) =>
    (!teamMode || t === myPlayer) ? team : null);
  const players = visibleTeams.flatMap((team, t) =>
    (team?.players ?? []).map((player) => ({team, player, t})));
  const complete = players.length > 0 && players.every(({team, player}) =>
    (selections[slotKey(team, player)] ?? []).slice(0, count).every((s) => !!s)
    && (selections[slotKey(team, player)] ?? []).length >= count);

  const selectActive = !!characterSelect?.active;
  const mySubmitted = teamMode && selectActive
    && !!characterSelect.submitted?.[String(teams?.[myPlayer]?.team)];
  const otherTeam = teamMode ? teams?.[(myPlayer + 1) % 2] : null;
  const otherName = otherTeam ? (otherTeam.name || playerNames[(myPlayer + 1) % 2]) : null;

  const send = async (keepCurrent) => {
    // Keeping the characters sends what the scoreboard has
    const source = keepCurrent ? initialSelections(teams, characters, count) : selections;
    const payload = {};
    players.forEach(({team, player}) => {
      payload[String(team.team)] ??= {};
      payload[String(team.team)][String(player.player)] = (source[slotKey(team, player)] ?? [])
        .slice(0, count)
        .filter((s) => !!s)
        .map((s) => [s.en_name, s.skin]);
    });

    setSending(true);
    try {
      const response = await report(target, payload);
      if (response.ok) {
        // The other team's characters are still missing
        const waiting = teamMode && !characterSelect?.submitted?.[String(otherTeam?.team)];
        setResult(waiting ? "waiting" : "success");
        setEdited(false);
        onSent?.();
        onClose?.();
      } else if (response.status === 409) {
        // Already picked for this score (character select page)
        setResult("locked");
      } else {
        setResult("error");
      }
    } catch (e) {
      console.error(e);
      setResult("error");
    } finally {
      setSending(false);
    }
  };

  let content;
  if (picking) {
    const current = selections[picking.key]?.[picking.slot] ?? null;
    content = <CharacterPicker
      characters={characters}
      current={current}
      onPick={(c) => {
        const skin = current?.en_name === c.en_name ? current.skin : 0;
        setSlot(picking.key, picking.slot, {en_name: c.en_name, skin});
        // Characters with colors stay open to pick one
        if ((c.skins ?? []).length <= 1) setPicking(null);
      }}
      onPickSkin={(skin) => {
        setSlot(picking.key, picking.slot, {...current, skin});
        setPicking(null);
      }}
    />;
  } else if (players.length === 0 || Object.keys(characters).length === 0) {
    content = <Typography color="text.secondary">{i18n.t("no_players")}</Typography>;
  } else {
    content = <Box className="ss-report">
      {mySubmitted &&
        <Alert severity="success" className="ss-report-alert">
          {i18n.t("characters_waiting", {team: otherName})}
        </Alert>
      }
      <Typography color="text.secondary" className="ss-report-hint">
        {i18n.t(teamMode ? "select_characters_hint_team" : "select_characters_hint", {count})}
      </Typography>
      <Box className="ss-report-teams">
        {visibleTeams.map((team, t) => team &&
          <Box key={t} className={`ss-report-team p${t + 1}`}>
            <Typography className="ss-report-team-name" noWrap>
              {team.name || playerNames[t]}
            </Typography>
            {(team.players ?? []).map((player) => {
              const key = slotKey(team, player);
              return <Box key={key} className="ss-report-player">
                {(team.players.length > 1 || team.name) &&
                  <Typography className="ss-report-player-name" noWrap>
                    {player.name || i18n.t("player_n", {value: player.player})}
                  </Typography>
                }
                <Box className="ss-report-slots">
                  {Array.from({length: count}).map((_, slot) => {
                    const selection = selections[key]?.[slot];
                    const character = selection ? characters[selection.en_name] : null;
                    return <CharacterTile
                      key={slot}
                      character={character}
                      skin={selection?.skin ?? 0}
                      label={count > 1 ? i18n.t("character_n", {value: slot + 1}) : i18n.t("character")}
                      highlight={!character}
                      onClick={() => setPicking({key, slot, name: player.name})}
                      onClear={() => setSlot(key, slot, null)}
                    />;
                  })}
                </Box>
              </Box>;
            })}
          </Box>
        )}
      </Box>
    </Box>;
  }

  const titleText = picking
    ? `${i18n.t("pick_character")}${picking.name ? ` · ${picking.name}` : ""}`
    : title ?? (selectActive
      ? i18n.t("characters_for_game", {value: (characterSelect.game ?? 0) + 1})
      : i18n.t("report_characters"));

  const sendButtons = <>
    <Button
      variant="outlined"
      disabled={sending || !game || players.length === 0}
      onClick={() => send(true)}
    >
      {i18n.t("keep_characters")}
    </Button>
    <Button
      variant="contained"
      color="success"
      disabled={!complete || sending || !game}
      onClick={() => send(false)}
    >
      {i18n.t("send_to_hd")}
    </Button>
  </>;

  const snackbar = <Snackbar
    open={!!result}
    autoHideDuration={3000}
    onClose={() => setResult(null)}
    anchorOrigin={{vertical: "top", horizontal: "center"}}
  >
    <Alert
      severity={result === "error" ? "error" : result === "locked" ? "warning" : "success"}
      variant="filled"
      onClose={() => setResult(null)}
    >
      {result === "waiting"
        ? i18n.t("characters_waiting", {team: otherName})
        : result === "locked"
          ? i18n.t("characters_locked_short")
          : i18n.t(result === "error" ? "characters_failed" : "characters_sent")}
    </Alert>
  </Snackbar>;

  if (inline) {
    return <>
      <Paper className="ss-dialog ss-inline-select" elevation={4}>
        <Box className="ss-dialog-title ss-inline-select-title">
          {picking &&
            <IconButton aria-label={i18n.t("back")} onClick={() => setPicking(null)} edge="start">
              <ArrowBack />
            </IconButton>
          }
          <Typography className="ss-dialog-title-text" variant="h6" component="h2">{titleText}</Typography>
        </Box>
        <Box className="ss-inline-select-content">
          {content}
        </Box>
        <Box className="ss-inline-select-actions">
          {picking
            ? <Button onClick={() => setPicking(null)}>{i18n.t("done")}</Button>
            : sendButtons
          }
        </Box>
      </Paper>
      {snackbar}
    </>;
  }

  return <>
    <Dialog
      open={open}
      onClose={onClose}
      fullScreen={fullScreen}
      fullWidth
      maxWidth="md"
      PaperProps={{className: "ss-dialog"}}
    >
      <DialogTitle className="ss-dialog-title">
        {picking &&
          <IconButton aria-label={i18n.t("back")} onClick={() => setPicking(null)} edge="start">
            <ArrowBack />
          </IconButton>
        }
        <span className="ss-dialog-title-text">
          {titleText}
        </span>
        <IconButton aria-label={i18n.t("close")} onClick={onClose} edge="end">
          <Close />
        </IconButton>
      </DialogTitle>
      <DialogContent dividers>
        {content}
      </DialogContent>
      <DialogActions>
        {picking
          ? <Button onClick={() => setPicking(null)}>{i18n.t("done")}</Button>
          : <>
            <Button onClick={onClose}>{i18n.t("cancel")}</Button>
            {sendButtons}
          </>
        }
      </DialogActions>
    </Dialog>
    {snackbar}
  </>;
}
