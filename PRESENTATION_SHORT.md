# プロジェクト紹介（5分版）

**発表者**: Romeitou  
**テーマ**: リプレイ攻撃防御手法の評価シミュレーション

---

## 1. 問題設定（30秒）

### リプレイ攻撃とは？

```
正規ユーザー → "UNLOCK" → 受信機 → ドアが開く
        ↓（攻撃者が傍受）
攻撃者 → "UNLOCK"（再送信） → 受信機 → またドアが開く！
```

**脅威**：スマートロック、車両、IoTデバイス

---

## 2. 防御手法（1分）

| 手法 | 原理 | 長所 | 短所 |
|------|------|------|------|
| **Rolling Counter** | カウンタで古いフレームを拒否 | シンプル | 順序入れ替えに弱い |
| **Sliding Window** | カウンタの範囲を許容 | 順序入れ替えに強い | 実装が複雑 |
| **Challenge-Response** | 問題-答え方式 | 最高のセキュリティ | 双方向通信が必要 |

---

## 3. 実験結果（2分）

### 順序入れ替え環境での性能（p_reorder=0.3）

| 手法 | 正規受理率 | 評価 |
|------|-----------|------|
| Rolling Counter | **84.47%** ❌ | ユーザビリティ低下 |
| Sliding Window (W=5) | **99.88%** ✅ | 実用的 |
| Challenge-Response | **100%** ✅ | 理想的 |

**結論**：不安定なネットワークでは **Sliding Window が最適**

---

### ウィンドウサイズの選択（p_loss=0.05, p_reorder=0.3）

| Window Size | 正規受理率 | 攻撃成功率 |
|-------------|-----------|-----------|
| W=1 | 27.65% ❌ | 4.51% |
| **W=3** | **95.10%** ✅ | **0.22%** ✅ |
| **W=5** | **95.08%** ✅ | **0.30%** ✅ |
| W=10 | 95.22% ✅ | 0.48% ⚠️ |

**推奨**：W=3〜5（高いユーザビリティと低い攻撃成功率）

---

## 4. 技術的ハイライト（1分）

### スライディングウィンドウの実装

**ビットマスクで受信履歴を管理**：

```python
# 例：Last Counter = 10, Window Size = 5
# 許容範囲：[6, 7, 8, 9, 10]

state.received_mask = 0b10101
# bit 0 (Counter 10): 受信済み
# bit 1 (Counter 9):  未受信
# bit 2 (Counter 8):  受信済み
# ...

# フレーム Counter=9 が到着
offset = 10 - 9 = 1
if (state.received_mask >> 1) & 1 == 0:  # 未受信
    state.received_mask |= (1 << 1)  # マーク
    # Accept!
```

**ポイント**：メモリ効率的（整数1つで64カウンタ分を記録）

---

### チャネルモデル

```python
class Channel:
    def send(self, frame):
        # 1. パケット損失
        if random() < self.p_loss:
            return []  # 破棄
        
        # 2. 順序入れ替え（優先度キューで遅延）
        if random() < self.p_reorder:
            delay = randint(1, 3)
        else:
            delay = 0
        
        heappush(self.pq, (current_tick + delay, frame))
        return self._deliver_due_frames()
```

**ポイント**：現実的な無線環境をシミュレート

---

## 5. デモ（30秒）

```bash
# ケース1: 安定したネットワーク
python3 main.py --modes rolling window --p-loss 0.05
# → Rolling と Window が同等の性能

# ケース2: 不安定なネットワーク
python3 main.py --modes rolling window --p-reorder 0.3
# → Rolling: 84%, Window: 99.9%（15%の差！）
```

---

## まとめ

### 主要な発見

1. ✅ Rolling Counter は安定したネットワークで有効
2. ✅ **Sliding Window (W=3-5) は不安定なネットワークで最適**
3. ✅ Challenge-Response は双方向通信可能なら最強

### プロジェクトの貢献

- 📊 1,585行のPythonコードで完全再現可能
- 📊 200-500回のモンテカルロ試行で統計的信頼性
- 📊 3言語ドキュメント（英語・日本語・中国語）
- 📊 MIT ライセンスでオープンソース

**GitHub**: https://github.com/tammakiiroha/Replay-simulation

---

## 質疑応答の準備

### よくある質問

**Q: なぜシミュレーション？実機実験は？**
> A: コスト・時間・再現性の観点でシミュレーションが有効。チャネルモデルは文献に基づく。

**Q: Window のセキュリティリスクは？**
> A: 実験で測定済み。W=5 でも攻撃成功率 < 0.5%。実用上問題なし。

**Q: 他の攻撃（改ざん、中間者攻撃）は？**
> A: MAC（HMAC-SHA256）で改ざんを防止。中間者攻撃は本研究の範囲外。

---

**ご清聴ありがとうございました！**

