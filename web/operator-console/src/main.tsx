import React from "react";
import ReactDOM from "react-dom/client";
import { ApolloProvider } from "@apollo/client";
import { BrowserRouter } from "react-router-dom";

import { apolloClient } from "./api/client";
import { Dashboard } from "./routes/Dashboard";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ApolloProvider client={apolloClient}>
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    </ApolloProvider>
  </React.StrictMode>,
);
