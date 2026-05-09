// Rapidly email renderer — bundle as a self-contained IIFE binary.
import { defineConfig } from "tsup";

export default defineConfig({
  entry: ["src/index.tsx"],
  format: ["iife"],
  clean: true,
});
