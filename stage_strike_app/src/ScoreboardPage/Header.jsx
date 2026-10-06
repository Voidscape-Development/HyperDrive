import {AppBar, Chip, MenuItem, Select, Toolbar, Typography} from "@mui/material";
import {CheckCircleOutline, ErrorOutline, Sync} from "@mui/icons-material";
import i18n from "../i18n/config";
import {useSaveStatus} from "./saveStatus";
import {Box} from "@mui/system";
import {useTheme} from "@mui/material/styles";
import {shallowEqual, useSelector} from "react-redux";
import {BASE_URL} from "../env";
import {GameIcon} from "../GameIcon";


/** Whether the changes made on this page have reached HyperDrive. */
const SaveStatus = () => {
    const status = useSaveStatus();
    if (status === "idle") {
        return null;
    }
    const chip = {
        saving: {icon: <Sync/>, label: i18n.t("saving"), color: "default"},
        saved: {icon: <CheckCircleOutline/>, label: i18n.t("saved"), color: "success"},
        error: {icon: <ErrorOutline/>, label: i18n.t("save_failed"), color: "error"},
    }[status];
    return <Chip size={"small"} variant={"outlined"} {...chip} sx={{ml: 'auto'}}/>;
};

export const Header = ({onSelectedGameChange, ...rest}) => {
    const {hdState, games} = useSelector(state => ({
      hdState: state.hdState.hdState,
      games: state.hdGames.value
    }), shallowEqual);

    const theme = useTheme();

    return (
        <AppBar
          sx={{
              position: 'unset',
              px: '2em',
          }}
          {...rest}
        >
            <Toolbar disableGutters sx={{
                whiteSpace: "nowrap",
                textOverflow: "ellipsis",
                display: 'flex',

                [theme.breakpoints.down('sm')]: {
                    flexDirection: 'column',
                    gap: 1,
                    paddingY: 2,
                },
            }}>

                <Typography
                    variant="h6"
                    gap={2}
                    sx={{
                        display: 'flex',
                        alignItems: "center",
                        mr: 4,
                    }}
                >
                    <img alt="HyperDrive logo" src={`${BASE_URL}/assets/icons/icon.png`} height={48} width={48} sx={{mr: 2}} />
                    Web Scoreboard
                </Typography>

                <Box
                    sx={{
                        display: 'flex',
                        alignItems: 'center',
                        mr: 2
                    }}
                >
                    <span>Game:&nbsp;</span>
                    <Select
                      sx={{
                          '.MuiSelect-select': {
                              paddingY: 0,
                              marginY: 0
                          },
                      }}
                      value={hdState.game.codename}
                      renderValue={(codename) =>
                        <GameIcon game={games[codename]} />
                      }
                      id={"header-game-select"}
                      onChange={(e) => onSelectedGameChange(e.target.value)}
                    >
                        {
                            Object.values(games).map(game =>
                              <MenuItem key={game.codename} value={game.codename}>
                                  <GameIcon fixedWidth={true} game={game} />
                                  <Typography>{game.name}</Typography>
                              </MenuItem>
                            )
                        }
                    </Select>
                </Box>

                <Box sx={{
                    overflowX: "hidden",
                    textOverflow: "ellipsis",
                    maxWidth: '100%',
                }}>
                    <span>Event:&nbsp;</span>
                    <span>{hdState.tournamentInfo.tournamentName}:</span>
                    <span>{hdState.tournamentInfo.eventName}</span>
                </Box>

                <SaveStatus/>
            </Toolbar>
        </AppBar>
    )
}
