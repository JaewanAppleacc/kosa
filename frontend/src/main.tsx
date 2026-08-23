import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles/index.css";

const container = document.getElementById("root");
if (!container) throw new Error("#root를 찾을 수 없습니다.");

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
