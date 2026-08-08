# Claude Code on the Web で Docker はどこまで使えるか

実測メモ。すべてこのリポジトリの web セッション内で実際に動かして確認した結果です。

結論から言うと **ほぼフルスペックの Docker が使えます**。イメージビルド、docker compose に
よる複数コンテナ開発、リソース制限、特権コンテナ、Docker-in-Docker、QEMU によるクロス
アーキテクチャビルドまで動きました。詰まるのは主に 2 点、**デーモンが起動していない**ことと
**コンテナ内の TLS 検証**です。どちらも `scripts/docker-bootstrap.sh` で解決します。

## 実行環境

web セッションはコンテナではなく **Firecracker の microVM** です。ここが重要で、だからこそ
入れ子のコンテナを自由に作れます。

| 項目 | 値 |
| --- | --- |
| カーネル | 6.18.5-fc-v20 (Ubuntu 24.04.4 ベース) |
| ユーザー | root (`CapEff: 000001fffeffffff` — 落ちているのは `CAP_SYS_TIME` のみ) |
| seccomp | VM 側ではフィルタなし (`Seccomp: 0`) |
| CPU / メモリ | 4 vCPU / 15.7 GiB |
| ディスク | 書き込み可能領域に約 29 GB の空き |
| cgroup | v1 (hybrid、`/sys/fs/cgroup/unified` に v2 も) |
| PID 1 | `/process_api` (systemd なし) |

インストール済みで、そのまま使えるもの:

- Docker Engine / CLI **29.3.1**
- Buildx **v0.31.1** (バンドル BuildKit v0.28.1)
- Compose **v5.1.1**
- containerd, containerd-shim-runc-v2, runc v1.3.4, docker-proxy

## 落とし穴 1: デーモンが起動していない

バイナリはあるのに `/var/run/docker.sock` がありません。init システムがないので誰も
`dockerd` を起動しないからです。自分で起動します。

**必ず `setsid` で完全にデタッチしてください。** 単なるバックグラウンドジョブだと、その
ツール呼び出しのプロセスグループに残ります。呼び出しが中断・終了した瞬間にデーモンごと
巻き添えで死にます（実際にこれで一度落ちました）。

```bash
setsid dockerd >> /var/log/dockerd.log 2>&1 </dev/null & disown
```

起動後は `PPID 1` の独立したセッションリーダーになり、以降のツール呼び出しをまたいで
生き続けます。コールドスタートは実測 **約 1.3 秒**です。

ストレージドライバは `overlay2`（ext4 上、`d_type: true`）、cgroup ドライバは `cgroupfs`
が自動選択されます。特別な設定は要りません。

## 落とし穴 2: `daemon.json` にプロキシを書いてはいけない

セッションには `HTTPS_PROXY=http://127.0.0.1:<port>` が設定されていて、`DOCKER_HTTPS_PROXY`
まで用意されています。これを `daemon.json` の `proxies` に書きたくなりますが、**書かないで
ください**。

このプロキシの**ポート番号はセッション中に変わります**（実測で 42809 → 43941）。焼き込むと、
ポートが移動した瞬間に全 pull がこう失敗します:

```
proxyconnect tcp: dial tcp 127.0.0.1:42809: connect: connection refused
```

プロキシ設定は不要です。VM からの直接 egress は透過ゲートウェイ経由でそのまま通り、その CA は
すでに VM のシステムトラストストアに入っています。`daemon.json` は最小限で十分:

```json
{
  "storage-driver": "overlay2",
  "features": { "buildkit": true },
  "log-level": "info"
}
```

## 落とし穴 3: コンテナ内の HTTPS は CA を入れるまで検証に失敗する

これが一番ハマりどころです。コンテナから外部への通信は**ネットワーク的には通っています** —
DNS も解決するし TCP 443 も開きます。それでも `pip` / `npm` / `curl` がこう落ちます:

```
certificate verify failed
```

