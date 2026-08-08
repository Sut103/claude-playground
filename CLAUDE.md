# claude-playground

Claude Code の検証用リポジトリ。

## このリポジトリの設定方針

Claude Code on the web（クラウドセッション）は、リポジトリを毎回新規に clone した
使い捨て VM 上で動く。したがって **リポジトリにコミットされた設定だけが全員に共通で効く**。
個人のマシン上の `~/.claude/` や、claude.ai/code で各自が作る「クラウド環境」の設定は
他のメンバーには一切届かない。

共通化したい設定は必ず以下に置く:

| 置き場所 | 用途 |
| --- | --- |
| `CLAUDE.md` | プロジェクト共通の指示 |
| `.claude/rules/` | 分割した規約・ルール |
| `.claude/settings.json` | hooks / permissions / env / plugins |
| `.claude/hooks/` | hook 本体のスクリプト |
| `.claude/skills/`, `.claude/agents/`, `.claude/commands/` | 独自スキル・サブエージェント・スラッシュコマンド |
| `.mcp.json` | MCP サーバー定義（`claude mcp add --scope project`） |

詳細は `docs/claude-code-web-shared-config.md` を参照。

## 禁止事項

- シークレットを `.claude/settings.json`、クラウド環境の環境変数、セットアップ
  スクリプトに書かない。いずれも秘密情報の保管場所ではなく、その環境を使う全員から
  読み取れる。
