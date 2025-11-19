# リプレイ攻撃シミュレーションツールキット

[![English](https://img.shields.io/badge/lang-English-blue.svg)](README.md)
[![日本語](https://img.shields.io/badge/lang-日本語-red.svg)](README.ja.md)
[![中文](https://img.shields.io/badge/lang-中文-green.svg)](README.zh.md)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)](tests/)

[English](README.md) | **日本語** | [中文](README.zh.md)

このツールキットは、記録再生攻撃者の下で複数の受信機構成をモデル化し、セキュリティ（攻撃成功率）とユーザビリティ（正規受理率）の両方の指標を報告します。

## 動作環境

- Python 3.11+ (CLI は標準ライブラリのみ、可視化には `matplotlib` を使用)
- macOS 14.x (Apple Silicon) および Ubuntu 22.04 でテスト済み
- 仮想環境の使用（推奨）:
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  ```

## 特徴

- **プロトコルバリエーション**: 無防御、ローリングカウンタ + MAC、ローリングカウンタ + 受理ウィンドウ、ノンスベースのチャレンジレスポンス
- **ロールモデル**: 送信者、損失/順序入れ替えチャネル、永続状態を持つ受信者、および観測フレームを記録・再生する攻撃者
- **評価指標**: 各試行の正規受理率と攻撃成功率、モンテカルロ試行における平均値と標準偏差
- **コマンドソース**: デフォルトのトイセットまたは実機コントローラから取得したトレースファイル
- **攻撃スケジューリング**: ポストラン一括再生またはインライン挿入
- **出力形式**: 標準出力への人間可読テーブル、下流解析用 JSON、パラメータスイープ自動化ヘルパー

## クイックスタート

```bash
python3 main.py --runs 200 --num-legit 20 --num-replay 100 --p-loss 0.05 --window-size 5
```

## CLI リファレンス

| フラグ | 説明 |
|------|------|
| `--modes` | 評価するモード（`no_def`, `rolling`, `window`, `challenge`）をスペース区切りで指定 |
| `--runs` | モードごとのモンテカルロ試行回数 |
| `--num-legit` | 試行ごとの正規送信数 |
| `--num-replay` | 試行ごとの再生攻撃試行数 |
| `--p-loss` | 正規フレームと注入フレームの両方に適用されるパケット損失確率 |
| `--p-reorder` | パケット順序入れ替え確率（ネットワークジッタ/遅延をシミュレート） |
| `--window-size` | `window` モード有効時の受理ウィンドウ幅 |
| `--commands-file` | 実ハードウェアから取得した改行区切りコマンドトレースへのパス |
| `--target-commands` | 攻撃者が再生する特定のコマンド（選択的再生） |
| `--mac-length` | 切り詰められた MAC 長（16進文字数） |
| `--shared-key` | 送信者/受信者が MAC 導出に使用する共有秘密鍵 |
| `--attacker-loss` | 攻撃者が正規フレームの記録に失敗する確率 |
| `--seed` | 再現性のためのグローバル RNG シード |
| `--attack-mode` | 再生スケジューリング戦略: `post` または `inline` |
| `--inline-attack-prob` | 正規フレームごとのインライン再生確率 |
| `--inline-attack-burst` | 正規フレームごとの最大インライン再生試行回数 |
| `--challenge-nonce-bits` | チャレンジレスポンスモードで使用されるノンス長（ビット） |
| `--output-json` | 集計メトリクスを JSON 形式で保存するパス |

## トレースファイル形式

1行に1つのコマンドトークンを記述します。空行と `#` で始まるコメントは無視されます。

```
# サンプルトレース
FWD
FWD
LEFT
RIGHT
STOP
```

サンプルファイル: `traces/sample_trace.txt` を `--commands-file` で直接使用できます。

## 完全な実験パイプラインの実行

### ステップ 1: 環境のセットアップ
```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows の場合: .venv\Scripts\activate
pip install -r requirements.txt
```

### ステップ 2: パラメータスイープの実行
```bash
python3 scripts/run_sweeps.py \
  --runs 300 \
  --modes no_def rolling window challenge \
  --p-loss-values 0 0.01 0.05 0.1 0.2 \
  --p-reorder-values 0 0.1 0.3 0.5 0.7 \
  --window-values 1 3 5 10 \
  --window-size-base 5 \
  --attack-mode post \
  --commands-file traces/sample_trace.txt \
  --seed 123 \
  --p-loss-output results/p_loss_sweep.json \
  --p-reorder-output results/p_reorder_sweep.json \
  --window-output results/window_sweep.json
```

### ステップ 3: 図の生成
```bash
python3 scripts/plot_results.py --formats png
```

### ステップ 4: ドキュメントへのテーブルエクスポート
```bash
python3 scripts/export_tables.py
```

### ステップ 5: テストの実行（オプション）
```bash
python -m pytest tests/ -v
```

## 実験の拡張

- `scripts/run_sweeps.py` でシナリオを自動化、または `run_many_experiments` でカスタムスイープを作成
- インライン攻撃確率/バーストを調整、または他の戦略のために `AttackMode` を拡張
- トレードオフを議論する際の高セキュリティ参照として `Mode.CHALLENGE` を使用

## プロジェクト構成

```
.
|-- main.py
|-- sim/
|   |-- attacker.py
|   |-- channel.py
|   |-- commands.py
|   |-- experiment.py
|   |-- receiver.py
|   |-- security.py
|   |-- sender.py
|   \-- types.py
|-- scripts/
|   |-- plot_results.py
|   |-- export_tables.py
|   \-- run_sweeps.py
|-- traces/
|   \-- sample_trace.txt
|-- tests/
|   \-- test_receiver.py
\-- README.md
```

## 論文での使用方法

1. 実験パラメータを文書化（`num_legit`, `num_replay`, `p_loss`, `p_reorder`, `window_size`, MAC 長）
2. テーブル出力または JSON 集計を論文のテーブルにコピー
3. トレードオフを強調: パケット損失と順序入れ替え率にわたる `window` 構成を比較、インライン対ポストラン攻撃モデルを対比、上限参照として `challenge` を使用

## 攻撃者モデルとランダム性に関する注意事項

- デフォルトでは、攻撃者は完全な記録者としてモデル化されます（`attacker_record_loss=0`）。正規リンクと同じ損失を攻撃者に経験させたい場合は、`p_loss` と等しく設定してください
- すべてのモンテカルロ試行は、すべてのモードで同じコマンドシーケンスとパケット損失ドローを再利用するため、比較が公平になります

## データセットとテーブルの再現

1. `main.py` / `scripts/run_sweeps.py` でデータセットを生成
2. 図を生成:
```bash
python scripts/plot_results.py --formats png
```

## 主な研究成果（テーブル）

### パケット順序入れ替えスイープ - 正規受理率（p_loss=0）

_ウィンドウモードは、ローリングカウンタと比較してチャネル順序入れ替えに対する優れた堅牢性を示します。_

| p_reorder | Rolling (%) | Window (W=5) (%) |
| --------- | ----------- | ---------------- |
| 0.0       | 100.00%     | 100.00%          |
| 0.1       | 93.55%      | 100.00%          |
| 0.3       | 84.47%      | 99.88%           |
| 0.5       | 77.62%      | 99.88%           |
| 0.7       | 78.33%      | 99.90%           |

### パケット損失スイープ - 正規受理率（p_reorder=0）

_両モードとも純粋なパケット損失で線形に劣化しますが、同様のパフォーマンスを示します。_

| p_loss | Rolling (%) | Window (W=5) (%) |
| ------ | ----------- | ---------------- |
| 0.00   | 100.00%     | 100.00%          |
| 0.01   | 98.97%      | 98.97%           |
| 0.05   | 94.88%      | 94.88%           |
| 0.10   | 89.90%      | 89.90%           |
| 0.20   | 79.53%      | 79.53%           |

### ウィンドウスイープ（ストレステスト: p_loss=0.05, p_reorder=0.3）

_厳しいチャネル条件下でのユーザビリティとセキュリティのトレードオフを比較。_

| Window W | 正規受理率 (%) | 再生成功率 (%) |
| -------- | -------------- | -------------- |
| 1        | 27.65%         | 4.51%          |
| 3        | 95.10%         | 0.22%          |
| 5        | 95.08%         | 0.30%          |
| 10       | 95.22%         | 0.48%          |

### 理想的なチャネルベースライン（ポスト攻撃、runs = 500、p_loss = 0）

_`results/ideal_p0.json` からの参照ベースライン_

| モード       | 正規受理率 (%) | 再生成功率 (%) |
| ------------ | -------------- | -------------- |
| no_def       | 100.00%        | 100.00%        |
| rolling      | 100.00%        | 0.00%          |
| window (W=5) | 100.00%        | 0.00%          |
| challenge    | 100.00%        | 0.00%          |

## 観察と考察

- **順序入れ替えに対する堅牢性**: ローリングカウンタメカニズムはパケット順序入れ替えに非常に敏感です。中程度の順序入れ替え確率（0.3）でも、正規受理率は約84%に低下します。対照的に、ウィンドウ（W=5）メカニズムは、深刻な順序入れ替え（0.7）下でもほぼ完璧なユーザビリティ（>99.8%）を維持します。
- **ウィンドウチューニング**: `W=1` は厳格なカウンタとして機能し、不安定な条件下で壊滅的に失敗します（受理率27.6%）。ウィンドウを `W=3..5` に増やすと、攻撃成功率を極めて低く保ちながら（<0.3%）、ユーザビリティを約95%に回復します。
- **セキュリティトレードオフ**: ウィンドウモードは理論的には小さな再生ウィンドウを開きますが、実験結果は、実際には（200試行でも）攻撃成功率が大幅なユーザビリティ向上と比較して無視できるレベルに留まることを示しています。
- **結論**: パケット損失と順序入れ替えが一般的な実世界の無線制御システムでは、スライディングウィンドウメカニズム（W=5）がセキュリティとユーザーエクスペリエンスの最良のバランスを提供します。

## コントリビューション

コントリビューションを歓迎します！開発環境のセットアップ、コードスタイルガイドライン、変更の提出方法については、[CONTRIBUTING.md](CONTRIBUTING.md) をご覧ください。

## 引用

このシミュレーションツールキットを研究や論文で使用する場合は、以下のように引用してください:

```bibtex
@software{replay_simulation_2025,
  author = {Romeitou},
  title = {Replay Attack Simulation Toolkit},
  year = {2025},
  publisher = {GitHub},
  url = {https://github.com/tammakiiroha/Replay-simulation}
}
```

またはプレーンテキスト形式:
> Romeitou. (2025). Replay Attack Simulation Toolkit. GitHub. https://github.com/tammakiiroha/Replay-simulation

## ライセンス

このプロジェクトは MIT ライセンスの下でライセンスされています。詳細については [LICENSE](LICENSE) ファイルをご覧ください。

