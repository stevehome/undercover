import { useEffect, useState } from "react";
import { BrowserRouter, Route, Routes } from "react-router";
import { fetchMe } from "./api";
import { signOut } from "./auth";
import { LoadError } from "./components/LoadError";
import { Loading } from "./components/Loading";
import { Navigation } from "./components/Navigation";
import { ClaimPage } from "./pages/ClaimPage";
import { ConfigurationPage } from "./pages/ConfigurationPage";
import { EvaluationPage } from "./pages/EvaluationPage";
import { ImprovementPage } from "./pages/ImprovementPage";
import { QueuePage } from "./pages/QueuePage";
import { ScoreboardPage } from "./pages/ScoreboardPage";
import { SettingsPage } from "./pages/SettingsPage";
import { SignInPage } from "./pages/SignInPage";
import type { Handler } from "./types";
import { MeContext } from "./useMe";
import { useSignedIn } from "./useSignedIn";

function Shell() {
  const [me, setMe] = useState<Handler | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    fetchMe().then(setMe, () => {
      setFailed(true);
    });
  }, []);

  if (me === null) return failed ? <LoadError /> : <Loading />;

  return (
    <MeContext.Provider value={me}>
      <header className="app-header">
        <Navigation />
        <div className="signed-in">
          <span>{me.name}</span>
          <button
            type="button"
            onClick={() => {
              void signOut();
            }}
          >
            Sign out
          </button>
        </div>
      </header>
      <Routes>
        <Route path="/" element={<QueuePage />} />
        <Route path="/claims/:claimId" element={<ClaimPage />} />
        <Route path="/scoreboard" element={<ScoreboardPage />} />
        <Route path="/evaluations/:runId" element={<EvaluationPage />} />
        <Route path="/improvement" element={<ImprovementPage />} />
        <Route path="/configuration" element={<ConfigurationPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Routes>
    </MeContext.Provider>
  );
}

export function App() {
  const signedIn = useSignedIn();
  if (signedIn === null) return <Loading />;
  if (!signedIn) return <SignInPage />;
  return (
    <BrowserRouter>
      <Shell />
    </BrowserRouter>
  );
}
