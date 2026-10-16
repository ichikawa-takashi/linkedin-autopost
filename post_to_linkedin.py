#!/usr/bin/env python3
"""posts/YYYY-MM-DD.md（日本時間の今日）を LinkedIn に投稿する。

環境変数:
  LINKEDIN_ACCESS_TOKEN  必須。scope: openid profile w_member_social
  LINKEDIN_PERSON_URN    任意。未設定なら /v2/userinfo から取得
  POST_DATE              任意。YYYY-MM-DD（手動実行で日付を指定したい場合）
  DRY_RUN                任意。"1" なら投稿せず内容だけ表示
"""
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.request

JST = dt.timezone(dt.timedelta(hours=9))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESERVED = r"\|{}@[]()<>#*_~"


def api_version() -> str:
    # LinkedIn API のバージョン(YYYYMM)は約1年で廃止されるため、2か月前の月を自動で使う
    override = os.environ.get("LINKEDIN_VERSION")
    if override:
        return override
    d = dt.datetime.now(JST).date().replace(day=1)
    for _ in range(2):
        d = (d - dt.timedelta(days=1)).replace(day=1)
    return d.strftime("%Y%m")


def to_little_text(text: str) -> str:
    """Posts API の commentary 形式に変換（予約文字をエスケープし、#タグをハッシュタグ化）。"""
    out = []
    for line in text.split("\n"):
        parts = re.split(r"(#[^\s#　、。,.!?！？]+)", line)
        buf = []
        for p in parts:
            if p.startswith("#") and len(p) > 1:
                tag = "".join("\\" + c if c in RESERVED else c for c in p[1:])
                buf.append("{hashtag|\\#|" + tag + "}")
            else:
                buf.append("".join("\\" + c if c in RESERVED else c for c in p))
        out.append("".join(buf))
    return "\n".join(out)


def request(method, url, token, body=None):
    headers = {
        "Authorization": f"Bearer {token}",
        "LinkedIn-Version": api_version(),
        "X-Restli-Protocol-Version": "2.0.0",
    }
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, dict(r.headers), r.read().decode() or "{}"
    except urllib.error.HTTPError as e:
        msg = e.read().decode()
        if e.code == 401:
            msg += "\n→ アクセストークンの期限切れの可能性があります（60日ごとに再発行が必要）。README の手順で更新してください。"
        sys.exit(f"LinkedIn API エラー {e.code}: {msg}")


def main():
    date = os.environ.get("POST_DATE") or dt.datetime.now(JST).strftime("%Y-%m-%d")
    post_path = os.path.join(ROOT, "posts", f"{date}.md")
    marker = os.path.join(ROOT, "posted", f"{date}.json")

    if not os.path.exists(post_path):
        print(f"{date} の投稿ファイルがありません。スキップします。")
        return
    if os.path.exists(marker):
        print(f"{date} は投稿済みです。スキップします。")
        return

    text = open(post_path, encoding="utf-8").read().strip()
    if not text:
        sys.exit("投稿ファイルが空です。")
    if len(text) > 3000:
        sys.exit(f"本文が {len(text)} 文字あり、LinkedIn の上限(3000)を超えています。")

    if os.environ.get("DRY_RUN") == "1":
        print("--- DRY RUN ---\n" + to_little_text(text))
        return

    token = os.environ.get("LINKEDIN_ACCESS_TOKEN")
    if not token:
        sys.exit("LINKEDIN_ACCESS_TOKEN が設定されていません。")

    author = os.environ.get("LINKEDIN_PERSON_URN")
    if not author:
        _, _, body = request("GET", "https://api.linkedin.com/v2/userinfo", token)
        author = "urn:li:person:" + json.loads(body)["sub"]

    payload = {
        "author": author,
        "commentary": to_little_text(text),
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    status, headers, _ = request("POST", "https://api.linkedin.com/rest/posts", token, payload)
    post_id = headers.get("x-restli-id") or headers.get("X-RestLi-Id") or ""
    print(f"投稿しました: status={status} id={post_id}")

    os.makedirs(os.path.dirname(marker), exist_ok=True)
    with open(marker, "w", encoding="utf-8") as f:
        json.dump({"date": date, "post_id": post_id,
                   "posted_at": dt.datetime.now(JST).isoformat()}, f, ensure_ascii=False)


if __name__ == "__main__":
    main()
