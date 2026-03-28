# Mozc4med パッチ集

このディレクトリは Mozc のコードベースに対するカスタマイズパッチをまとめたものです。

## 主な目的
- 再ブランディング（製品名・インストールパスの変更）
- Linux/macOS 向け共通パッチ (`common/`)
- Windows 向けパッチ (`windows/`)
- 補助ツール (`tool/`)

## 使い方
1. パッチを適用する前に内容を確認します。
   ```bash
   git apply --check mozc4med/common/0005_ibus_install_path.patch
   ```
2. 問題なければ適用します。
   ```bash
   git apply mozc4med/common/0005_ibus_install_path.patch
   ```
3. 必要に応じて `git commit` してください。

## ディレクトリ構成
- `common/` … Linux/macOS 共通パッチ
- `windows/` … Windows 用パッチ
- `tool/` … 補助ツール
- `README.md`・`CHANGELOG.md` は本リポジトリのトップレベルにありますが、Mozc4med 固有情報はこのファイルに記載しています。
