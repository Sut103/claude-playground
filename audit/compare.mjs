// 変更前後のスクリーンショットを 1 枚の比較画像に合成する。
// 人間のレビュアーが「差分を目で見る」ための証跡を生成する。
import { chromium } from 'playwright';
import { readFile } from 'node:fs/promises';
import path from 'node:path';

const dir = import.meta.dirname;

const PAIRS = [
  {
    title: 'R1 境界: 申請金額 ちょうど 100,000 円',
    before: 'baseline/01-boundary-100000.png',
    after: 'shots/01-boundary-100000.png',
    beforeNote: '部長承認なし / 控除税額 ¥9,000（千円丸め）',
    afterNote: '部長承認あり / 控除税額 ¥9,090（1円単位）',
  },
  {
    title: 'R5 自己承認禁止: 部長本人が 1,500,000 円を申請',
    before: 'baseline/04-director-self-approval.png',
    after: 'shots/04-director-self-approval.png',
    beforeNote: '課長承認が残存（同格以下の除外漏れ）',
    afterNote: '役員承認のみ（仕様どおり）',
  },
];

const dataUri = async (rel) =>
  'data:image/png;base64,' + (await readFile(path.join(dir, rel))).toString('base64');

const blocks = [];
for (const p of PAIRS) {
  blocks.push(`
    <section>
      <h2>${p.title}</h2>
      <div class="pair">
        <figure class="bad">
          <figcaption><span class="tag tag-bad">修正前</span> ${p.beforeNote}</figcaption>
          <img src="${await dataUri(p.before)}" />
        </figure>
        <figure class="good">
          <figcaption><span class="tag tag-good">修正後</span> ${p.afterNote}</figcaption>
          <img src="${await dataUri(p.after)}" />
        </figure>
      </div>
    </section>`);
}

const html = `<!doctype html><meta charset="utf-8"><style>
  body { font-family: system-ui, "Noto Sans JP", sans-serif; background:#fff; margin:0; padding:28px; color:#14181d; }
  h1 { font-size:20px; margin:0 0 4px; }
  .sub { color:#5b636c; font-size:13px; margin:0 0 24px; }
  section { margin-bottom:28px; }
  h2 { font-size:15px; margin:0 0 10px; padding-bottom:6px; border-bottom:1px solid #e3e6ea; }
  .pair { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
  figure { margin:0; }
  figcaption { font-size:12px; color:#41474e; margin-bottom:6px; display:flex; align-items:center; gap:8px; }
  .tag { font-weight:700; padding:2px 8px; border-radius:4px; font-size:11px; }
  .tag-bad { background:#fee2e2; color:#b42318; }
  .tag-good { background:#dcfce7; color:#15803d; }
  img { width:100%; border:1px solid #e3e6ea; border-radius:6px; display:block; }
  .bad img { border-color:#fca5a5; }
  .good img { border-color:#86efac; }
</style>
<h1>監査による検出と是正の証跡</h1>
<p class="sub">仕様オラクル全数照合（768 ケース）と UI 実描画照合（324 ケース）が検出した不整合の修正前後比較</p>
${blocks.join('\n')}`;

const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH ?? '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
});
const page = await browser.newPage({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 2 });
await page.setContent(html, { waitUntil: 'load' });
const out = path.join(dir, 'before-after.png');
await page.screenshot({ path: out, fullPage: true });
await browser.close();
console.log('wrote ' + out);
