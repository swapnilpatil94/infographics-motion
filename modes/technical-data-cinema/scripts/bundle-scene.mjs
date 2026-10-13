import { build } from "esbuild";

export async function bundleSceneHtml(html, root) {
  const moduleScripts = [...html.matchAll(/<script\b(?=[^>]*\btype\s*=\s*["']module["'])[^>]*>([\s\S]*?)<\/script\s*>/gi)];
  if (moduleScripts.length > 1) {
    throw new Error("Generated HTML contains multiple module scripts. Use one module script so the scene can be bundled into a single offline HTML file.");
  }
  if (moduleScripts.length === 1) {
    const match = moduleScripts[0];
    const result = await build({
      stdin: { contents: match[1], resolveDir: root, sourcefile: "generated-scene.js", loader: "js" },
      bundle: true,
      write: false,
      platform: "browser",
      format: "iife",
      target: "es2022",
      minify: true,
      legalComments: "none"
    });
    const bundled = result.outputFiles[0]?.text;
    if (!bundled) throw new Error("esbuild returned no bundled output");
    return html.replace(match[0], `<script>\n${bundled}\n</script>`);
  }
  if (/from\s*["']three(?:\/|["'])|import\s*["']three(?:\/|["'])/.test(html)) {
    throw new Error('Generated HTML imports Three.js but has no <script type="module"> block. Put Three.js imports in one module script so they can be bundled offline.');
  }
  return html;
}
