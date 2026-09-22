# BASE APIショップ自動運用 - 認証編

BASE APIを使ってショップを自動運用するための第一歩、「認証（アクセストークンの取得と自動更新）」の仕組みです。

## できること

- ブラウザで表示される認可コードを手入力して、初回のアクセストークンを取得する
- アクセストークンが切れたら、リフレッシュトークンで自動更新する
- ショップ情報を取得して、認証が成功したことを確認する

`client_secret` やトークンはすべて `.env` ファイルに保存され、コードには直接書きません。`.env` は `.gitignore` で除外されているので、Gitにコミットされません。

## 事前準備

- Python 3.9以上が入っていること（ターミナルで `python3 --version` を実行して確認）
- BASE Developersでアプリ登録済み、`client_id` と `client_secret` を取得済みであること
- コールバックURLが `https://tkt.base.ec/` に設定されていること

## 手順

### 1. このフォルダに移動して、仮想環境を作る

```bash
cd base-shop-automation
python3 -m venv venv
```

仮想環境を有効化します。

```bash
# Mac / Linux の場合
source venv/bin/activate

# Windows (コマンドプロンプト) の場合
venv\Scripts\activate.bat

# Windows (PowerShell) の場合
venv\Scripts\Activate.ps1
```

ターミナルの行頭に `(venv)` と表示されれば成功です。

### 2. 必要なライブラリをインストールする

```bash
pip install -r requirements.txt
```

`requests`（BASE APIへの通信用）と `python-dotenv`（`.env`ファイルの読み書き用）がインストールされます。

### 3. `.env` ファイルを作る

サンプルファイルをコピーします。

```bash
cp .env.example .env
```

`.env` をエディタで開いて、以下の項目を埋めてください（あなた自身で入力する部分です）。

```
BASE_CLIENT_ID=（BASE Developersで発行されたclient_id）
BASE_CLIENT_SECRET=（BASE Developersで発行されたclient_secret）
BASE_REDIRECT_URI=https://tkt.base.ec/
BASE_SCOPE=read_items,write_items,read_orders,write_orders,read_users
```

`BASE_ACCESS_TOKEN` などそれより下の項目は空のままでOKです。次のステップでスクリプトが自動的に書き込みます。

> `BASE_SCOPE` の区切り文字（カンマ）は一般的なBASE APIの仕様に基づいたものです。もし次の手順で認可画面にエラーが出る場合は、BASE Developersのアプリ設定画面で許可されているスコープの表記を確認し、`.env` の `BASE_SCOPE` を実際の表記に合わせて書き換えてください。

### 4. 認証スクリプトを実行する

```bash
python auth.py
```

ターミナルに認可用のURLが表示されます。

### 5. ブラウザで認可する

1. ターミナルに表示されたURLをコピーして、ブラウザのアドレス欄に貼り付けて開きます。
2. BASEのログイン画面が出たら、ショップのアカウントでログインします。
3. 「アプリを連携しますか？」のような確認画面が出るので、内容を確認して「許可する」を選びます。
4. 許可すると、ブラウザは `https://tkt.base.ec/` に移動します（真っ白なページや、何も表示されないページになるかもしれませんが問題ありません）。
5. その状態のまま、**ブラウザのアドレス欄に表示されているURL全体をコピー**してください。

   ```
   例: https://tkt.base.ec/?code=xxxxxxxxxxxxxxxx&scope=read_items,...
   ```

### 6. ターミナルにコードを貼り付ける

ターミナルに戻り、

```
4. コピーしたURL（またはcodeの値だけ）を貼り付けてEnter:
```

と表示されているので、先ほどコピーしたURL（またはURL中の `code=` の後ろの値だけでもOK）を貼り付けてEnterを押します。

### 7. 結果を確認する

成功すると、以下のように表示されます。

```
トークンを取得しています...
トークンを取得し、.env に保存しました。

ショップ情報を取得して、認証が成功したか確認します...

=== 認証成功 ===
{'shop_id': ..., 'shop_name': ..., ...}
```

ショップ情報（ショップ名など）が表示されれば、認証は成功です。取得したアクセストークンとリフレッシュトークンは `.env` に自動保存されています。

## 2回目以降の実行について

`.env` にアクセストークンが保存されていれば、`python auth.py` を再実行してもブラウザでの認可は不要です。アクセストークンの期限が切れていた場合は、リフレッシュトークンを使って自動的に更新され、`.env` も自動で上書きされます。

他のスクリプト（今後作る「注文取得」「商品登録」「発送済み更新」など）からは、以下のようにインポートするだけで、常に有効なアクセストークンを取得できます。

```python
from auth import get_access_token

token = get_access_token()
```

## トラブルシューティング

- `.envファイルが見つかりません` と出た場合 → 手順3で `.env` を作り忘れています。
- 認可画面でエラーになる場合 → `.env` の `BASE_CLIENT_ID` / `BASE_REDIRECT_URI` が、BASE Developers側の登録内容と完全に一致しているか確認してください。
- トークン取得時に `400` エラーが出る場合 → `.env` の `BASE_CLIENT_SECRET` が正しいか、コールバックURLが一致しているかを確認してください。

## 次のステップ

このあと、「2. 注文の取得」「3. 商品の登録」「4. 発送済みへの更新」を順番に作っていきます。それぞれ `get_access_token()` を使って、同じ `.env` の認証情報をそのまま利用できます。
