import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import fs from "fs";
import path from "path";

// Strip UTF-8 BOM from .env files — PowerShell's Set-Content writes BOM by
// default which causes Vite to misread variable names (e.g. \ufeffVITE_API_BASE_URL).
function stripEnvBom() {
  const envFiles = [".env", ".env.local", ".env.development", ".env.development.local"];
  for (const file of envFiles) {
    const filePath = path.resolve(__dirname, file);
    if (fs.existsSync(filePath)) {
      const content = fs.readFileSync(filePath);
      if (content[0] === 0xef && content[1] === 0xbb && content[2] === 0xbf) {
        fs.writeFileSync(filePath, content.slice(3));
        console.log(`[vite] Stripped UTF-8 BOM from ${file}`);
      }
    }
  }
}

stripEnvBom();

export default defineConfig({
  plugins: [react()],
});
