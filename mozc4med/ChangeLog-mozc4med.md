# 変更履歴 (Mozc4med)

パッチ名は現在のファイル名に合わせています。各パッチの依存関係と対象ファイルは、
パッチ先頭のヘッダ (`Depends-On` / `Touch-Files` / `Scope`) を参照してください。
Phase ごとの方針は `readme-mozc4med.md` にあります。

## 2026‑11‑21
- Windows用LLVM依存関係を23.1.6に更新するパッチを追加
  - Visual Studio 2026のMSVC標準ライブラリが要求するClang 22以上に対応
  - Windows x64/ARM64の依存定義とWindowsビルド手順を更新
- 製品アイコンを独自デザインに変更
  - `assets/icon.svg` を追加 (緑・赤・青の 3 つの円。背景は透過)
  - `windows-mozc4med.yaml` (`build_x64` / `build_arm64`) に「Install mozc4med icon SVGs」ステップを追加し、
    CI 作業コピーの `src/data/images/icon.svg` と `icon_base.svg` (言語バー用) を上書き (コミットしない)
  - `hue_shift_svg.py` と `colorize_icons.py` のステップを削除 (ツール自体は残してある)
  - `product_icon.ico` / `product_icon_langbar.ico` はどちらも新 SVG から生成される
  - 残りの `src/data/images/win/*.ico` は `tool/generate_win_mode_icons.py` で生成
    (`*_a.ico` は 8 サイズ、それ以外は 16x16 のみ)
    - 入力モード表示 (`ms_hiragana` / `ms_katakana` / `ms_katakana_half` / `ms_alpha` /
      `ms_alpha_half` / `ms_direct_input`): 上流の `ms_*.svg` の文字を三つの円に重ねる
      (24px 以下は文字を全面に出し、円を薄くする)
    - `ms_disabled*`: 円をグレーにしたもの
    - `tools_*`: 上流に文字 SVG がないため円のみ
  - `tool/generate_icon_from_svg.py` に `--sizes` オプションを追加 (テストも追加)

## 2026‑09‑28
- `common/0007_disable_half_width_katakana_variant.patch` (Scope: candidate-filtering)
  - 変換候補から半角カタカナを除外する (`variants_rewriter.cc`)
  - あわせて `variants_rewriter_test.cc` の期待値を更新
    (`RewriteForMixedConversion` / `RewriteForSuggestion` を含む)
  - 注意: ブランディングではなく挙動変更のため、Phase 1 の範囲に含めるかは要確認

## 2026‑09‑25
- `tool/check_no_upstream_identifiers.py` を追加 (Track A の CI ゲート)
  - ビルド済みバイナリに上流 Mozc のレジストリキー / IPC プレフィックス /
    ミューテックス・イベント接頭辞 / ウィンドウクラス名 / 旧 CLSID が残っていないことを検査
  - `build_x64` / `build_arm64` の MSI アップロード前に実行
- `tool/compare_evaluation_quality.py` を追加 (Track C)
  - `evaluation.tsv` を、リグレッションがない場合に限り Bazel 生成物で同期
  - `test` ジョブのみに組み込み
- `windows/0008_windows_guid_refresh.patch` (Scope: coexistence-guid, branding-string)
  - TSF / COM の CLSID・GUID を刷新し、オリジナル Mozc との共存に備える
  - `kHelpUrl` が仮置きの URL を指していた問題を同パッチ内で修正
- About ダイアログのロゴを、色を変えたアイコンに差し替え
  (`tool/generate_icon_from_svg.py` を更新)

## 2026‑09‑22
- `common/0006_gui_branding.patch` (Scope: branding-string)
  - About ダイアログ、`credits_en.html`、GUI の翻訳文字列 (`*.qtts`)、
    `gui/base/util.cc` の表示名を mozc4med に変更

## 2026‑09‑20
- `tool/rm_dictionary_entries.py` を追加 (Track C): `dictionary*.txt` の重複エントリ削除
- `tool/append_collocation_entries.py` を追加 (Track C):
  `collocation.txt` / `collocation_suppression.txt` へのカスタムエントリ追記
- `windows-mozc4med.yaml` に上記 2 ツールを組み込み
  (`build_*` は `--apply` のみ、`test` はログ・レポート・ステップサマリ付き)

## 2026‑09‑19
- `common/0005_dictionary_oss_mozc4med_tsv.patch` (Scope: build-metadata)
  - `dictionary_manual` / `dictionary_oss` の `BUILD.bazel` に mozc4med 用 TSV を追加
- `tool/generate_mozc4med_dictionary.py` を追加
- 辞書パッチの配線を検証する回帰テストを追加

## 2026‑07‑19
- アイコン生成ツールを追加
  (`tool/colorize_icons.py`, `tool/hue_shift_svg.py`, `tool/generate_icon_from_svg.py`)

## 2026‑07‑15
- `common/0002_path_isolation.patch` を更新 (`system_util.cc` のユーザープロファイル等のパス分離)
- `windows/0002_win32_installer_rebranding.patch`、
  `windows/0003_win32_msi_filename.patch` を更新

## 2026‑04‑02
- `tool/validate_and_apply_patches.py` を更新
  (メタデータ検査、`Touch-Files` の重複検査、インデックス順の `--check`)

## 2026‑03‑29
- `windows/0008_windows_guid_refresh.patch` の初版

## 2026‑03‑28
- `windows/0005_custom_action_resource_rebranding.patch`:
  カスタムアクション DLL のリソース文字列を変更
- `windows/0006_cache_service_resource_rebranding.patch`:
  キャッシュサービスのリソース文字列を変更
- `windows/0007_renderer_resource_rebranding.patch`:
  レンダラーのリソース文字列を変更

## 2026‑03‑27
- `common/0003_version_rewriter_test.patch`:
  `version_rewriter_test.cc` の期待バージョン文字列を `Mozc4med-` に更新
- `common/0004_ibus_install_path.patch`:
  ibus の `path_util.cc` のインストール先を mozc4med 用に変更
- `windows/0004_tip_resource_rebranding.patch`: TSF TIP のリソース文字列を変更
- `common/0001_brand_isolation.patch` を更新 (`base/const.h` のブランド名・パス・IPC 名など)
- `tool/validate_and_apply_patches.py` の初版

## 2026‑03‑25
- `windows/0003_win32_msi_filename.patch`: MSI のファイル名を変更

## 2026‑03‑24
- `common/0001_brand_isolation.patch` の初版 (Scope: path-isolation)
- `common/0002_path_isolation.patch` の初版
- `windows/0001_win32_resource_template.patch`: Win32 リソーステンプレートの製品名等を変更
- `windows/0002_win32_installer_rebranding.patch`:
  インストーラ (`build_installer.py`, `installer_oss_64bit.wxs`) の製品名・製造元を変更
- `windows-mozc4med.yaml` の初版
