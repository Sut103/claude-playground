# GitHub Issue Mapping

Epic: #3 - https://github.com/Sut103/claude-playground/issues/3

Tasks:
- #4: プロジェクト構造とテスト基盤のセットアップ - https://github.com/Sut103/claude-playground/issues/4
- #5: パーサ層 — Task モデルと行の相互変換 - https://github.com/Sut103/claude-playground/issues/5
- #6: ストア層 — 読み書き、原子的置換、ID 採番 - https://github.com/Sut103/claude-playground/issues/6
- #7: 表示層 — 並び順、期限状態の判定と整形 - https://github.com/Sut103/claude-playground/issues/7
- #8: コマンド層 — argparse の骨格と 4 サブコマンド - https://github.com/Sut103/claude-playground/issues/8
- #9: 結線と E2E テスト — 実際のコマンド実行での通し確認 - https://github.com/Sut103/claude-playground/issues/9
- #10: 受け入れ確認 — Success Criteria の検証 - https://github.com/Sut103/claude-playground/issues/10

Synced: 2026-08-10T12:38:39Z

## 同期方法についての注記

CCPM の `sync.md` は `gh issue create` を前提としているが、本セッションのクラウド環境では
`gh` の高レベルサブコマンドが GraphQL ゲートで 403 になるため使用できない。
代替として GitHub MCP ツール（`issue_write` / `sub_issue_write`）で同一の結果を作成した。

- 旧ファイル名 → Issue 番号: 001→4, 002→5, 003→6, 004→7, 005→8, 006→9, 007→10
- sub-issue 階層は `sub_issue_write(add)` で構築済み（`sub_issues_summary.total = 7`）
- ラベル `epic` / `epic:task-cli` / `feature` / `task` は Issue 作成時に自動生成された
  （`init.sh` のラベル作成は 403 でスキップされていた）
