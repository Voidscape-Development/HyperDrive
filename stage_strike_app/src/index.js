import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import StageStrikePage from './StageStrikePage';
import CharacterSelectPage from './CharacterSelectPage';
import BracketFocusPage from './BracketFocusPage';

import {BrowserRouter, Navigate, Route, Routes} from "react-router-dom";
import ScoreboardPage from "./ScoreboardPage";
import {darkTheme} from "./themes";
import {ThemeProvider} from "@mui/material/styles";
import {CssBaseline} from "@mui/material";
import {tshStore} from "./redux/store";
import {Provider} from "react-redux";

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
      <ThemeProvider theme={darkTheme}>
          <CssBaseline />
          <Provider store={tshStore}>
              <BrowserRouter>
                  <Routes>
                      <Route
                          path="/stage-strike-app"
                          element={<StageStrikePage />}
                      />
                      <Route
                          path="/character-select"
                          element={<CharacterSelectPage />}
                      />
                      <Route
                          path="/scoreboard"
                          element={<ScoreboardPage />}
                      />
                      <Route
                          path="/bracket-focus-app"
                          element={<BracketFocusPage />}
                      />
                      <Route
                          path="*"
                          element={<Navigate to={"/stage-strike-app"} replace={true}/>}
                      />
                  </Routes>
              </BrowserRouter>
          </Provider>
      </ThemeProvider>
  </React.StrictMode>
);
