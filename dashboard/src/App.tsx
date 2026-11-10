import { BrowserRouter, Link, Route, Routes } from "react-router";
import { ClaimPage } from "./pages/ClaimPage";
import { EvaluationPage } from "./pages/EvaluationPage";
import { InstructionsPage } from "./pages/InstructionsPage";
import { QueuePage } from "./pages/QueuePage";
import { ScoreboardPage } from "./pages/ScoreboardPage";

export function App() {
  return (
    <BrowserRouter>
      <nav className="top-nav">
        <Link to="/">Queue</Link>
        <Link to="/scoreboard">Scoreboard</Link>
        <Link to="/instructions">Instructions</Link>
      </nav>
      <Routes>
        <Route path="/" element={<QueuePage />} />
        <Route path="/claims/:claimId" element={<ClaimPage />} />
        <Route path="/scoreboard" element={<ScoreboardPage />} />
        <Route path="/evaluations/:runId" element={<EvaluationPage />} />
        <Route path="/instructions" element={<InstructionsPage />} />
      </Routes>
    </BrowserRouter>
  );
}
