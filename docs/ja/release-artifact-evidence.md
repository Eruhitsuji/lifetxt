# リリース成果物の証跡

リリース成果物は、同じソースコミットから生成した wheel と sdist の組として
扱います。リリース証跡コマンドは、成果物、SHA-256 チェックサム、CycloneDX
1.5 の依存関係マニフェスト、ビルド環境と provenance を同じ証跡ディレクトリに
出力します。

## 検証

```console
python scripts/release_evidence.py --output-dir .cache/release-evidence
```

証跡は、wheel と sdist のハッシュが `SHA256SUMS` と一致すること、マニフェスト
が runtime と optional extra のポリシーを反映すること、provenance がソース
コミット・ビルドツール・ハッシュを記録することを確認します。出力には秘密情報
や絶対パスを含めません。

これは生成物の同一性と再確認可能性を示す証跡であり、依存パッケージの脆弱性
監査については [依存関係セキュリティ監査](../en/dependency-security-audit.md) を
参照してください。