egress ゲートウェイが TLS を張り直しているためです。VM はその CA を信頼していますが、
新しいコンテナは信頼していません。TLS 検証を無効化するのは**やってはいけません**。CA を
入れれば正しく検証が通ります:

```dockerfile
COPY ca-bundle.crt /usr/local/share/ca-certificates/ccr-proxy.crt
ENV PIP_CERT=/usr/local/share/ca-certificates/ccr-proxy.crt \
    SSL_CERT_FILE=/usr/local/share/ca-certificates/ccr-proxy.crt \
    REQUESTS_CA_BUNDLE=/usr/local/share/ca-certificates/ccr-proxy.crt
```

使い捨ての `docker run` ならマウントで十分:

```bash
docker run --rm -v /root/.ccr/ca-bundle.crt:/etc/ssl/certs/ca-certificates.crt:ro alpine:3.20 ...
```

`scripts/docker-bootstrap.sh` が全 Dockerfile の隣に `ca-bundle.crt` を自動配置するので、
`COPY ca-bundle.crt ...` と書くだけで済みます。証明書は環境ごとに再生成されるため
`.gitignore` 済みです。

なお **`ubuntu:24.04` はブートストラップの順序に注意**が必要です。最小イメージには
`/etc/ssl/certs` すら存在しません。apt は平文 HTTP なので TLS 不要 — 先に
`apt-get install ca-certificates` してから CA を入れて `update-ca-certificates` します。

## Egress の許可リスト

ここは組織の egress ポリシー次第ですが、このセッションでの実測値です。**回避してはいけません** —
届かないホストはポリシーで止められています。

| 到達可 | 到達不可 (403) |
| --- | --- |
| registry-1.docker.io, ghcr.io, gcr.io, mcr.microsoft.com, public.ecr.aws | quay.io |
| pypi.org, files.pythonhosted.org | dl-cdn.alpinelinux.org |
| registry.npmjs.org | deb.debian.org |
| index.crates.io, proxy.golang.org | jsr.io |
| github.com, raw./codeload./objects.githubusercontent.com | |
| **archive.ubuntu.com, security.ubuntu.com** | |

ベースイメージ選定に直結する実用的な結論:

- **`apt` を使いたいなら Debian ではなく Ubuntu ベースを選ぶ。** `archive.ubuntu.com` は
  通りますが `deb.debian.org` は 403 です。
- **Alpine で `apk add` はできません。** ただし Alpine を pull して動かすことは可能です
  （Docker Hub は許可、Alpine の CDN が不許可）。`postgres:16-alpine` などパッケージを
  追加せず使うぶんには問題ありません。
- **`pip` / `npm` / `cargo` / `go mod` はそのまま通ります**（CA を入れれば）。

## 動いたこと

すべて実測です。

**ビルド**
- 旧ビルダー (`DOCKER_BUILDKIT=0`) と BuildKit の両方
- マルチステージビルド
- キャッシュマウント `RUN --mount=type=cache` — pip キャッシュが効いて 12.5 秒 → 7.0 秒
- シークレットマウント `--secret id=tok,src=...`
- ヒアドキュメント `RUN <<'SH'`
- ビルド中のネットワークアクセス（`apt-get`、`pip install`、`curl` すべて成功）

**Compose による開発スタック** (`examples/compose-stack/`)

FastAPI + Postgres 16 + Redis 7 のスタックを起動し、以下を確認:
- `--build` 込みの `compose up -d` が 21 秒で完了
- ヘルスチェックと `depends_on: condition: service_healthy` による起動順制御
- ユーザー定義ネットワーク上のサービス名 DNS (`db` → 172.18.0.2 など)
- 名前付きボリュームの永続化 — `compose down` → `up` をまたいで Postgres の行が残存
- ポート公開 (`127.0.0.1:8000:8000`) と VM 側からの `curl` 疎通
- `docker compose exec` / `logs` / `docker cp`

