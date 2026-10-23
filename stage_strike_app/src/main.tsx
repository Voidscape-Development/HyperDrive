import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import StageStrikePage from "./StageStrikePage";
import CharacterSelectPage from "./CharacterSelectPage";
import BracketFocusPage from "./BracketFocusPage";
import CommentaryDashboardPage from "./CommentaryDashboardPage";

import {BrowserRouter, Navigate, Route, Routes} from "react-router-dom";
import ScoreboardPage, {ScoreboardSection} from "./ScoreboardPage";
import {Provider} from "react-redux";
import {hdStore} from "./redux/store";
import {TooltipProvider} from "@/components/ui/tooltip";
import {Toaster} from "@/components/ui/sonner";
import DashboardLayout from "./Dashboard/Layout";
import Overview from "./Dashboard/Overview";
import {PinGate} from "./Dashboard/PinGate";
import BracketPage from "./Dashboard/BracketPage";
import CommentaryPage from "./Dashboard/CommentaryPage";
import DisplayControlsPage from "./Dashboard/DisplayControlsPage";
import PlayerListPage from "./Dashboard/PlayerListPage";
import StreamQueuePage from "./Dashboard/StreamQueuePage";
import TeamBattlePage from "./Dashboard/TeamBattlePage";
import TournamentInfoPage from "./Dashboard/TournamentInfoPage";
import {AdminSection, AdminStandalone, ApprovalSection, ApprovalStandalone, StationPage, StationSection} from "./Reporting";

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <Provider store={hdStore}>
      <TooltipProvider delayDuration={300}>
        <BrowserRouter>
          <Routes>
            {/* The dashboard, behind its PIN when there is one */}
            <Route element={<PinGate><DashboardLayout /></PinGate>}>
              <Route path="/" element={<Overview />} />
              <Route path="/dashboard/scoreboard" element={<ScoreboardSection />} />
              <Route path="/dashboard/stage-strike" element={<StageStrikePage />} />
              <Route path="/dashboard/character-select" element={<CharacterSelectPage />} />
              <Route path="/dashboard/bracket-focus" element={<BracketFocusPage />} />
              <Route path="/dashboard/commentary" element={<CommentaryPage />} />
              <Route path="/dashboard/display-controls" element={<DisplayControlsPage />} />
              <Route path="/dashboard/team-battle" element={<TeamBattlePage />} />
              <Route path="/dashboard/stream-queue" element={<StreamQueuePage />} />
              <Route path="/dashboard/bracket" element={<BracketPage />} />
              <Route path="/dashboard/player-list" element={<PlayerListPage />} />
              <Route path="/dashboard/tournament-info" element={<TournamentInfoPage />} />
              <Route path="/dashboard/reporting" element={<AdminSection />} />
              <Route path="/dashboard/reporting-approval" element={<ApprovalSection />} />
              <Route path="/dashboard/player-reporting" element={<StationSection />} />
            </Route>

            {/* The pages on their own, as before, for players and commentators */}
            <Route path="/stage-strike-app" element={<StageStrikePage />} />
            <Route path="/character-select" element={<CharacterSelectPage />} />
            <Route path="/scoreboard" element={<ScoreboardPage />} />
            <Route path="/bracket-focus-app" element={<BracketFocusPage />} />
            <Route path="/commentary-dashboard" element={<CommentaryDashboardPage />} />
            <Route path="/report" element={<StationPage />} />
            <Route path="/report-admin" element={<AdminStandalone />} />
            <Route path="/report-approval" element={<ApprovalStandalone />} />
            <Route path="*" element={<Navigate to={"/"} replace={true} />} />
          </Routes>
        </BrowserRouter>
        <Toaster position="top-center" />
      </TooltipProvider>
    </Provider>
  </React.StrictMode>
);
