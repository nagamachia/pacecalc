# pacecalc

[![test](https://github.com/nagamachia/pacecalc/actions/workflows/test.yml/badge.svg)](https://github.com/nagamachia/pacecalc/actions/workflows/test.yml)

エンデュランススポーツ（ラン／サイクリング）向けのペース計算ライブラリです。
Python 標準ライブラリのみで動作します。

## インストール

Python 3.10 以上が必要です。外部依存はありません（PyPI には公開していません）。

リポジトリを clone してインストールする場合:

```sh
git clone https://github.com/nagamachia/pacecalc.git
cd pacecalc
pip install .
```

GitHub から直接インストールする場合:

```sh
pip install git+https://github.com/nagamachia/pacecalc
```

インストールすると `pacecalc` コマンドが使えるようになります（`python3 -m pacecalc` と同じ動作です）。

```sh
$ pacecalc pace --speed 12
5:00 /km
```

バージョンは `pacecalc.__version__` で確認できます。変更履歴は [CHANGELOG.md](CHANGELOG.md) を参照してください。

## 機能

| 関数 | 説明 |
| --- | --- |
| `speed_to_pace_sec(speed_kmh)` | 速度（km/h）→ ペース（秒/km）。0 以下は `ValueError` |
| `pace_to_speed_kmh(pace_sec)` | ペース（秒/km）→ 速度（km/h）。0 以下は `ValueError` |
| `format_pace(pace_sec)` | 秒/km を `"M:SS"` 形式に整形（秒は四捨五入）。負値は `ValueError` |
| `format_hms(seconds)` | 秒を `"H:MM:SS"` 形式に整形（秒は四捨五入）。負値は `ValueError` |
| `finish_time_sec(distance_km, pace_sec)` | 距離（km）×ペース（秒/km）で完走タイム（秒）。0 以下は `ValueError` |
| `riegel_predict_sec(known_distance_km, known_time_sec, target_distance_km, exponent=1.06)` | Riegel 式 `T2 = T1 × (D2/D1)^exponent` で予測タイム（秒）。0 以下は `ValueError` |
| `split_table(distance_km, pace_sec=None, target_time_sec=None, interval_km=1.0)` | 区間ごとの `(point_km, lap_sec, elapsed_sec)` のリスト。`pace_sec` か `target_time_sec` のどちらか一方を指定（目標タイムはイーブンペースで計算）。最後の区間は `distance_km` ちょうどで、端数は短い区間になる |
| `climb_time_sec(distance_km, elevation_gain_m, total_weight_kg, power_w, cda=0.32, crr=0.004, air_density=1.0, drivetrain_efficiency=0.97)` | 平均勾配の物理モデルで、一定パワーで登ったときの予測所要時間（秒）。**推定値** |
| `required_power_w(distance_km, elevation_gain_m, total_weight_kg, target_time_sec, cda=0.32, crr=0.004, air_density=1.0, drivetrain_efficiency=0.97)` | 目標タイムで登るのに必要な平均パワー（W）。**推定値** |
| `load_gpx_points(text)` | GPX 文字列から `(lat, lon, ele)` のリスト。`ele` がない点は `None` |
| `haversine_m(lat1, lon1, lat2, lon2)` | 2 点間の距離（m、haversine 公式・球体近似） |
| `course_segments(points, segment_km=1.0)` | 累積距離で区間に切った `(start_km, end_km, distance_km, gain_m, loss_m, gradient_pct)` のリスト |
| `plan_course(points, power_w, total_weight_kg, segment_km=1.0, cda=0.32, crr=0.004, air_density=1.0, drivetrain_efficiency=0.97)` | 区間ごとの勾配に物理モデルを適用した一定パワー走行の計画。`(rows, total_time_sec)` を返し、`rows` は `(start_km, end_km, gradient_pct, speed_kmh, time_sec)` のリスト。**推定値** |

## 使い方（ライブラリとして）

```python
from pacecalc import speed_to_pace_sec, pace_to_speed_kmh, format_pace, format_hms

pace = speed_to_pace_sec(12.0)   # 300.0（秒/km）
print(format_pace(pace))         # "5:00"

print(pace_to_speed_kmh(330))    # 10.909...（km/h）
print(format_pace(330))          # "5:30"
print(format_pace(359.6))        # "6:00"（60 秒の繰り上がり）

# フルマラソンを 5:30/km で走ったときの所要時間
print(format_hms(330 * 42.195))  # "3:52:04"
```

Riegel 式による予測の例:

```python
from pacecalc import riegel_predict_sec, format_hms

# 10km を 50 分で走れる人のハーフマラソン予測
print(format_hms(riegel_predict_sec(10, 50 * 60, 21.0975)))  # "1:50:19"
```

スプリット表の例:

```python
from pacecalc import split_table

# 10km を 50 分（イーブンペース）で走るときの 5km ごとの通過タイム
for point_km, lap_sec, elapsed_sec in split_table(10, target_time_sec=3000, interval_km=5):
    print(point_km, lap_sec, elapsed_sec)   # 5 1500.0 1500.0 / 10 1500.0 3000.0
```

ヒルクライムの予測の例:

```python
from pacecalc import climb_time_sec, required_power_w, format_hms

# 富士スバルライン（24.03km、獲得標高 1211m）を総重量 76kg・226.6W で登る
print(format_hms(climb_time_sec(24.03, 1211, 76, 226.6)))  # "1:20:55"

# 1:20:00 で登るのに必要な平均パワー（W）
print(round(required_power_w(24.03, 1211, 76, 80 * 60)))  # 230
```

`climb_time_sec` / `required_power_w` の距離・パワー・重量・目標タイムが 0 以下の場合は `ValueError`
になります（獲得標高は 0 を許し、平坦として計算します）。

> **注意**: ヒルクライムの予測は、平均勾配・無風・一定パワーを仮定した物理モデルによる**推定値**です。
> 実際のタイムは勾配の変化、風、体調、機材などで変わります。式・前提・限界は
> [docs/model.md](docs/model.md) を参照してください。

GPX コースの計画の例:

```python
from pacecalc import load_gpx_points, plan_course, format_hms

with open("course.gpx", encoding="utf-8") as f:
    points = load_gpx_points(f.read())
rows, total = plan_course(points, power_w=230, total_weight_kg=76)
for start_km, end_km, gradient_pct, speed_kmh, time_sec in rows:
    print(start_km, end_km, round(gradient_pct, 1), round(speed_kmh, 1), round(time_sec))
print(format_hms(total))
```

### GPX の対応形式と前提

- GPX 1.0 / 1.1 のトラック点（`<trkpt>`）を文書順に読みます。トラック点がなければルート点（`<rtept>`）を読みます。
  複数の `<trk>` / `<trkseg>` は順に連結します（ウェイポイント `<wpt>` は使いません）。
- 名前空間あり（`xmlns="http://www.topografix.com/GPX/1/1"` など）・なしの両方に対応します。
- 距離は緯度経度から haversine 公式で求めた水平距離です（標高差は距離に含めません）。
- **標高なしの扱い**: `<ele>` がない点の標高は `None` です。標高 `None` の点に接する部分は
  獲得標高・下り標高を 0（平坦）として扱います。すべての点に標高がなければ全区間が平坦になります。
- **下りの速度上限**: 急な下りで物理モデルの速度が発散しないよう、速度は **60 km/h** で頭打ちにします。
  ブレーキやコーナーでの減速は考えないため、下りの所要時間は実際より短めに出ることがあります。
- 区間の勾配は区間内の標高差（獲得 − 下り）÷ 区間距離で、区間内では一定勾配とみなします。
  式・前提の詳細は [docs/model.md](docs/model.md) を参照してください。

## 使い方（CLI）

`python3 -m pacecalc`（インストール後は `pacecalc`）でコマンドラインから使えます。

```sh
# 速度（km/h）からペースを表示
$ python3 -m pacecalc pace --speed 12
5:00 /km

# 距離（km）とペース（"M:SS" 形式）から完走タイムを表示
$ python3 -m pacecalc finish --distance 42.195 --pace 5:30
3:52:04

# 1km ごとのスプリット表（距離 ラップ 累計）
$ python3 -m pacecalc splits --distance 10 --pace 5:00
距離(km)  ラップ     累計
       1    5:00  0:05:00
       2    5:00  0:10:00
       ...
      10    5:00  0:50:00

# 目標タイムから 5km ごとのスプリット表を CSV で出力（端数は最後の短い区間になる）
$ python3 -m pacecalc splits --distance 21.0975 --target 1:45:00 --interval 5 --format csv
distance_km,lap,elapsed
5,24:53,0:24:53
10,24:53,0:49:46
15,24:53,1:14:39
20,24:53,1:39:32
21.0975,5:28,1:45:00

# ヒルクライムの予測タイム（距離 km、獲得標高 m、総重量 kg、平均パワー W）※推定値
$ python3 -m pacecalc climb --distance 24.03 --gain 1211 --weight 76 --power 226.6
1:20:55

# GPX コースを一定パワーで走るときの区間表（区間、勾配、速度、所要、累計）と総所要時間 ※推定値
$ python3 -m pacecalc course --gpx course.gpx --power 230 --weight 76
区間(km)  勾配(%)  速度(km/h)  所要     累計
     0-1     +5.0        18.1  3:18  0:03:18
     1-2     +5.0        18.1  3:18  0:06:37
     2-3     +5.0        18.1  3:18  0:09:55
     3-4     -7.2        60.0  1:00  0:10:55
     4-5     -8.0        60.0  1:00  0:11:55
   5-5.1     -8.0        60.0  0:06  0:12:01
総所要時間: 0:12:01
```

| サブコマンド | 引数 | 出力 |
| --- | --- | --- |
| `pace` | `--speed`（km/h） | ペース `"M:SS /km"` |
| `finish` | `--distance`（km）、`--pace`（`"M:SS"`、秒は 00〜59） | 完走タイム `"H:MM:SS"` |
| `splits` | `--distance`（km）、`--pace`（`"M:SS"`）または `--target`（`"MM:SS"` / `"H:MM:SS"`）のどちらか一方、`--interval`（km、既定 1）、`--format`（`table` / `csv`、既定 `table`） | 区間ごとの「距離 ラップ 累計」表。ラップは `"M:SS"`、累計は `"H:MM:SS"` |
| `climb` | `--distance`（km）、`--gain`（獲得標高 m）、`--weight`（総重量 kg）、`--power`（平均パワー W） | 予測タイム `"H:MM:SS"`（推定値。CdA などは既定値を使用） |
| `course` | `--gpx`（GPX ファイルのパス）、`--power`（平均パワー W）、`--weight`（総重量 kg）、`--segment`（区間幅 km、既定 1） | 区間ごとの「区間 勾配 速度 所要 累計」表と総所要時間（推定値。CdA などは既定値、速度上限 60 km/h） |

不正な入力（0 以下の値、`--pace` / `--target` の形式不正、GPX ファイルが読めない・不正、`splits` で `--pace` と `--target` の同時指定など）の場合は、標準エラーにメッセージを出して終了コード 2 で終了します。

## テストの実行

```sh
python3 -m unittest discover -s tests
```

## CI

GitHub Actions（`.github/workflows/test.yml`）で、push と pull request のたびにテストが自動実行されます。
ランナーは `ubuntu-latest`、Python は 3.12 を使い、`python -m unittest discover -s tests` を実行します。
外部依存はないため、依存パッケージのインストール手順はありません。

ローカルで同じテストを実行するには、リポジトリのルートで次を実行します（Python 3 標準ライブラリのみで動作します）。

```sh
python3 -m unittest discover -s tests
```