**ランタイム**
- リソース制限: `--memory=256m` `--cpus=1.5` が cgroup に正しく反映
- OOM キラーが実際に効く（64 MiB 制限に 200 MiB 書き込み → `Killed`）
- 既定のコンテナは適切に絞られている (`Seccomp: 2`、ケーパビリティ削減済み)
- `--privileged` でフルケーパビリティ + `mknod` 可
- `--network=host`
- `--add-host=host.docker.internal:host-gateway` — ただし VM 側が `0.0.0.0` で
  listen している場合のみ。`127.0.0.1` バインドのポートはコンテナから見えません

**入れ子とマルチアーキ**
- **Docker-in-Docker**: `--privileged` で `docker:27-dind` を起動 → 入れ子の dockerd が
  overlay2 で起動し、入れ子側で `docker run` と `docker build` が両方成功
  （CA のマウントが必須）
- **Docker-outside-of-Docker**: `/var/run/docker.sock` をマウントしてホスト側の
  コンテナ一覧を取得
- **クロスアーキテクチャビルド**: `binfmt_misc` は未マウントなので手動で用意する
  ```bash
  mount -t binfmt_misc binfmt_misc /proc/sys/fs/binfmt_misc
  docker run --privileged --rm tonistiigi/binfmt --install arm64
  ```
  この後 `--platform linux/arm64` のビルドが通り、x86 ホスト上で arm64 イメージを
  実行して `uname -m` が `aarch64` を返すことも確認
- **マルチプラットフォームのマニフェスト**: `docker-container` ドライバのビルダーで
  `linux/amd64,linux/arm64` の OCI インデックスを生成。ただしビルダーは別コンテナで
  動くため、**CA を焼き込んだ BuildKit イメージが必要**:
  ```dockerfile
  FROM moby/buildkit:buildx-stable-1
  COPY ca-bundle.crt /tmp/ccr.crt
  RUN cat /tmp/ccr.crt >> /etc/ssl/certs/ca-certificates.crt
  ```
  ```bash
  docker buildx create --name xbuilder --driver docker-container \
    --driver-opt image=buildkit-ccr:local --bootstrap
  ```

## 制約

- **何も永続しません。** microVM はセッション終了後に回収されます。イメージ、ボリューム、
  ビルドキャッシュ、`/var/lib/docker` はすべて消えます。残したいものは commit & push が必須です。
- **公開ポートは外部から到達できません。** 公開ポートは microVM 内でのみ有効です。ブラウザで
  開けるプレビュー URL にはなりません。動作確認は VM 内から `curl` で行うことになります。
- **Egress は許可リスト制**（上表）。回避せず、届かないホストは報告してください。
- **cgroup v1** です。cgroup v2 前提のツール（一部の新しい可観測性ツールなど）は動かない
  可能性があります。Docker 自体は非推奨警告を出しますが正常に動作します。
- **ディスク予算に注意。** 空きは約 29 GB です。この実験だけでイメージ 1.37 GB +
  ビルドキャッシュ 222 MB を消費しました。大きなイメージを扱うときは
  `docker system prune -af` で掃除してください。
- **binfmt は毎回入れ直し**です。ハンドラの登録はセッションをまたぎません。
- **GPU なし。**

## 使い方

セッション開始時にフックが自動で走ります（`.claude/settings.json` に登録済み）。手動なら:

```bash
bash scripts/docker-bootstrap.sh    # デーモン起動 + CA 配置
bash scripts/docker-smoke-test.sh   # 6 項目の動作確認
```

デモスタック:

```bash
cd examples/compose-stack
docker compose up -d --build
curl -s --noproxy '*' http://127.0.0.1:8000/db
docker compose down -v
```

このフックは同期実行です。セッション開始が数秒遅くなる代わりに、Claude が動き出す前に
Docker が確実に使える状態になります。フックをデフォルトブランチにマージすれば、以降の
全セッションで有効になります。
