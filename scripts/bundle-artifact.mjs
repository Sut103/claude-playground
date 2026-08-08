/**
 * dist/ のビルド成果物を 1 枚の HTML に束ねる。
 * Artifact は外部ホストへのリクエストを CSP で止めるので、
 * JS も CSS も外部参照ではなくインラインにする必要がある。
 *
 *   npm run build
 *   npm run bundle:artifact    # → dist/standalone.html
 *
 * 出力は <!doctype>/<html>/<head>/<body> を含まない断片。
 * Artifact 側がその骨組みを被せるため、中身だけを書き出す。
 */
import { readFile, readdir, writeFile } from 'node:fs/promises'
import path from 'node:path'

const DIST = 'dist'
const OUT = path.join(DIST, 'standalone.html')

const assets = await readdir(path.join(DIST, 'assets'))
const jsFile = assets.find((name) => name.endsWith('.js'))
const cssFile = assets.find((name) => name.endsWith('.css'))

if (!jsFile || !cssFile) {
  console.error('dist/assets に js / css が見つかりません。先に npm run build を実行してください。')
  process.exit(1)
}

const [js, css] = await Promise.all([
  readFile(path.join(DIST, 'assets', jsFile), 'utf8'),
  readFile(path.join(DIST, 'assets', cssFile), 'utf8'),
])

// </script> がスクリプト本文に現れると HTML パーサが早期に閉じてしまう
const safeJs = js.replaceAll('</script>', '<\\/script>')

// 断片には <head> が無く、配信側が charset を付けてくれる保証も無い。
// 先頭 1024 バイト以内の meta charset は位置に関わらず効くので、必ず先頭に置く。
const html = `<meta charset="utf-8" />
<title>DX Board — Claude Code フロントエンド体験</title>
<style>
${css}
</style>
<div id="root"></div>
<script type="module">
${safeJs}
</script>
`

await writeFile(OUT, html)
console.log(`✓ ${OUT} (${(html.length / 1024).toFixed(0)} kB)`)
console.log(`  js: ${jsFile}  css: ${cssFile}`)
