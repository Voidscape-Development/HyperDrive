import {useState} from "react";
import {
  Box,
  Chip,
  FormControlLabel,
  IconButton,
  Menu,
  MenuItem,
  Select,
  Switch,
  Tooltip,
  Typography,
} from "@mui/material";
import {Settings, SportsEsports} from "@mui/icons-material";
import i18n from "../i18n/config";
import {LanguageSelector} from "./LanguageSelector";

export function TopBar({
  scoreboard,
  scoreboards,
  onScoreboardChange,
  teamName,
  teamPlayer,
  connected,
  playerLanguages,
  currPlayer,
  selectedStage,
  uiSettings,
  onUiSettingsChange,
  // The page's name, "Stage Strike" by default
  title,
}) {
  const [menuAnchor, setMenuAnchor] = useState(null);

  // Keeps the current scoreboard listed while the list loads
  const options = scoreboards.length > 0
    ? scoreboards
    : [{number: scoreboard, name: i18n.t("scoreboard_n", {value: scoreboard})}];

  return <Box className="ss-topbar">
    <Box className="ss-topbar-left">
      <SportsEsports className="ss-logo" />
      <Typography variant="h6" component="h1" className="ss-title" noWrap>
        {title ?? i18n.t("title")}
      </Typography>
      <Tooltip title={connected ? i18n.t("connected") : i18n.t("connecting")}>
        <span className={`ss-connection ${connected ? "on" : "off"}`} />
      </Tooltip>
    </Box>

    {teamName &&
      <Chip
        className={`ss-team-chip p${teamPlayer + 1}`}
        label={i18n.t("team_view", {team: teamName})}
        size="small"
      />
    }

    <Select
      value={options.some((s) => s.number === scoreboard) ? scoreboard : ""}
      onChange={(e) => onScoreboardChange(Number(e.target.value))}
      size="small"
      className="ss-scoreboard-select"
      inputProps={{"aria-label": i18n.t("scoreboard")}}
    >
      {options.map((s) =>
        <MenuItem key={s.number} value={s.number}>{s.name}</MenuItem>
      )}
    </Select>

    <Box className="ss-topbar-right">
      <Box sx={{display: {xs: "none", sm: "block"}}}>
        <LanguageSelector
          playerLanguages={playerLanguages}
          currPlayer={currPlayer}
          selectedStage={selectedStage}
        />
      </Box>
      <IconButton
        aria-label={i18n.t("settings")}
        onClick={(e) => setMenuAnchor(e.currentTarget)}
      >
        <Settings />
      </IconButton>
      <Menu
        anchorEl={menuAnchor}
        open={!!menuAnchor}
        onClose={() => setMenuAnchor(null)}
      >
        <Box sx={{display: {xs: "block", sm: "none"}, px: 2, py: 1}}>
          <LanguageSelector
            playerLanguages={playerLanguages}
            currPlayer={currPlayer}
            selectedStage={selectedStage}
          />
        </Box>
        {uiSettings &&
          <MenuItem disableRipple>
            <FormControlLabel
              control={<Switch
                checked={uiSettings.askCharacters}
                onChange={(e) => onUiSettingsChange({askCharacters: e.target.checked})}
              />}
              label={i18n.t("auto_ask_characters")}
            />
          </MenuItem>
        }
      </Menu>
    </Box>
  </Box>;
}
