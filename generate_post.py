#!/usr/bin/env python3
"""GitHub Models（無料）で今日の LinkedIn 投稿文（テーマ: Web制作）を作成し posts/YYYY-MM-DD.md に保存する。

環境変数:
  GITHUB_TOKEN       必須（GitHub Actions が自動で用意）
  AI_MODEL           任意。使うモデルID（未設定なら下の候補を順に試す）
  POST_DATE          任意。YYYY-MM-DD
  POST_THEME         任意。テーマ（既定: Web制作）
"""
import datetime as dt
import glob
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

JST = dt.timezone(dt.timedelta(hours=9))
ROOT = os.environ.get("GITHUB_WORKSPACE") or os.getcwd()
DEFAULT_MODELS = ["openai/gpt-4.1", "openai/gpt-4o", "openai/gpt-4.1-mini"]

SYSTEM = """あなたは日本のビジネスパーソンの LinkedIn 投稿を代筆するライターです。
テーマ「{theme}」について、今日の投稿を1本書いてください。

ルール:
- 文体は「です・ます」調で丁寧に。誠実で落ち着いたトーン
- 400〜700文字程度。冒頭1〜2行で読み手の興味を引く
- 1投稿1トピック。具体的な実務のヒント・考え方・最近の技術動向などから選ぶ
  （例: UI/UX、アクセシビリティ、表示速度、SEO、CMS、デザインと開発の連携、要件定義、運用保守、生成AIの活用 など）
- 読みやすさのため適度に改行し、箇条書きは「・」を使う
- 架空の体験談・社名・顧客名・具体的な数値実績・統計データは創作しない。確かな一般論として書く
- 最後に読み手への問いかけを1文入れてもよい
- 末尾にハッシュタグを3〜5個（例: #Web制作 #ホームページ制作 #UIUX）
- 絵文字は使わないか、使っても1〜2個まで
- 出力は投稿本文のみ。前置き・説明・見出し・コードブロックは不要"""


def recent_posts(limit=14):
    files = sorted(glob.glob(os.path.join(ROOT, "posts", "*.md")))[-limit:]
    out = []
    for f in files:
        body = open(f, encoding="utf-8").read().strip()
        out.append(f"[{os.path.basename(f)[:-3]}]\n{body[:300]}")
    return "\n\n".join(out)


ENDPOINT = "https://models.github.ai/inference/chat/completions"


def _parse(raw):
    data = json.loads(raw)
    return (data["choices"][0]["message"]["content"] or "").strip()


def call_model(token, model, system, user):
    payload = json.dumps({
        "model": model,
        "max_tokens": 1500,
        "temperature": 0.9,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
    }, ensure_ascii=False)
    errors = []

    # 1) curl で呼び出し（GitHub 公式ドキュメントと同じ形式）
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write(payload)
        body_file = f.name
    try:
        r = subprocess.run(
            ["curl", "-sS", "-L", "-X", "POST", ENDPOINT,
             "-H", "Accept: application/vnd.github+json",
             "-H", f"Authorization: Bearer {token}",
             "-H", "X-GitHub-Api-Version: 2022-11-28",
             "-H", "Content-Type: application/json",
             "--data-binary", f"@{body_file}",
             "-w", "\n__STATUS__%{http_code}"],
            capture_output=True, text=True, timeout=180)
        out, _, status = r.stdout.rpartition("\n__STATUS__")
        try:
            text = _parse(out)
            if text:
                return text
            errors.append(f"curl [{model}] 空の応答")
        except Exception:
            errors.append(f"curl [{model}] HTTP {status}: {out[:300]!r} {r.stderr[:200]}")
    finally:
        os.unlink(body_file)

    # 2) Python 標準ライブラリで呼び出し
    req = urllib.request.Request(
        ENDPOINT, data=payload.encode("utf-8"), method="POST",
        headers={"Authorization": f"Bearer {token}",
                 "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28",
                 "Content-Type": "application/json",
                 "User-Agent": "linkedin-autopost/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8", "replace")
            try:
                text = _parse(raw)
                if text:
                    return text
                errors.append(f"urllib [{model}] 空の応答")
            except Exception:
                errors.append(f"urllib [{model}] HTTP {resp.status} {dict(resp.headers)}: {raw[:300]!r}")
    except urllib.error.HTTPError as e:
        errors.append(f"urllib [{model}] HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}")
    except Exception as e:
        errors.append(f"urllib [{model}] {type(e).__name__}: {e}")
    raise RuntimeError("\n".join(errors))


def main():
    date = os.environ.get("POST_DATE") or dt.datetime.now(JST).strftime("%Y-%m-%d")
    path = os.path.join(ROOT, "posts", f"{date}.md")
    if os.path.exists(path):
        print(f"{date} の投稿ファイルは既にあります（手書き or 作成済み）。生成をスキップします。")
        return

    key = os.environ.get("GITHUB_TOKEN")
    if not key:
        sys.exit("GITHUB_TOKEN がありません（GitHub Actions 上で実行してください）。")

    theme = os.environ.get("POST_THEME") or "Web制作"
    weekday = "月火水木金土日"[dt.date.fromisoformat(date).weekday()]
    past = recent_posts()
    user = f"今日は {date}（{weekday}曜日）です。\n"
    user += ("以下は最近の投稿です。トピックや書き出しが重複しないようにしてください。\n\n" + past) if past else "これが最初の投稿です。"

    models = [os.environ["AI_MODEL"]] if os.environ.get("AI_MODEL") else DEFAULT_MODELS
    text, last_err = "", None
    for m in models:
        try:
            text = call_model(key, m, SYSTEM.format(theme=theme), user)
            print(f"モデル {m} で作成しました。")
            break
        except RuntimeError as e:
            last_err = str(e)
            print("失敗:\n" + last_err)
    if not text:
        sys.exit(f"投稿文を作成できませんでした。{last_err}")

    if len(text) > 2900:
        text = text[:2900]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(f"--- {date} ---\n{text}")


if __name__ == "__main__":
    main()
