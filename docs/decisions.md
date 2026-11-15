# 設計判断の記録

## T001: 丸めと負値の扱い

- **丸め方式**: 仕様の「四捨五入」に従い、Python 組み込みの `round()`（偶数丸め）ではなく
  `floor(x + 0.5)` による四捨五入を採用した（例: 330.5 → "5:31"）。
  `format_hms` も同じく秒を四捨五入してから時・分・秒に分解する。
- **`format_pace` の負値**: 仕様に明記はないが、負のペースは意味を持たず
  `"M:SS"` 表記も破綻するため、`format_hms` と揃えて `ValueError` とした。0 は `"0:00"` を返す。

## T002: 完走タイム予測と CLI

- **`--pace` の書式**: 仕様の "M:SS" に厳密に従い、秒は 2 桁の 00〜59 のみ受け付ける
  （"5:3"・"5:60"・負値・小数は `ValueError`）。分は 0 以上の整数で桁数制限なし。
  解析関数は `pacecalc.cli.parse_pace` として公開している。
- **CLI のエラー処理**: `ValueError`（0 以下の値や書式不正）はトレースバックを出さず、
  標準エラーに `pacecalc: エラー: ...` を出して終了コード 2 を返す。argparse の引数エラーと同じ
  終了コードに揃えた。`main(argv)` は終了コードを返し、`__main__.py` が `sys.exit` する。
- **`riegel_predict_sec` の exponent**: 仕様の「不正な入力（0以下）」に exponent も含め、
  0 以下なら `ValueError` とした。
- **公開 API の追加**: `finish_time_sec` と `riegel_predict_sec` を `pacecalc` パッケージ直下からも
  import できるよう `__init__.py` に追加した（既存 API は変更なし）。

## T003: GitHub Actions CI

- **ワークフロー検査テストの追加**: 仕様は「ワークフローと README のみ」の変更だが、工場ルールの
  「変更には必ずテストを追加」に従い、`tests/test_ci_workflow.py` を追加した（製品コードは無変更）。
  標準ライブラリのみの制約で YAML パーサが使えないため、必須キー（トリガー・ランナー・Python
  バージョン・テストコマンド）が期待どおりのインデントで書かれていること、タブを含まないことを
  行単位で確認している。
- **アクションのバージョン**: `actions/checkout@v4`、`actions/setup-python@v5` を使用した。

## T004: スプリット表

- **ペース・目標タイムの検証**: 仕様の「0 以下なら ValueError」は distance_km / interval_km のみだが、
  既存関数と揃えて `pace_sec` / `target_time_sec` も 0 以下なら `ValueError` とした。
- **浮動小数点誤差の扱い**: 通過点は誤差の累積を避けるため `i * interval_km` で求める。
  `0.3 / 0.1` のような誤差で極小の端数区間が出ないよう、1e-9 km 未満の差は割り切れたものとみなす。
  最後の通過点は常に `distance_km` そのものの値を使う。
- **`--target` の書式**: "MM:SS" の分は桁数制限なし（例: "125:00"）、秒は 2 桁の 00〜59。
  "H:MM:SS" の分・秒は 2 桁の 00〜59。解析関数は `pacecalc.cli.parse_time` として公開した。
- **`--pace` と `--target`**: argparse の排他グループ（必須）で実装した。同時指定・どちらもなしは
  argparse のエラーとして終了コード 2 になる。
- **表示形式**: 距離は小数第 4 位まで出し末尾の 0 を省く（例: "10"、"21.0975"）。ラップは `format_pace`
  による "M:SS"（1 時間以上は "65:00" のように分で表す）、累計は `format_hms` による "H:MM:SS"。
  ラップ・累計はそれぞれ独立に四捨五入するため、表示上のラップ合計と累計が 1 秒ずれることがある
  （累計は丸め前の値から計算しており、最終行の累計は目標タイムと一致する）。
  表形式は全角文字の表示幅を考慮して右揃えする。
- **CSV**: 見出しは機械処理しやすい英語（`distance_km,lap,elapsed`）とし、値は表形式と同じ書式の文字列とした。
- **公開 API の追加**: `split_table` を `pacecalc` パッケージ直下から import できるようにした。

## T005: ヒルクライム物理モデル

- **θ の求め方**: 仕様の「平均勾配（gain/distance）」に従い、`θ = atan(gain / distance)` とした
  （distance は道のりとして扱い、所要時間は `distance / v`）。重力加速度は 9.80665 m/s² を使う。
- **入力検証の追加**: 仕様の ValueError 条件（距離・パワー・重量・目標タイムが 0 以下）に加え、
  獲得標高が負、`cda` / `crr` / `air_density` が負、`drivetrain_efficiency` が (0, 1] の範囲外も
  `ValueError` とした。下りを含む負の獲得標高はモデルの前提（登坂）外のため受け付けない。
  `cda` と `crr` がともに 0 の平坦など、速度が有限に定まらない場合も `ValueError` とする。
- **解法**: `climb_time_sec` は抵抗パワーが速度について単調増加であることを利用し、上限を倍々に
  広げてから二分法で解く。`required_power_w` は速度が既知になるため閉じた式で計算する。
