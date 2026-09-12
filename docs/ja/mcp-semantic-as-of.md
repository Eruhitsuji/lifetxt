# MCP semantic as-of

読み取り専用MCPツール `get_semantic_as_of` は、指定したアイテムとoffset付きの
明示的な時刻について、既存の `semantic-as-of-v1` 投影を返します。known、partial、
unavailable の状態、制約、provenanceを保持し、過去の証拠がない場合に現在のアイテムを
代用しません。Git履歴を合成することもありません。
