# mozc4med パッチ集

このディレクトリは、Google [Mozc](https://github.com/google/mozc) のコードベースを
"**mozc4med**" としてリブランディングするためのカスタマイズ一式です。`src/` は
下記の Track B の方針により直接変更せず、すべて `.patch` ファイル
またはビルド時マージ（Track C）として保持しています。

このファイルは Phase の切れ目ごとに「何を変えたか / 何を意図的に変えていないか /
非目標としているもの / リリース前に確認すべきこと」を1つの表として管理するための
ドキュメントです（構成は [Mozkey](https://github.com/koyasi777/mozkey) の
[`docs/rename-to-mozkey-v0.7.0.md`](https://github.com/koyasi777/mozkey/blob/main/docs/rename-to-mozkey-v0.7.0.md)
に倣っています）。

## Track A / Track B / Track C

| Track | 対象 | 方法 |
| :--- | :--- | :--- |
| A: Infrastructure | `.github/workflows/*.yaml` | 直接コミット |
| B: Source Rebranding | `src/` 配下のソース | `mozc4med/{common,windows,mac,linux,android,lint}/*.patch` |
| C: Build-Time Data Merge | ビルド時に素読みされる単純な行指向データ | `mozc4med/tool/*.py` が CI ランナーの作業コピーを直接編集（コミットしない） |

---

## 変えるもの（Changed）

### ブランディング文字列・メタデータ（common/, windows/）
- 製品名／プレフィックス: `Mozc` → `Mozc4med`（`kProductNameInEnglish`,
  `kProductPrefix` ほか, `common/0001_brand_isolation.patch`）
- 会社名表示: `Mozc Project` → `Mozc Project, MATANUKI`
  （`kCompanyNameInEnglish`, `common/0001_brand_isolation.patch`）
- Qt GUI 文字列（About ダイアログ製品名・URL・著作権表示、ヘルプ/クレジットページ、
  `tr_ja.qtts`）: `common/0006_gui_branding.patch`
- Windows バージョンリソース（ProductName / CompanyName / LegalCopyright）:
  `windows/0001_win32_resource_template.patch`
- Windows インストーラ（製品名・Manufacturer・メッセージ文言）:
  `windows/0002_win32_installer_rebranding.patch`
- Windows MSI 出力ファイル名: `windows/0003_win32_msi_filename.patch`
- TIP / カスタムアクション / キャッシュサービス / レンダラーの `.rc` リソース
  （製品名・会社名・著作権表示）:
  `windows/0004`〜`windows/0007_*_resource_rebranding.patch`
- Windows 製品アイコン（`.ico`）と About ダイアログ / Unix 側で共有される
  `product_icon_32bpp-128.png`: `mozc4med/tool/hue_shift_svg.py`
  （`icon.svg`/`icon_base.svg` の色相を赤へシフト）→
  `generate_icon_from_svg.py`（そのSVGから `.ico` を再生成。`--png-out`/`--png-size`
  で同じレンダリングを `product_icon_32bpp-128.png` にも保存 — これが
  `about_dialog.qrc` 経由で About ダイアログのロゴに、`src/unix/build_icons.py`
  経由で Linux の `mozc.png` になる）→ `colorize_icons.py`（SVG化されていない
  残りの `.ico` をファジーカラーマッチで着色）。いずれも CI 作業コピーへの
  ビルド時マージ（Track C 相当）で、`.patch` 化していない。
  `windows-mozc4med.yaml` でのみ配線されており、macOS/Linux 向けワークフローの
  アイコンはまだこのパイプラインの対象外（[非目標](#非目標non-goals)参照）

### データパス・IPC・レジストリの分離（Phase 2 先行実施分）
CLAUDE.md では Phase 2 の作業とされているが、`common/0001`/`0002` の時点で
以下はすでに mozc4med 専用の値に切り替え済み:
- レジストリキー: `Software\Mozc Project\Mozc` → `Software\MATANUKI\Mozc4med`
- IPC 名前付きパイプ: `\\.\pipe\mozc.` → `\\.\pipe\mozc4med.`
- Mutex / Event プレフィックス: `Local\Mozc.{mutex,event}.` →
  `Local\Mozc4med.{mutex,event}.`
- ウィンドウクラス名: `Mozc{Candidate,Composition,Indicator,Infolist}Window`,
  `MozcUIWindow` → `Mozc4med...` 各種
- Windows TSF/COM の CLSID・IID: `windows/0008_windows_guid_refresh.patch` で
  本家 Mozc の値から全面刷新（本家 Mozc と同一 GUID を共存させると TSF 登録が
  衝突するため）
- Unix: `MOZC_IBUS_INSTALL_DIR` を `/usr/share/ibus-mozc4med` に変更
  （`common/0004_ibus_install_path.patch`）

これらが本当に衝突しないことは `mozc4med/tool/check_no_upstream_identifiers.py`
で検証する（[検証チェックリスト](#検証チェックリストvalidation-checklist)参照）。

### 辞書・コロケーションデータ（Track C, `mozc4med/tool/`）
- `dictionary_oss/dictionary*.txt` の重複エントリ削除:
  `rm_dictionary_entries.py`（mozc4med.tsv と重複する行を CI 作業コピーから除去）
- `collocation.txt` / `collocation_suppression.txt` への追記:
  `append_collocation_entries.py`
- いずれもコミットされる `.patch` は生成せず、CI ランナーの作業コピーのみを書き換える
  （CLAUDE.md 3.7）

### CI/CD（Track A）
- `windows-mozc4med.yaml`: トリガーを `workflow_dispatch` に変更し、パッチ適用
  ステップ（`git apply --check` → `git apply`）と Track C ステップを追加

---

## 意図的に変えないもの（Intentionally kept）

- **インストール先ディレクトリ**: `C:\Program Files (x86)\Mozc`
  （変更すると Phase 2 の共存要件と衝突するため、共存レイアウトが固まるまで保留）
- **バイナリ/DLL ファイル名**: `mozc_server.exe`, `mozc_tool.exe`,
  `mozc_tip32.dll`, `mozc_tip64.dll`, `mozc_broker.exe`, `mozc_renderer.exe`,
  `mozc_cache_service.exe`, `mozc_ja.ime` は Phase 1 では変更しない
  （CLAUDE.md Phase 1 の明示的な Note）。
  `mozc4med/tool/check_no_upstream_identifiers.py` はこれらをハードエラーにせず
  REPORT_ONLY として扱う。
- **Bazel 内部ターゲット名・C++ 名前空間 (`mozc::`)**: Phase 1/2 とも対象外
- **MSI UpgradeCode / MSI コンポーネント・ディレクトリ識別子**: 既存インストールの
  アップグレード互換性を壊さないよう現状維持（変更する場合は将来の明示的な決定が必要）
- **ライセンス表記中の "Mozc" という語自体**: `credits_en.html` は
  "mozc4med is based on Mozc, which is licensed as follows:" のように、
  Google LLC への帰属を保ったまま製品名だけを置き換える
  （`common/0006_gui_branding.patch`）

## 非目標（Non-goals）

- **Phase 1 時点でのソースレベル完全リネーム**: コメント・テストデータ・upstream
  参照からの "Mozc" 文言の全除去はしない
- **バイナリファイル名・インストールディレクトリのリネーム**: Phase 2 の
  "Refactoring" 項目として先送り
- **Windows 以外のワークフローの Track A 移行**: `android.yaml` / `lint.yaml` /
  `linux.yaml` / `macos.yaml` / `windows.yaml`（無印）は本書時点で未着手。
  `workflow_dispatch` 化・パッチ適用ステップの追加は `windows-mozc4med.yaml` のみ
- **`mac/` / `linux/` / `android/` / `lint/` パッチカテゴリ**: CLAUDE.md
  上は定義済みだが、本書時点で該当ディレクトリ・パッチは未作成
  （macOS の GUI 文字列 `tweak_info_plist_strings.py` / `Config.xib` はまだ
  "Mozc" のまま）

---

## 検証チェックリスト（Validation checklist）

CI（`windows-mozc4med.yaml` の `test` ジョブ）およびリリース前に確認する項目:

- [ ] `mozc4med/tool/validate_and_apply_patches.py mozc4med/common mozc4med/windows`
      が exit 0 で終わる（メタデータ検証・overlap 検出・順序付き `--check`・最終
      apply）
- [ ] `rm_dictionary_entries.py` / `append_collocation_entries.py` の
      `--step-summary` に想定外の大量削除・追加がない
- [ ] `mozc4med/tool/compare_evaluation_quality.py --before .../evaluation.tsv
      --after .../evaluation_updated.tsv` に **regression（OK→FAILED）が 0 件**
      （辞書編集後の変換品質劣化がないことの確認。運用方法は
      [`tool/compare_evaluation_quality.py`](tool/compare_evaluation_quality.py)
      のモジュール docstring を参照）
- [ ] `mozc4med/tool/check_no_upstream_identifiers.py` が
      built binary（`mozc_tip32.dll` / `mozc_tip64.dll` / `mozc_server.exe` /
      `mozc_cache_service.exe` / `mozc_renderer.exe`）に対して PASS
      （本家 Mozc のレジストリキー・IPC 名・旧 CLSID が残っていないことの確認）
- [ ] MSI が正常にビルドされる
- [ ] MSI の administrative extract が成功する
- [ ] IME 一覧に "Mozc4med" と表示される
- [ ] About ダイアログの製品名・著作権表示が mozc4med 用になっている
- [ ] 設定ダイアログ・辞書ツールが正常に開く
- [ ] 通常変換・ライブ変換が動作する
- [ ] クリーンインストール・アンインストールが成功する
- [ ] 本家 Mozc（別インストール）と Side-by-Side で共存できる
      （レジストリキー・IPC 名・TSF CLSID が衝突しないこと。
      Phase 2 で正式な共存検証手順に格上げ予定）

---

## ディレクトリ構成

- `common/` … Linux/macOS/Windows 共通の Track B パッチ
- `windows/` … Windows 専用の Track B パッチ
- `tool/` … Track A/C 補助ツール（辞書編集、コロケーション追記、アイコン生成、
  評価品質比較、アップストリーム識別子衝突チェック、パッチ検証）
- `mac/` / `linux/` / `android/` / `lint/` … CLAUDE.md 上定義済みだが未作成
  （[非目標](#非目標non-goals)参照）
- 本リポジトリの `README.md` / `CHANGELOG.md` はトップレベルにあるが、mozc4med
  固有の情報は本ファイルと `ChangeLog-mozc4med.md` に記載する

## 使い方

1. パッチを適用する前に内容を確認する:
   ```bash
   git apply --check mozc4med/common/0001_brand_isolation.patch
   ```
2. カテゴリ内のパッチはインデックス順に、まず全件 `--check` してから適用する
   （CLAUDE.md 3.6 / `mozc4med/tool/validate_and_apply_patches.py` 参照）:
   ```bash
   python mozc4med/tool/validate_and_apply_patches.py mozc4med/common mozc4med/windows
   ```
3. 必要に応じて `git commit` する。
