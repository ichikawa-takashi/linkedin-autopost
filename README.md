# LinkedIn 毎朝自動投稿

PCを閉じていても、毎朝8時ごろ（日本時間）に「Web制作」をテーマにした投稿が LinkedIn に公開されます。すべて GitHub 上で動き、**費用はかかりません**（GitHub Actions・GitHub Models・LinkedIn API の無料枠内）。

## しくみ

1. **毎朝7:50** に GitHub Actions が起動し、GitHub Models（無料のAI）で投稿文を作成（直近14件と重複しないように調整）
2. LinkedIn 公式 API で投稿（GitHub側の混雑で数分〜十数分遅れることがあります）
3. 投稿文は `posts/YYYY-MM-DD.md`、投稿済みの記録は `posted/YYYY-MM-DD.json` に保存。二重投稿はしません
4. 失敗した場合は **9:10** にもう一度試します

**自分で書いた文章を投稿したい日**は、前日までに `posts/YYYY-MM-DD.md` を作っておくと、その文章がそのまま投稿されます（当日のファイルを追加した場合は、追加した時点ですぐ投稿されます）。
**一時的に止めたい**ときは Actions → Post to LinkedIn → 右上「…」→ **Disable workflow**。

## 初回セットアップ

### 1. LinkedIn 開発者アプリ
1. https://www.linkedin.com/developers/apps → **Create app**
2. App name は任意。LinkedIn Page には会社ページ（Hreed など）を指定
3. **Products** タブで次の2つを **Request access**
   - **Share on LinkedIn**
   - **Sign In with LinkedIn using OpenID Connect**

### 2. LinkedIn アクセストークン
1. https://www.linkedin.com/developers/tools/oauth/token-generator
2. 作成したアプリを選び、スコープ `openid` `profile` `w_member_social` にチェック
3. **Request access token** → 許可 → 表示されたトークンをコピー

### 3. GitHub に登録
このリポジトリの **Settings → Secrets and variables → Actions → New repository secret** で登録：

- Name: `LINKEDIN_ACCESS_TOKEN` / Secret: 手順2のトークン

### 4. 動作確認
**Actions → Post to LinkedIn → Run workflow** で `dry_run` に `1` を入れて実行。ログに作成された投稿文が表示され、エラーがなければ準備完了です（dry_run では投稿しません）。

## 任意の設定（Settings → Secrets and variables → Actions → **Variables** タブ）
- `POST_THEME`: テーマを変更（既定: `Web制作`）
- `AI_MODEL`: 使用するモデルIDを指定（既定: `openai/gpt-4.1`。一覧は https://github.com/marketplace?type=models ）

## ⚠️ 60日ごとのトークン更新
LinkedIn のトークンは **60日で失効** します。失効すると Actions が失敗し、GitHub から通知メールが届きます。手順2をやり直し、`LINKEDIN_ACCESS_TOKEN` を上書きしてください。
