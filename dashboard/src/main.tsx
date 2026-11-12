import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { savedAppearance, setAppearance } from "./theme";
import "./theme.css";

setAppearance(savedAppearance(), false);

const root = document.getElementById("root");
if (!root) throw new Error("index.html has no #root element");

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
