# taskcli

AI エージェントと人間が、同じ Markdown ファイルを読み書きして共有するタスク管理 CLI。

仕様は [Epic #3](https://github.com/Sut103/claude-playground/issues/3) と `.claude/prds/task-cli.md` にある。

## 使い方

```bash
python -m taskcli add "リファクタする" --priority high --tag refactor --due 2026-08-20
python -m taskcli list
python -m taskcli list --all
python -m taskcli done 1
python -m taskcli rm 1
```

タスクファイルの既定パスは `./TASKS.md`。環境変数 `TASK_CLI_FILE` で変更できる。

## 保存形式

```markdown
- [ ] リファクタする `#3` `!high` `@docs` `@refactor` `~2026-08-20`
- [x] README を書く `#1` `!mid`
```

`#N` が ID、`!` が優先度、`@` がタグ、`~` が期限。GitHub 上でチェックリストとして
レンダリングされ、人間がエディタで直接編集できる。CLI が解釈できない行（見出し、
メモ、通常の箇条書き）は、CLI 操作を経ても原文のまま同じ位置に残る。

## 開発

### テストランナーの決定（Issue #4）

**pytest を採用した。**

エピックの Dependencies は「プロキシ経由の `pip install` が失敗した場合は標準ライブラリの
`unittest` へフォールバックする」と定めていた。実際に検証した結果は次のとおり。

```
$ python3 -m pip install pytest
Successfully installed iniconfig-2.3.0 pluggy-1.6.0 pygments-2.20.0 pytest-9.1.1
$ echo $?
0
```

**インストールは成功した（pytest 9.1.1）。** したがって unittest へのフォールバックは
発動せず、テストは pytest の記法（プレーンな `assert`、`tmp_path` フィクスチャ）で書く。
Issue #4 の Technical Details にあった「`unittest.TestCase` と `tempfile.TemporaryDirectory`
に統一する」という方針は、フォールバックが起きた場合に備えた条件付きの取り決めであり、
pytest が使える以上は適用しない。後続タスクはこの決定を再検討しない。

### 実行

```bash
python -m pytest
```

実行時依存は Python 標準ライブラリのみ（`pyproject.toml` の `dependencies` は空）。
pytest は開発時のみの依存として `optional-dependencies.dev` に置いてある。
