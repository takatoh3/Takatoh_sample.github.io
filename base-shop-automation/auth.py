"""BASE APIの認証まわり（アクセストークン取得・自動更新）を担当するモジュール。

他のスクリプト（注文取得・商品登録など）からは
    from auth import get_access_token
    token = get_access_token()
だけ呼べば、必要なら自動でリフレッシュされた有効なアクセストークンが返ります。

このファイル単体を実行すると、初回の認可コード入力〜トークン取得〜
ショップ情報取得による疎通確認までを行います。
    python auth.py
"""

import time
import urllib.parse
from pathlib import Path

import requests
from dotenv import load_dotenv, set_key

ENV_PATH = Path(__file__).parent / ".env"

AUTHORIZE_URL = "https://api.thebase.in/1/oauth/authorize"
TOKEN_URL = "https://api.thebase.in/1/oauth/token"
USER_INFO_URL = "https://api.thebase.in/1/user/info"

# アクセストークンの期限切れ判定に使う余裕時間（秒）
EXPIRY_BUFFER_SECONDS = 60


def _env(key, default=""):
    load_dotenv(ENV_PATH, override=True)
    import os

    return os.environ.get(key, default)


def _save_tokens(access_token, refresh_token, expires_in):
    if not ENV_PATH.exists():
        raise FileNotFoundError(
            f".envファイルが見つかりません: {ENV_PATH}\n"
            ".env.example をコピーして .env を作成し、client_id等を入力してください。"
        )
    expires_at = str(int(time.time()) + int(expires_in))
    set_key(str(ENV_PATH), "BASE_ACCESS_TOKEN", access_token)
    set_key(str(ENV_PATH), "BASE_REFRESH_TOKEN", refresh_token)
    set_key(str(ENV_PATH), "BASE_TOKEN_EXPIRES_AT", expires_at)


def build_authorization_url():
    """ブラウザで開くための認可URLを作る。"""
    client_id = _env("BASE_CLIENT_ID")
    redirect_uri = _env("BASE_REDIRECT_URI")
    scope = _env("BASE_SCOPE")

    if not client_id or not redirect_uri:
        raise ValueError(
            ".env に BASE_CLIENT_ID / BASE_REDIRECT_URI が設定されていません。"
        )

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
    }
    return f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"


def exchange_code_for_token(code):
    """認可コードをアクセストークン・リフレッシュトークンに交換し、.envに保存する。"""
    client_id = _env("BASE_CLIENT_ID")
    client_secret = _env("BASE_CLIENT_SECRET")
    redirect_uri = _env("BASE_REDIRECT_URI")

    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
        },
    )
    response.raise_for_status()
    payload = response.json()

    _save_tokens(
        access_token=payload["access_token"],
        refresh_token=payload["refresh_token"],
        expires_in=payload.get("expires_in", 3600),
    )
    return payload


def refresh_access_token():
    """保存済みのリフレッシュトークンを使ってアクセストークンを更新し、.envに保存する。"""
    client_id = _env("BASE_CLIENT_ID")
    client_secret = _env("BASE_CLIENT_SECRET")
    refresh_token = _env("BASE_REFRESH_TOKEN")

    if not refresh_token:
        raise RuntimeError(
            "リフレッシュトークンがありません。先に python auth.py を実行して"
            "初回認証を行ってください。"
        )

    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        },
    )
    response.raise_for_status()
    payload = response.json()

    # BASEがリフレッシュトークンを新しく発行しない場合は、既存のものを使い続ける
    new_refresh_token = payload.get("refresh_token", refresh_token)

    _save_tokens(
        access_token=payload["access_token"],
        refresh_token=new_refresh_token,
        expires_in=payload.get("expires_in", 3600),
    )
    return payload


def get_access_token():
    """有効なアクセストークンを返す。期限切れなら自動でリフレッシュする。"""
    access_token = _env("BASE_ACCESS_TOKEN")
    expires_at = _env("BASE_TOKEN_EXPIRES_AT")

    if not access_token:
        raise RuntimeError(
            "アクセストークンがまだありません。先に python auth.py を実行して"
            "初回認証を行ってください。"
        )

    if not expires_at or time.time() > int(expires_at) - EXPIRY_BUFFER_SECONDS:
        refresh_access_token()
        access_token = _env("BASE_ACCESS_TOKEN")

    return access_token


def get_shop_info():
    """ショップ情報を取得する（認証成功の確認に使う）。"""
    token = get_access_token()
    response = requests.get(
        USER_INFO_URL,
        headers={"Authorization": f"Bearer {token}"},
    )
    response.raise_for_status()
    return response.json()


def _run_first_time_auth_flow():
    print("=== BASE API 初回認証 ===")
    print()
    print("1. 以下のURLをブラウザで開いてください。")
    print()
    print(build_authorization_url())
    print()
    print("2. BASEショップにログインし、アプリの連携を「許可」してください。")
    print(
        "3. 許可すると、ブラウザは https://tkt.base.ec/ に飛びます"
        "（何も表示されないページかもしれません）。"
    )
    print(
        "   その状態のまま、ブラウザのアドレス欄のURL全体をコピーしてください。"
    )
    print("   例: https://tkt.base.ec/?code=xxxxxxxxxx&scope=read_items,...")
    print()
    pasted = input("4. コピーしたURL（またはcodeの値だけ）を貼り付けてEnter: ").strip()

    code = _extract_code(pasted)

    print()
    print("トークンを取得しています...")
    exchange_code_for_token(code)
    print("トークンを取得し、.env に保存しました。")


def _extract_code(pasted_text):
    """アドレス欄からコピーした文字列（URL全体でもcodeの値だけでも）からcodeを取り出す。"""
    if "code=" in pasted_text:
        parsed = urllib.parse.urlparse(pasted_text)
        query = urllib.parse.parse_qs(parsed.query)
        if "code" in query:
            return query["code"][0]
    return pasted_text


def main():
    access_token = _env("BASE_ACCESS_TOKEN")
    if not access_token:
        _run_first_time_auth_flow()
    else:
        print(".env に既存のアクセストークンが見つかりました。")
        print("期限切れの場合は自動でリフレッシュされます。")

    print()
    print("ショップ情報を取得して、認証が成功したか確認します...")
    shop_info = get_shop_info()
    print()
    print("=== 認証成功 ===")
    print(shop_info)


if __name__ == "__main__":
    main()
