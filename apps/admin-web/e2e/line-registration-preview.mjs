// Local UI tests only: no production API or LINE Login requests.
import { createServer } from "vite";

const server = await createServer({
  configFile: false,
  cacheDir: ".vite/registration-preview",
  server: { host: "127.0.0.1", port: 4317, strictPort: true },
});
await server.listen();
