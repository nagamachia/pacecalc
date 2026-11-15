# 変更履歴

このファイルには pacecalc の主な変更を記録します。
書式は [Keep a Changelog](https://keepachangelog.com/ja/1.1.0/) に、バージョン番号は
[セマンティック バージョニング](https://semver.org/lang/ja/) に従います。

## [1.0.0] - 2026-11-15

最初の公開版です（GitHub で公開。PyPI には公開しません）。

### 追加

- **コア変換**（T001）: 速度（km/h）とペース（秒/km）の相互変換 `speed_to_pace_sec` / `pace_to_speed_kmh`、
  表示用の書式化 `format_pace`（`"M:SS"`）/ `format_hms`（`"H:MM:SS"`）。秒は四捨五入（偶数丸めではない）。
- **完走タイム予測**（T002）: 距離×ペースの `finish_time_sec`、Riegel 式による別距離の予測 `riegel_predict_sec`。
- **CLI**（T002）: `python3 -m pacecalc` の `pace` / `finish` サブコマンド。入力エラーは標準エラーに出して終了コード 2。
- **CI**（T003）: GitHub Actions（`.github/workflows/test.yml`）で push / pull request ごとにテストを実行。
- **スプリット表**（T004）: 区間ごとのラップと累計タイムを返す `split_table`（ペースまたは目標タイムを指定）と
  CLI `splits` サブコマンド（表形式 / CSV）。
- **ヒルクライム物理モデル**（T005）: 平均勾配の定常モデルで、一定パワーでの所要時間 `climb_time_sec` と
  目標タイムに必要な平均パワー `required_power_w`、CLI `climb` サブコマンド。式と前提は `docs/model.md`。
- **GPX コース対応**（T006）: GPX の読み込み `load_gpx_points`、距離計算 `haversine_m`、区間分割
  `course_segments`、区間ごとに物理モデルを適用する `plan_course`、CLI `course` サブコマンド。
- **パッケージング**（T007）: `pyproject.toml`（`pip install .` / `pip install git+https://github.com/nagamachia/pacecalc`
  でインストール可能、`pacecalc` コマンドを提供）、`pacecalc.__version__`、公開関数の型ヒント。

### 修正

- **空区間の修正**（T006R）: GPX コースの総距離が区間幅の倍数ちょうどのとき、長さ 0 に近い空の最終区間が
  出ていた不具合を修正（1 m 未満の端数は直前の区間に吸収）。

[1.0.0]: https://github.com/nagamachia/pacecalc/releases/tag/v1.0.0
