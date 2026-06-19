import { ApolloClient, InMemoryCache, HttpLink, split } from "@apollo/client";
import { GraphQLWsLink } from "@apollo/client/link/subscriptions";
import { createClient } from "graphql-ws";
import { getMainDefinition } from "@apollo/client/utilities";

const API_BASE = import.meta.env.VITE_API_BASE ?? "https://twin-api.dev.neom.internal";
const WS_BASE = API_BASE.replace(/^http/, "ws");

const httpLink = new HttpLink({ uri: `${API_BASE}/graphql` });

const wsLink = new GraphQLWsLink(
  createClient({
    url: `${WS_BASE}/graphql`,
    connectionParams: async () => ({
      authorization: `Bearer ${localStorage.getItem("neom_sso_token") ?? ""}`,
    }),
    retryAttempts: Infinity,
  }),
);

const splitLink = split(
  ({ query }) => {
    const def = getMainDefinition(query);
    return def.kind === "OperationDefinition" && def.operation === "subscription";
  },
  wsLink,
  httpLink,
);

export const apolloClient = new ApolloClient({
  link: splitLink,
  cache: new InMemoryCache(),
});
