# UTF-8中心／Unicode最小構成・source-only PoC（#1434）

**これはprofile3の完成品ではありません。** 現在のprofile2、release/配布フラグ、Core、Pagesは一切変更しない調査用実装です。最終WASMの構築・配布適法性を示すものではありません。

## 契約

- 外部テキストはUTF-8のみ。PythonのUnicode文字列自体は従来どおり日本語・韓国語・中国語・絵文字を保持する。
- 内部用に残す候補codec：\`ascii\`, \`latin_1\`, \`utf_8\`, \`utf_8_sig\`, \`utf_16\`とBE/LE, \`utf_32\`とBE/LE, \`unicode_escape\`, \`raw_unicode_escape\`, \`idna\`, \`punycode\`, \`charmap\`, \`undefined\`, \`encodings/__init__\`, \`aliases\`。あくまで**起動・依存未検証の仮のallowlist**。
- 標準ライブラリの \`base64_codec\`・\`bz2_codec\` 等もPoCでは除外。Pyodide起動やCoreの依存が必要とする場合は正式実装前に最小限復元する。
- UTF-7を含め従来型のコーデックとCJK由来mappingは除去候補とする。UTF-8入力の仕様は維持。Unicode UCD等の別ライセンスは残る。

## 実装

\`unicode_minimal.py\` は**既にhash検証されたHKSCS-free CPython 3.14.2 source archive**を受け取り、別パスのdeterministic tar.gzにソース候補を出力する。元ファイルは上書きしない。

除外範囲：
- \`Modules/cjkcodecs/\` 全体（\`_codecs_cn\`, \`_codecs_jp\`, \`_codecs_kr\`, \`_codecs_tw\`, \`_codecs_iso2022\`, \`multibytecodec\`, GB18030生成Cヘッダ）。
- \`Tools/unicode/python-mappings/\` 全体（ICUの元GB18030 XML、GB2312、JIS X 0213等のmapping入力）。この出典群がすべてのUnicode入力を代表するとは主張しない。
- allowlist外の \`Lib/encodings/*.py\`（GB18030/GBK/Shift_JIS等）。\`aliases\`から除去codecへの別名も削る。

入力検証：必須の元ソースmemberが存在、symlink/非regular/重複/不正pathを拒否、既存出力を拒否、alias辞書形式を検証。元アーカイブのSHAは呼出側が固定lockと照合。レポートにhash、残存/除去ファイル数、除去パス集合のdigestを含む。

実行例：

\`\`\`sh
python -m contrib.browser_check_poc.unicode_minimal \
  /private/verified-profile2/cpython-source.tar.gz \
  .cache/unicode-minimal-cpython-source.tar.gz
python -m unittest tests.test_unicode_minimal
\`\`\`

## 2026-10-26 実測（隔離環境）

元のPR #1428 checker archiveの内部にあったHKSCS-free CPython sourceを使用。元source SHA-256：
\`f862710e3d61091aae013d486d8bedbf1074188fd98086572d6340ec60b5392c\`

PoC生成source SHA-256：
\`eb80e7df3c4a4190ec5b83c72e231fbba33dc299a442ce6743ea03a54dea5619\`

**削除130ファイル／保持4927ファイル、候補codec18ファイル**。除去名一覧のSHA-256：
\`2d992f949d6af6350deb923e9a97a95687f6af902da6e3326796ff91b2ea97f8\`

Synthetic focused tests: **4 PASS**（CJK/ICU source・alias削除、必須入力欠損拒否、symlink拒否、既存出力拒否、deterministic hash）。

これは **source-only PASS**。次はすべて**NOT RUN**：Pyodide SDKでのconfigure/compile、\`Setup.local\`でのCJK builtin/\`_multibytecodec\`の無効化、build/objectの除去確認、stdlib/WASMの負試験、Python/JSON/encodingの実動作、life.txt parser parity、Node/Chromium/browser、実メモリ、独立レビュー、全ライセンス。

## 次段階：専用profile3 runtime（別Issue）

1. 新source recipeとprofile3固定hashを定義。既存profile2・source pins・lockを絶対に上書きしない。
2. Pyodide \`cpython/Setup.local\`のCJK builtinと\`_multibytecodec\`を無効化し、不要CJK object/生成表を再ビルドから除外。実際のCPython/stdlib依存に必要な内部codecを実検査してkeep listを調整。
3. 固定SDKによる実WASMビルド、source/object/stdlib/WASMと対応ソース10archiveのhash/notice束縛。GB18030/HKSCS/JIS/GB2312の実データ混入を独立否定。
4. 正試験：UTF-8、日本語/絵文字、Python import・JSON・datetime・life.txt Core、JA/EN 16KiB/100診断・キャンセル/復旧/Privacy/no-script。負試験：GB18030、GBK、Shift_JIS、Big5/HKSCS、他除外codecはLookupError等となること。
5. exact runtime/head/manifestで独立High review・Owner判断。#1398のICU/HKSCS出典別resolutionと残るUnicode等のlicence/notice・ソース保持を再評価する。

**PoCのみで\`resolved-removed\`や配布許可を立てない。** \`complete_distribution_audit=false\`、\`public_distribution_approved=false\`、#1398/#1400 blocked、Pages deployは対象外。
