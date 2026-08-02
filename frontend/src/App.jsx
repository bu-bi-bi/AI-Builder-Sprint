import React from "react";
import Home from "./pages/Home";
import Result from "./pages/Result";

function App() {
  const path = window.location.pathname;

  if (path.startsWith("/result")) {
    return <Result />;
  }

  return <Home />;
}

export default App;
