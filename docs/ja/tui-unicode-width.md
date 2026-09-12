# TUI Unicode幅ポリシー

curses TUI は、ヘッダー、行、パネル、入力プロンプト、styled span、カーソル位置で
同じ表示セル幅とclip規則を使います。結合文字、variation selector、ZWJ列、flag列は
clip時に分割しません。全角・wide・emoji・frame以外の曖昧幅文字は保守的に計測し、
frameの罫線は1セルとします。active header markerは端末差を避けるASCII記号です。

端末固有の表示問題には `--glyphs ascii` を決定的なfallbackとして使えます。
