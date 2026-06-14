import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { initGA4 } from "./lib/ga4";
import "./index.css";

initGA4();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
