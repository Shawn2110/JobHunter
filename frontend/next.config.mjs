import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Pin the file-tracing root to this folder so Next.js doesn't infer
  // a parent directory when the user has unrelated package.json files
  // higher up the path.
  outputFileTracingRoot: __dirname,
};

export default nextConfig;
