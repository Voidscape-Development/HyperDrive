import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import StageStrikePage from "./StageStrikePage";
import CharacterSelectPage from "./CharacterSelectPage";
import BracketFocusPage from "./BracketFocusPage";
import CommentaryDashboardPage from "./CommentaryDashboardPage";

import {BrowserRouter, Navigate, Route, Routes} from "react-router-dom";
import ScoreboardPage from "./ScoreboardPage";
import {Provider} from "react-redux";
import {hdStore} from "./redux/store";
import {TooltipProvider} from "@/components/ui/tooltip";
import {Toaster} from "@/components/ui/sonner";

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <Provider store={hdStore}>
      <TooltipProvider delayDuration={300}>
        <BrowserRouter>
          <Routes>
            <Route path="/stage-strike-app" element={<StageStrikePage />} />
            <Route path="/character-select" element={<CharacterSelectPage />} />
            <Route path="/scoreboard" element={<ScoreboardPage />} />
            <Route path="/bracket-focus-app" element={<BracketFocusPage />} />
            <Route path="/commentary-dashboard" element={<CommentaryDashboardPage />} />
            <Route path="*" element={<Navigate to={"/stage-strike-app"} replace={true} />} />
          </Routes>
        </BrowserRouter>
        <Toaster position="top-center" />
      </TooltipProvider>
    </Provider>
  </React.StrictMode>
);
