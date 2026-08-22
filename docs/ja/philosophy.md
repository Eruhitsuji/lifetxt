# Philosophy と長期的な Vision

この文書は、lifetxt がなぜ存在するのか、そしてどのような原則がその発展を導くべきか
を説明します。自分の記録をどう残したいかを考えている user と、ある機能提案が
この project に属するかどうかを判断する contributor の両方に向けて書かれています。

これは意図と方向性を述べるものであり、runtime の挙動、file format、API、schema、
MCP contract を変更するものではありません。この文書と `.ai/project/RULES.md` の
Design Principles が食い違う場合は `RULES.md` が優先します
（[Section 10](#10-将来の機能のための-product-principles) 参照）。

- [1. なぜ lifetxt は存在するのか](#1-なぜ-lifetxt-は存在するのか)
- [2. 人生を統合した record](#2-人生を統合した-record)
- [3. なぜ text が基盤なのか](#3-なぜ-text-が基盤なのか)
- [4. 一つの record、複数の interface](#4-一つの-record複数の-interface)
- [5. User ownership と portability](#5-user-ownership-と-portability)
- [6. 外部 system と hub model](#6-外部-system-と-hub-model)
- [7. AI と Personal Context](#7-ai-と-personal-context)
- [8. Life Record、Life Context、Life Assistance](#8-life-recordlife-contextlife-assistance)
- [9. Privacy、選択的な記録、disclosure](#9-privacy選択的な記録disclosure)
- [10. 将来の機能のための Product Principles](#10-将来の機能のための-product-principles)
- [11. lifetxt ではないもの](#11-lifetxt-ではないもの)

---

## 1. なぜ lifetxt は存在するのか

人生を管理する助けとなる software の多くは、一つの category を中心に組み立てられ
ています -- task manager、calendar、notes app、journal、habit tracker。それぞれが
独立した application で、独自の storage と account、そして「何が重要か」について
独自の考え方を持っています。

lifetxt はこれとは異なる前提から出発します。task、event、deadline、reminder、
habit、status、message、note、journal entry は、スマートフォンの一枠を奪い合う
無関係な category ではありません。それらはすべて同じもの -- 一人の人間の人生を、
時間を通じて見たときの、異なる view です。名前もそのとおりの意味を持ちます:
scope が一つの productivity category より広いという意味での **life**、そして
どの application、service、UI にも縛られない、単純で inspectable、portable な
text という durable な substrate という意味での **txt** です。

lifetxt は、ある人の過去・現在・未来に関する重要な情報を、複数の tool や interface
にわたって記録し活用するための、text-native で user-owned な基盤です。

## 2. 人生を統合した record

record に何が含まれるべきかを考える上で有用なのは、単純な time model です:

```text
Past     = history / 起きたこと
Present  = state / 今起きていること
Future   = intent / 起きるべきこと・起きるかもしれないこと
```

完了した task、記録済みの work session、辛かった一日についての journal entry は
すべて「past」です。今まさに meeting 中であることを示す presence record は
「present」です。deadline、habit の次回発生、まだ固まっていない plan は
「future」です。lifetxt はこれらの次元を一つの record model の中で相互運用可能に
保ちます。人生を「calendar」「todo」「notes」「journal」といった application の
境界に無理に当てはめることはしません。

「統合された life record」とは、*あなたの*人生と情報同士の関係性を中心にした
統合を意味します -- task は所属する project を参照でき、journal entry はその日の
event を参照でき、ticket の history はそれを起票した人を参照できます。あなたに
関するあらゆる datum を無差別に収集することを意味するのではありません。詳細は
[Section 9](#9-privacy選択的な記録disclosure) を参照してください。

## 3. なぜ text が基盤なのか

Plain text は CLI や editor を使う user だけのための convenience ではありません。
durability 戦略の一部です:

- 専用の application がなくても record を読める -- 誰でも開いて読める。
- editor、version control、diff、search、script、backup といった標準的な tool が、
  すでにそれを扱う方法を知っている。
- 将来の lifetxt の実装、あるいは全く無関係な tool でも、そのデータを解釈または
  移行できる -- 一つの program しか理解できない binary format に閉じ込められて
  いないため。
- user は自分自身の record を実質的に所有し続ける -- `life.txt` file を読んだり
  copy したりするのに lifetxt の協力は一切必要ない。

text であること自体は、将来にわたる完全な互換性を保証しません。`life.txt` には
今も文書化された grammar と format semantics があり、その grammar を責任を持って
進化させるには、[format specification](./life_txt_format_spec.md) と
[format migration guide](./format-migration.md) に記載された migration・
compatibility の rule が今も必要です。Plain text はその進化のコストを下げますが、
その必要性自体を無くすわけではありません。

## 4. 一つの record、複数の interface

lifetxt は意図的に複数の access surface を同時にサポートします:

```text
plain text editor
CLI
TUI
Web UI / API
AI / MCP / 将来の agent interface
```

これらのどれか一つが唯一の canonical な human interface というわけではありません。
それぞれは同じ underlying data を読み、提示し、変更するための一つの方法です。
直接 text を編集することは、正当で恒久的な access path であり続けます -- どんな
editor でも `life.txt` を開いて、そこにあるものを理解したり変更したりできます。
これは、lifetxt が管理する mutation の write-safety rule とは別の話です:
CLI、TUI、Web、MCP surface が authoritative な write を行うときは、
`.ai/project/RULES.md` の Design Principles がすでに要求しているとおり、
この project の validated・atomic・revision-aware な mutation contract を経由し、
同時編集が黙って失われることがないようにします。

重要な invariant は、underlying data とその semantics が inspectable かつ
portable であり続ける一方で、どの一つの interface も、あなたの record を
道連れにすることなく置き換え・拡張・放棄できる、ということです。

## 5. User ownership と portability

「どこからでも access できる」ことは、remote network access より広い概念です。
lifetxt の portability の主張は、複数の次元にまたがります:

- 異なる device や environment;
- 異なる interface（editor、CLI、TUI、Web、AI）;
- 同じ contract の上に構築された異なる software client;
- 異なる AI provider;
- まだ存在しない将来の interface;
- 今日の software がもはや存在しないかもしれない、長い時間の経過。

これは universal な connectivity や availability を保証するものではありません
-- lifetxt は、あなたの record が常にどこからでも設定なしに到達可能であるとは
主張しません。要点はもっと狭く、そしてもっと持続的です: record は、特定の
client、特定の account、特定の会社の存続に構造的に閉じ込められることなく、
それ自身の条件で再利用可能であり続けるべきだ、ということです。

これは、AI integration についてすでに述べられているより具体的な原則
（[`ai-integration.md`](./ai-integration.md) と
[issue #500](https://github.com/Eruhitsuji/lifetxt/issues/500) 参照）の
一般化です:

```text
UI is replaceable.
Client is replaceable.
AI is replaceable.
Provider is replaceable.
Transport is replaceable.

Your life record is the durable layer.
```

## 6. 外部 system と hub model

lifetxt は email、calendar、chat、Git hosting、CI/CD、issue tracker、file
storage を置き換えようとはしません。これらの system はそれぞれの domain の
authority であり続けて構いません。lifetxt の役割は hub になることです:
すべての外部 data source を完全に mirror することを要求するのではなく、
reference、正規化された summary、関連する state、proposal、そしてあなた自身が
記録した意味を統合します。

`life.txt` から参照される calendar event は、calendar provider が保持する
すべての詳細を必要としません -- title、time、そして source of truth への link が
あれば、あなたの record は十分に有用であり続けます。development ticket の
comment 全履歴は GitHub や GitLab に残しつつ、lifetxt はあなたにとって重要な
部分だけを正規化した append-only な local history として保持できます。これに
より、record が実際に何を所有し、何を単に参照しているだけかについて、正直で
あり続けられます。

## 7. AI と Personal Context

Generative AI は双方向で役立ちます:

```text
human language / external evidence
    -> interpretation
    -> proposal / structured capture
    -> lifetxt

lifetxt
    -> retrieval / context
    -> AI
    -> explanation / planning / suggestion
```

AI client は、雑な memo を整った record に変えたり、既存の record を daily
briefing や project summary、次に取るべき action の提案に変えたりする助けに
なります。AI がすべきでないのは、あなたの長期的な context が実際に存在する
唯一の場所になることです。もしある model や provider の memory 機能だけが、
あなたが誰で何を大切にしているかを記録する唯一の場所になってしまえば、その
context は tool を切り替えた瞬間に消え、provider 以外の誰もそれを inspect
できません。

> **AI はあなたの life context を使うべきであり、それを所有すべきではない。**

[Issue #500](https://github.com/Eruhitsuji/lifetxt/issues/500)（provider に
依存しない AI integration）と
[issue #503](https://github.com/Eruhitsuji/lifetxt/issues/503)（Personal
Context Engine の investigation）は、この原則の具体的な、AI 時代における
応用例です -- lifetxt の定義そのものではありません。今日使われているすべての
AI product が明日置き換わったとしても、この原則は変わらず成り立ちます。

## 8. Life Record、Life Context、Life Assistance

単純な layering が、何が何に依存しているかを明確にします:

```text
Life Record
    |
    v
Life Context
    |
    v
Life Assistance
```

- **Life Record** は durable な source です: `life.txt` とその設定された
  source に実際に存在する、あなたの task、event、note、journal、status、
  history です。
- **Life Context** は、その record から導かれる意味のある構造です --
  record 同士の関係、現在の state、ある瞬間や質問に関連する history です。
- **Life Assistance** は、CLI、TUI、Web、automation、AI といったどの interface
  でも、その context を使ってできることです: search、review、plan、explain、
  propose、そして act -- 常にその surface に適用される policy と permission
  の範囲内で。

Assistance layer が完全に変わっても、record は有用であり続けなければなりません。
現在のすべての lifetxt interface と AI integration への access を失っても、
plain text file に自分自身の人生の、本物で使える record が残っているべきです。

## 9. Privacy、選択的な記録、disclosure

「統合された life record」は「すべてを自動的に収集する」ことだと解釈しては
なりません。lifetxt の ownership model には、記録しない権利、開示しない権利が
含まれます:

- 何を record に含めるかはあなたが決めます。command、編集、承認した proposal
  といった、あなたの明示的な行動なしに何かが capture されることはありません。
- private または sensitive な data は、record に存在するというだけの理由で
  開示されることはありません。Visibility、workspace boundary、disclosure
  policy は、そもそも data を保存するかどうかとは別の、意図的な関心事です。
- AI client、remote user、integration に *access* や *permission* を与える
  ことと、*ownership* とは別の決定です。underlying record に対する control を
  手放すことなく、狭い read access や proposal のみの write path を許可
  できます。
- Provenance は重要です: AI によって提案された、外部 system から import
  された、あるいは他の人によって入力された record は、あなた自身が入力した
  ものと区別できるままであるべきです。

Data minimization、workspace boundary、disclosure policy、provenance の
追跡は、この原則が実際に software 内で強制される方法です。この文書は、それら
の仕組みが果たすべき意図を述べています。

## 10. 将来の機能のための Product Principles

`.ai/project/RULES.md` の Design Principles と Product Boundaries は、
lifetxt が何をし、何をしないかについての、repository における権威ある
enforceable な rule であり続けます。この文書は、それらの rule の背後にある
理由と長期的な方向性を、より分かりやすい言葉で説明するものであり、独自の
新しい rule を追加するものではありません。両者が食い違うように見える場合は
`RULES.md` が優先します。

新しい capability が lifetxt に属するかどうかを評価する際に有用な checklist:

- これは意味のある life information を保存または活用する助けになるか?
- authoritative な user data を portable かつ inspectable に保っているか?
- data model を、必要以上に一つの interface、provider、transport に
  結びつけていないか?
- 適切な場合、その capability は複数の surface で一貫して提供できるか?
- AI は user の record を助けているか、それとも意図せずその owner や
  source of truth になってしまっていないか?
- integration は privacy、provenance、そして外部 system 自身の domain に
  対する authority を尊重しているか?
- 今日好まれている client が消えても、underlying record は理解可能な
  ままか?

## 11. lifetxt ではないもの

この vision が過大な主張にならないよう、lifetxt は明示的に以下ではありません:

- あなたに代わってすべての外部 system を制御する、完全に自律した
  「Life OS」。
- すべての life data を収集・保存しなければならないという要求 -- 人生の
  大部分は記録されないままであるべきですし、実際そうあり続けます。
- Universal な connectivity の約束 -- 「どこからでも access できる」とは、
  device、interface、client、時間をまたいだ portability を意味するの
  であり、いつでもどこからでも network に到達できることを保証するもの
  ではありません。
- email、calendar、chat、Git hosting、CI/CD、issue tracker、file storage
  の置き換え。[Section 6](#6-外部-system-と-hub-model) を参照してください。
- 単一の AI provider に依存する product。
  [Section 7](#7-ai-と-personal-context) と
  [`ai-integration.md`](./ai-integration.md) を参照してください。
