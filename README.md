# claude-playground

Claude Code の検証用

## Docker on Claude Code on the Web

web セッションの microVM 内で Docker をフル活用するための設定一式と実測結果。

- **[docs/docker-on-claude-code-web.md](docs/docker-on-claude-code-web.md)** —
  何が動いて何が動かないか、ハマりどころ 3 点の実測メモ
- `scripts/docker-bootstrap.sh` — dockerd の起動と egress プロキシ CA の配置（冪等）
- `scripts/docker-smoke-test.sh` — 6 項目の動作確認
- `.claude/hooks/session-start.sh` — セッション開始時に上記を自動実行
- `examples/compose-stack/` — FastAPI + Postgres + Redis の動作するデモスタック

```bash
bash scripts/docker-bootstrap.sh
bash scripts/docker-smoke-test.sh

cd examples/compose-stack && docker compose up -d --build
curl -s --noproxy '*' http://127.0.0.1:8000/db
```

要点だけ 3 行:

1. `dockerd` は起動していない。`setsid` で完全にデタッチして起動する
2. `daemon.json` にプロキシを書かない（ポートがセッション中に変わる）
3. コンテナ内の HTTPS には egress プロキシの CA を入れる（検証は無効化しない）