- **CLI**: `climb` サブコマンドは CdA などの任意パラメータを公開せず、既定値で計算する（仕様の引数のみ）。
- **公開 API の追加**: `climb_time_sec` と `required_power_w` を `pacecalc` パッケージ直下から import できるようにした。

## T006: GPXコース対応

- **plan_course の戻り値**: 仕様の「各区間 … と累計時間」を `(rows, total_time_sec)` のタプルとした。
  `rows` は仕様どおり 5 要素 `(start_km, end_km, gradient_pct, speed_kmh, time_sec)` のリスト。
  区間ごとの累計は CLI 側で `time_sec` を足して表示する。
- **物理パラメータの受け方**: 仕様の `**physics` は、`climb_time_sec` と同じ名前・既定値のキーワード引数
  （`cda` / `crr` / `air_density` / `drivetrain_efficiency`）として明示した。呼び出し方は同じで、
  未知のキーワードは `TypeError` になり打ち間違いに気づける。検証条件も climb と揃えた。
- **下りの解法**: `climb._check_params` は負の獲得標高を拒否するため流用せず、`climb._resistance_power`
  を使って負の勾配も解く。抵抗パワーは下りでは小さい v で負になるが、正の根はただ 1 つなので
  [0, 上限速度] の二分法で解ける。上限速度で抵抗パワーが入力に届かなければ上限速度を返す。
- **勾配の定義**: 区間の勾配は (gain − loss) / 区間距離 とした（標高 None の部分を自然に除外できるため）。
  標高が揃っていれば区間の始点・終点の標高差 / 距離と同じ。
- **GPX の読み方**: `trkpt` を優先し、なければ `rtept` を読む。`wpt` は順序が経路を表すとは限らないため使わない。
  複数の trk / trkseg は文書順に連結し、セグメント間の距離も直線距離として加える。
  XML 不正・lat/lon 欠落や範囲外・ele が数値でない場合は `ValueError`。
- **CLI**: 仕様の引数に加え、区間幅 `--segment`（km、既定 1）を任意引数として追加した（splits の `--interval`
  に相当）。所要は `format_pace`（"M:SS"）、累計と総所要時間は `format_hms`（"H:MM:SS"）で表示する。
  GPX ファイルは UTF-8（BOM 可）として読み、読めない場合はエラー終了（終了コード 2）とする。
- **公開 API の追加**: `load_gpx_points` / `haversine_m` / `course_segments` / `plan_course` を
  `pacecalc` パッケージ直下から import できるようにした。

## T006R: 空の最終区間の修正

- **微小な端数は直前の区間に吸収する（切り捨てない）**: 総距離の末尾 `min(1 m, 区間幅 × 1%)` 未満の残りは
  独立した区間にせず、最終区間を総距離まで伸ばす。切り捨てると総距離と総所要時間がわずかに減るため、吸収を選んだ。
- **しきい値を 1 m とした理由**: 不具合は浮動小数の誤差（1e-12 km 程度）だけでなく、GPX の座標の丸め
  （小数 6 桁 ≒ 0.1 m）でも起きる。実際に 3 km のコースを小数 6 桁で書くと総距離が 3.00004 km になり、
  従来のしきい値 1e-9 km では "3-3" の区間が出た。1 m 未満の区間はペース配分として意味がなく、CLI の距離表示
  （小数第 4 位 = 0.1 m）でも始点と終点がほぼ同じに見えるため、まとめて吸収する。区間幅が極端に小さい
  （0.1 km 未満）場合に区間を飲み込みすぎないよう、区間幅の 1% を上限にした。
- 1 m 以上の端数は従来どおり短い区間として出す（既存仕様は変えない）。

## T007: パッケージング（v1.0.0）

- **パッケージ指定**: setuptools の自動検出はフラットレイアウトで `docs` / `tests` を拾う恐れがあるため、
  `[tool.setuptools] packages = ["pacecalc"]` で明示した。依存は `dependencies = []`（標準ライブラリのみ）。
- **long_description**: `readme = "README.md"` とし、形式は拡張子から `text/markdown` になる。
  description は英語 1 行。ライセンスは仕様にないため指定していない（公開前に決める必要がある）。
- **型ヒント**: requires-python が 3.10 以上のため、組み込みジェネリクス（`list[...]` / `tuple[...]`）を使った。
  `None` を取る引数は `Optional[float]` とした。GPX の点・区間・計画行のタプル型は `pacecalc.course` に
  別名 `Point` / `Segment` / `PlanRow` として定義した（`__all__` には加えていない）。数値引数は `float`
  （PEP 484 により `int` も受け付ける）。挙動は変えていない。
- **テスト**: `tests/test_packaging.py` を追加。pyproject.toml の検査は標準ライブラリの `tomllib`
  （3.11 以上）を使い、3.10 では skip する。
- **ビルド成果物**: `pip install .` で作られる `build/`・`*.egg-info/`・`dist/` を `.gitignore` に追加した
  （検証用の `.venv/` は既に除外済み）。
