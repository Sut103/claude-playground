/**
 * 起動中の dev / preview サーバーに実ブラウザで接続し、
 * ライト・ダーク・モバイルの 3 枚を撮る。
 *
 *   npm run dev &          # 別プロセスで起動しておく
 *   npm run screenshot     # → screenshots/*.png
 *
 * Claude Code on the Web のコンテナには Chromium が同梱されているので
 * `playwright install` は不要。
 */
import { existsSync, readdirSync } from 'node:fs'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { chromium } from 'playwright'

const BASE_URL = process.env.BASE_URL ?? 'http://localhost:5173/'
const OUT_DIR = process.env.OUT_DIR ?? 'screenshots'

/**
 * 同梱 Chromium のビルド番号は playwright パッケージが期待する番号と
 * 一致しないことがある。あるものを探して使い、無ければ通常の解決に任せる。
 */
function bundledChromium() {
  const root = process.env.PLAYWRIGHT_BROWSERS_PATH
  if (!root || !existsSync(root)) return undefined
  const dir = readdirSync(root)
    .filter((entry) => entry === 'chromium' || entry.startsWith('chromium-'))
    .sort()
    .reverse()
    .map((entry) => path.join(root, entry, 'chrome-linux', 'chrome'))
    .find((candidate) => existsSync(candidate))
  return dir
}

const SHOTS = [
  { name: 'light', colorScheme: 'light', viewport: { width: 1280, height: 900 } },
  { name: 'dark', colorScheme: 'dark', viewport: { width: 1280, height: 900 } },
  { name: 'mobile', colorScheme: 'light', viewport: { width: 390, height: 844 } },
]

const executablePath = bundledChromium()
if (executablePath) console.log(`using bundled chromium: ${executablePath}`)

const browser = await chromium.launch({ executablePath })
const errors = []

try {
  await mkdir(OUT_DIR, { recursive: true })

  for (const shot of SHOTS) {
    const context = await browser.newContext({
      colorScheme: shot.colorScheme,
      viewport: shot.viewport,
      deviceScaleFactor: 2,
      locale: 'ja-JP',
    })
    const page = await context.newPage()

    // コンソールエラーは見た目と同じくらい重要な回帰なので拾っておく
    page.on('console', (message) => {
      if (message.type() === 'error') errors.push(`[${shot.name}] ${message.text()}`)
    })
    page.on('pageerror', (error) => errors.push(`[${shot.name}] ${error.message}`))

    await page.goto(BASE_URL, { waitUntil: 'networkidle' })
    await page.getByRole('heading', { name: 'DX Board' }).waitFor()

    const path = `${OUT_DIR}/${shot.name}.png`
    await page.screenshot({ path, fullPage: true })
    console.log(`✓ ${path} (${shot.viewport.width}×${shot.viewport.height}, ${shot.colorScheme})`)

    await context.close()
  }
} finally {
  await browser.close()
}

if (errors.length > 0) {
  console.error('\nブラウザコンソールにエラーがあります:')
  for (const error of errors) console.error(`  ${error}`)
  process.exit(1)
}

console.log('\nコンソールエラーなし。')
