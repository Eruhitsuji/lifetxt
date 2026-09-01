# Personal Context: AIによる作成・維持・活用ガイド

このガイドでは、生成AIが lifetxt を provider-independent な Personal Context /
Personal DB として作成・維持・活用するための方針を説明します。ここで定義するのは
**authoring / usage policy** であり、新しい file format、schema、record kind、
Query language、AI provider 固有の contract ではありません。

基本モデルは次の通りです。

```text
Chat / PDF / ZIP / Docs / Code / Images / その他の source
                         |
                         v
                  Generative AI
              読む / 解釈 / 質問する
                         |
                         v
               長期的に使える personal meaning
                         |
                         v
                      lifetxt
                         |
             +-----------+-----------+
             |           |           |
             v           v           v
          Bootstrap   Maintain    Consume
```

AI は交換可能な intelligence / interface、lifetxt は user-owned で永続的な
context layer です。

MCP setup と、より小さな「会話 -> proposal -> Personal AI Memory」の pattern は
[AI 連携](./ai-integration.md#10-personal-ai-memory)を参照してください。

## 1. Personal Contextに何を残すか

保存候補か迷ったら、次の問いを使います。

> この情報は、別のsession、別のAI、あるいは将来のユーザー自身にとっても
> 役に立つか？

Yes なら Personal Context の候補です。その source や今回の1 turnだけを理解する
ための情報なら、source/search/RAG側に残し、lifetxtへ無理に昇格させません。

| Category | 典型的な durable meaning |
| --- | --- |
| Profile | role、専門、所属、安定したidentity context |
| Preference | 好むtool/format/work style、継続的な好き嫌い |
| Value | 継続的な判断原則や優先順位 |
| Skill | capability、意味のある経験 |
| Goal | 中長期的な目標 |
| Project | 継続中の活動・責任 |
| Relationship | 将来参照する価値のある人・組織との関係 |
| Decision | 重要な決定とその理由 |
| Current context | 1 turnを超えて意味を持つ現在状況 |
| History | 将来参照する価値のある重要な過去情報 |

通常、次のものは Personal Context へ昇格させません。

- chat全文;
- PDF/document全文;
- ZIP/archive内の全file;
- RAG chunk、embedding、search index;
- 一時的な雑談;
- すぐ意味を失う1 turnだけの情報;
- 根拠のないAIによるpersonality/profile推測;
- 既に十分表現されているfactの重複。

責任の境界は次のように考えます。

```text
RAG / source lookup: 「sourceには何が書かれているか？」
lifetxt:             「それがuserにとって長期的に何を意味するか？」
AI:                  「その情報から何を考え、何をすべきか？」
```

## 2. Source formatの処理はAI/clientに任せる

入力形式そのものを lifetxt の機能にする必要はありません。利用中の chat AI や
agent が対応していれば、PDFを読み、ZIPを展開し、codeを実行し、repositoryを
調べ、spreadsheetを解析するなど、そのAI/clientが持つ能力を利用できます。

このworkflowのために lifetxt が PDF/ZIP/DOCX parser、OCR、embedding、vector
DB、provider-specific ingestion codeを内蔵する必要はありません。AI/clientが
sourceを理解し、lifetxtには**durableなstructured resultだけ**を渡します。

この分離により、将来AIが新しいsource typeへ対応しても、lifetxt Formatを変更せず
同じauthoring policyを使えます。

必要であれば、既存の `source:` field で軽量なprovenanceを残します。

```text
source:chat
source:resume.pdf
source:resume.pdf#page=2
source:research.zip#README.md
```

これは新しいstructured provenance contractではなく、粗い参照です。元PDFや
archiveそのものが将来も必要なら適切なsource system側に残し、evidence保存のためだけ
に全文を `life.txt` へ複製しません。

## 3. 既存Format 1.0だけでrecordを作る

永続的なpersonal factは通常、既存の `N` (Note) recordとして表現できます。
workspace owner自身についてのfactには `person:self` を使い、意図を読みやすくする
ために既存の自由な `tag:` 値を使います。

推奨するrecord形の例:

```text
[N] N "Prefers CLI tools" id:ctx_pref_cli person:self tag:preference source:chat updated:2026-09-01
[N] N "Uses Python regularly" id:ctx_skill_python person:self tag:skill source:resume.pdf updated:2026-09-01
```

`profile`、`preference`、`value`、`skill`、`goal`、`project`、
`relationship`、`decision` などのtag値は**convention**です。新しい必須schemaでも、
自動的に first-class Query field へ昇格する新語彙でもありません。

`id:` はFormat上の必須条件ではありませんが、durable Personal Contextでは強く
推奨します。説明、link、correction、supersessionはstable IDがあると扱いやすく
なります。`updated:` も任意ですが、Personal Contextのstaleness判定は `updated:`
があるrecordだけを経時評価できます。`source:` もFormat上は任意ですが、
`context health` はsourceのないPersonal Contextを検出するため、可能なら残します。

### ContextとActionを混同しない

情報の意味が別の既存record kindに自然に対応するなら、それを使います。すべてを
`N` に押し込む必要はありません。

```text
[N] N "Wants to improve English ability" id:ctx_goal_english person:self tag:goal source:chat
[ ] T "Study TOEIC material for 30 minutes" project:english
```

1行目は再利用可能なgoal context、2行目は具体的actionです。同様に、calendar event
なら `E`、日付付きのjournal/historyなら `J`、presence/current statusなら `S` を
既存の意味に従って使います。

### Atomicで独立して訂正できるfactを優先する

1 recordには、後から独立してcorrect/supersede/retire/referenceできる、1つの
まとまった意味を持たせるのが基本です。

巨大なprofile Noteは避けます。

```text
[N] N "Profile" person:self
| Uses Python, prefers CLI tools, is working on Project A, and wants to learn English.
```

次のように独立してmaintainできるfactを推奨します。

```text
[N] N "Uses Python regularly" id:ctx_skill_python person:self tag:skill source:chat
[N] N "Prefers CLI tools" id:ctx_pref_cli person:self tag:preference source:chat
[N] N "Works on Project A" id:ctx_project_a person:self tag:project source:chat
[N] N "Wants to improve English ability" id:ctx_goal_english person:self tag:goal source:chat
```

一方で、1つのまとまった意味まで細切れにして読みにくくする必要はありません。
判断基準は「このfactだけが変わったり訂正されたりしても、他のfactはそのまま正しいか？」
です。

## 4. AIの推測を黙ってdurable factにしない

AIは、userの明示発言やsourceが直接supportするfactを抽出できます。しかし、
解釈や推測を黙ってauthoritative Personal Contextへ昇格させてはいけません。

例えばsourceが次をsupportしているとします。

```text
Uses Python regularly
```

これだけでは次を意味しません。

```text
Python is the user's favorite programming language
```

推測内容をPersonal Contextにすると将来役立ちそうなら、まずuserへ確認します。
確認された後は、通常のexplicit candidateとして扱えます。

このガイドでは、新しい `assertion:`、`confidence:`、`subject:` vocabularyを
導入しません。それらは実利用からstable contractが必要だと分かるまで保留します。

## 5. Lifecycle: Bootstrap -> Maintain -> Consume

### 5.1 Bootstrap

Bootstrapは、現在AIが利用できる情報から**小さな初期Personal Context**を作る工程です。
最初からuserの人生全体をmodel化することを目標にしません。

推奨手順:

```text
DISCOVER    既存Personal Contextがあれば読む。
SCOPE       今回役立つcontext domainを決める。
INGEST      AI/clientが理解できるsourceを読む。
EXTRACT     長期的・反復的に使えるpersonal meaningだけを選ぶ。
ATOMIZE     独立して訂正できるfactへ分割する。
CLASSIFY    既存kind + person/tag/sourceへ対応付ける。
VERIFY      曖昧なcandidateやAI推論をuserへ確認する。
RECONCILE   duplicate/conflict/supersessionを確認する。
REVIEW      proposed recordを表示またはstageし、人が確認する。
VALIDATE    生成したlifetxt workspace/contextを検証する。
```

最初は次の範囲程度で十分です。

- profile / identity context;
- preferences;
- skills / capabilities;
- goals;
- active projects / responsibilities.

values、relationships、decisions、important historyは、役立つevidenceが出てきた時に
追加します。小さく始めるとreviewしやすく、推測や低価値contextの大量保存を避けられます。

lifetxtへ直接接続していない普通のchat AIでも、例えば次のように依頼できます。

```text
この会話と私が渡すfileから、小さなlifetxt Personal Contextを作ってください。
将来の別sessionでも役立つdurable factだけを残してください。
既存Format 1.0を使い、原則1 record=独立して訂正可能な1 factとし、
根拠のない推測は保存せず、保存前にproposed recordsを私に見せてください。
```

reviewした内容を `personal.life.txt` として保存し、次で検証できます。

```sh
lifetxt check personal.life.txt
lifetxt context health personal.life.txt
```

### 5.2 Maintain

Personal Contextは毎回full rebuildするのではなく、日常利用の中で少しずつ育てます。

後のconversation/sourceから新しいdurable factが得られた場合:

1. 現在のcontextと比較する;
2. 既に十分表現されているなら何も追加しない;
3. 独立した新情報なら新しいatomic candidateを追加する;
4. 既存factが変化したならduplicateではなくcorrection/supersessionとして扱う;
5. 必要に応じauthoritative mutation前にproposalをreviewする。

現在の状態はdeterministic toolkitで確認できます。

```sh
lifetxt context health personal.life.txt
lifetxt context why ctx_pref_cli personal.life.txt
```

保存済みfactが変わった場合は、historyを残すcorrection proposalをstageできます。

```sh
lifetxt memory correct ctx_pref_cli "Now prefers GUI tools for daily work" personal.life.txt --source chat
lifetxt proposal list
lifetxt proposal show PROPOSAL_ID
lifetxt proposal accept PROPOSAL_ID
```

correction proposalは既存の `corrects:<old-id>` conventionで旧recordを参照します。
新recordがacceptされた後も過去recordは確認でき、toolkitは旧recordをsupersededとして
扱います。

MCP/agent clientなら `--profile assist` で同じproposal-first boundaryを利用できます。
read toolsに加え、追加writeとして許可されるのは `stage_proposal` だけです。MCPは
便利なautomationですが、このlifecycleの必須条件ではありません。

### 5.3 Consume

Personal Contextの価値は、別sessionや別AIが同じ背景を再発見せず利用できることに
あります。

代表的な使い方:

- 既知のpreference/constraintを回答へ反映する;
- 新しいAI/sessionでcontextを復元する;
- 現在のgoal/projectを考慮してplanする;
- skill/preferenceに合うtoolや方法をrecommendする;
- work開始前に関連person/project contextを取得する;
- 新しい選択を過去のdecision/rationaleと比較する;
- 全recordを毎回渡さず、boundedなAI向けprojectionを作る。

狭い検索なら通常のsearch/query surfaceを使えます。

```sh
lifetxt search "CLI" personal.life.txt
lifetxt query "kind:N person:self tag:preference" personal.life.txt
lifetxt decisions personal.life.txt
```

AI向けのboundedでdeterministicなprojectionにはContext Capsuleを使えます。

```sh
lifetxt context capsule personal.life.txt --pretty
lifetxt context capsule personal.life.txt --tag goal --tag project --pretty
```

Capsuleはdeterministic revisionを持つread-only projectionであり、第二のsource of
truthではありません。既定ではstale/supersededなPersonal Contextを除外するため、
過去record全件を無条件にmodelへ渡すより適したhandoff surfaceです。

## 6. 追加する前にreconcileする

既存Personal ContextをmaintainするAIは、新情報を次のいずれかに分類します。

| Case | Action |
| --- | --- |
| 同じfactが既にある | duplicateを作らない |
| 独立した新fact | 新しいatomic candidateを追加 |
| 既存factに独立して有用なdetailが増えた | 必要なmeaningだけ追加/改善 |
| 既存factが変わった | old recordをcorrect/supersede |
| sourceが矛盾・意味が曖昧 | 昇格前にuserへ確認 |
| old factは歴史としてのみ有用 | historyは残し、current/default contextとして扱わない |

目標は、過去の全発言を永遠にtrueとしてappendするlogではなく、説明可能でmaintain
できるPersonal Context storeです。

## 7. 最初は1 file、必要になってから分割する

最小の推奨構成は次だけです。

```text
personal.life.txt
```

これだけでPersonal DBとして利用できます。最初から大きなdirectory taxonomyを
作ることを導入条件にしません。

contextが増えたら、人間が整理しやすいよう通常のmulti-file workspaceとして
分割できます。

```text
personal/
  profile.life.txt
  preferences.life.txt
  projects.life.txt
  decisions.life.txt
  history.life.txt
```

これはworkspace/file organization上の選択にすぎず、新しいPersonal DB storage
semanticsではありません。lifetxtのmulti-file surfaceから同じcontextとして読めます。

## 8. Worked scenarios

### 8.1 Chat-only bootstrap

Personal Contextがまだないuserがchat AIへ初期構築を依頼します。AIはprofile、
preferences、skills、goals、active projectsについてboundedな質問をし、明示された
durable factだけを抽出します。小さな `N` record集合を提示し、userがreviewして
`personal.life.txt` へ保存します。

次のsessionは同じ背景質問を最初から繰り返さず、そのfileを読んで開始できます。

### 8.2 PDF / ZIP / repositoryを使うbootstrap

userがresume PDFとproject ZIPを対応可能なchat AIへuploadします。AIはPDFを読み、
archive内の必要なfileを調べ、durable skill、project responsibility、明示されたgoal
など長期的に意味を持つ情報だけを抽出します。

例えば次のrecordを生成できます。

```text
[N] N "Uses Python regularly" id:ctx_skill_python person:self tag:skill source:resume.pdf
[N] N "Maintains Project A" id:ctx_project_a person:self tag:project source:research.zip#README.md
```

PDF/ZIP自体はsource materialとして残ります。**このworkflowではlifetxt自身はPDFも
ZIPもparseしていません。** 将来AI clientが新しいfile typeを理解できるように
なっても、同じPersonal Context authoring policyを利用できます。

### 8.3 継続利用中のcorrection

保存済みrecordに特定のwork styleを好むとあります。数か月後、userが明示的に
好みが変わったと述べました。

AIは矛盾するpreferenceをもう1件current factとしてblind appendしません。既存recordを
特定し、`lifetxt memory correct`（または同等のreview済みmanual change）でcorrectionを
提案し、`corrects:` を通じて過去recordをhistoryとして残します。

`lifetxt context health` では旧recordがsupersededとして分類され、2つの値を両方current
として扱うことを避けられます。

### 8.4 別session / 別providerで再利用

後のAI clientがwork planを作る必要があります。現在のgoals、projects、preferencesを
含むbounded Context Capsuleを読み、そのfactをplanへ反映します。

同じ `personal.life.txt` は別のMCP client、CLI-driven agent、local model、通常のchat
workflowからも使えます。provider-specific memoryではなくlifetxtをdurable storeにします。

## 9. AI author向けreview / validation checklist

Personal Contextをproposal/saveする前に、AIは次を確認します。

- 将来も役立つ程度にdurableな情報か？
- user/sourceが明示的にsupportしており、AIがguessしただけではないか？
- source全文をcopyせず、意味へ要約しているか？
- 後で独立して訂正できる粒度か？
- 同等recordが既にないか？
- 本当にNoteか、既存 `T`/`E`/`J`/`S` の方が意味に合わないか？
- durable recordに有用な `id:` があるか？
- 軽量な `source:` 参照を残せるか？
- duplicate追加ではなくcorrection/supersessionすべきではないか？
- AI-generated authoritative changeをuserがreviewできたか？

最後に、生成textを信頼するだけでなく実fileを検証します。

```sh
lifetxt check personal.life.txt
lifetxt context health personal.life.txt
```

## 10. Non-goals

このガイドは次を追加・要求しません。

- Personal DB専用database engine / record type;
- built-in PDF/ZIP/DOCX/OCR ingestion;
- RAG、embedding、vector storage、bulk source mirroring;
- provider SDK / provider-specific memory API;
- first-class `subject:`、`assertion:`、`confidence:`、category field;
- 例示したtag値をmandatory Query vocabularyへ昇格すること;
- unreviewedなauthoritative AI writeの自動化;
- MCPの利用必須化。

目標とするarchitectureは次のままです。

```text
AI/client   sourceを理解し、meaningを提案する
lifetxt     durableでinspect可能なuser-owned contextを保存する
human       何をtrusted Personal Contextにするかのauthorityを持つ
```
