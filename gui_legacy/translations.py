"""
多语言翻译配置
Multilingual translations for GUI
"""

TRANSLATIONS = {
    "en": {
        "title": "Replay Attack Defense Evaluation",
        "subtitle": "Monte Carlo Simulation Framework",
        "version": "v1.0",
        "tagline": "Statistical analysis of defense mechanisms against replay attacks",
        "scenarios": "Experimental Scenarios",
        "dashboard": "Control Panel",
        "custom_exp": "Custom Configuration",
        "defense_mech": "Defense Mechanisms",
        "all": "All Modes (Comparative Study)",
        "no_def": "No Defense (Baseline)",
        "rolling": "Rolling Counter + MAC",
        "window": "Sliding Window",
        "challenge": "Challenge-Response",
        "runs": "Monte Carlo Runs",
        "num_legit": "Legitimate Packets",
        "num_replay": "Replay Attempts",
        "p_loss": "Packet Loss Rate",
        "p_reorder": "Reordering Rate",
        "window_size": "Window Size",
        "attack_mode": "Attack Timing",
        "post_run": "Post-run (after legit traffic)",
        "inline": "Inline (during legit traffic)",
        "seed": "Random Seed",
        "attacker_loss": "Attacker Loss Rate",
        "advanced": "Advanced Parameters",
        "start_sim": "▶  Run Simulation",
        "live_output": "Console Output",
        "status_ready": "Ready",
        "status_running": "Running",
        "clear_output": "Clear",
        "generate_plots": "Generate Figures",
        "export_tables": "Export Tables",
        "quick_test": "Quick Test",
        "quick_desc": "Fast validation run (30 iterations)",
        "baseline": "Baseline Comparison",
        "baseline_desc": "Ideal conditions (no loss/reorder)",
        "packet_loss": "Packet Loss Impact",
        "loss_desc": "10% packet loss scenario",
        "reorder": "Reordering Impact",
        "reorder_desc": "30% packet reordering",
        "harsh": "Harsh Network",
        "harsh_desc": "Combined loss + reordering",
        "busy_msg": "A simulation is already running.",
        "done": "COMPLETED",
        "error": "ERROR",
        "language": "Language",
        "params": "Parameters",
        "desc": "Description",
        "stop_sim": "Stop",
        "save_output": "Save Output",
        "confirm_stop": "Are you sure you want to stop the running experiment?",
        "no_results": "No results directory found. Please run experiments first.",
        "saved": "Output saved to",
        "metrics_help": "📊 Results Guide",
        "metrics_explanation": "Avg Legit = usability | Std Legit = stability | Avg Attack = risk | Std Attack = variation",
        "metrics_tooltip": """Result Metrics Explained:

• Avg Legit: Average acceptance rate of legitimate packets
  → Higher is better (closer to 100% = more usable)
  → Example: 95% means legitimate packets are accepted 95% of the time

• Std Legit: Standard deviation of legitimate acceptance
  → Lower is better (closer to 0% = more stable)
  → Example: 2% means results are consistent (stable system)
  → Example: 15% means results vary wildly (unstable system)

• Avg Attack: Average success rate of replay attacks
  → Lower is better (closer to 0% = more secure)
  → Example: 5% means only 5% of attacks succeed

• Std Attack: Standard deviation of attack success
  → Lower means defense performance is predictable

Ideal System: High Avg Legit + Low Std Legit + Low Avg Attack ✓""",
    },
    "zh": {
        "title": "重放攻击防御评估",
        "subtitle": "蒙特卡洛仿真框架",
        "version": "v1.0 版本",
        "tagline": "基于统计方法的防御机制评估研究",
        "scenarios": "实验场景",
        "dashboard": "控制面板",
        "custom_exp": "自定义配置",
        "defense_mech": "防御机制",
        "all": "全部模式（对比研究）",
        "no_def": "无防御（基线）",
        "rolling": "滚动计数器 + MAC",
        "window": "滑动窗口",
        "challenge": "挑战-响应",
        "runs": "蒙特卡洛运行次数",
        "num_legit": "正规传输次数（每次运行）",
        "num_replay": "重放攻击次数（每次运行）",
        "p_loss": "丢包率 (p_loss)",
        "p_reorder": "乱序率 (p_reorder)",
        "window_size": "窗口大小（滑动窗口）",
        "attack_mode": "攻击模式",
        "post_run": "事后攻击（正规流量后重放）",
        "inline": "内联攻击（正规流量中重放）",
        "seed": "随机种子",
        "attacker_loss": "攻击者记录丢失率",
        "advanced": "高级参数",
        "start_sim": "▶  运行仿真",
        "live_output": "控制台输出",
        "status_ready": "就绪",
        "status_running": "运行中",
        "clear_output": "清空",
        "generate_plots": "生成图表",
        "export_tables": "导出表格",
        "quick_test": "快速测试",
        "quick_desc": "快速验证运行（30次迭代）",
        "baseline": "基线对比",
        "baseline_desc": "理想条件（无丢包/乱序）",
        "packet_loss": "丢包影响",
        "loss_desc": "10% 丢包场景",
        "reorder": "乱序影响",
        "reorder_desc": "30% 数据包乱序",
        "harsh": "恶劣网络",
        "harsh_desc": "丢包 + 乱序组合",
        "busy_msg": "仿真正在运行中。",
        "done": "已完成",
        "error": "错误",
        "language": "语言",
        "params": "参数",
        "desc": "描述",
        "stop_sim": "停止",
        "save_output": "保存输出",
        "confirm_stop": "确定要停止正在运行的实验吗？",
        "no_results": "未找到结果目录。请先运行实验。",
        "saved": "输出已保存到",
        "metrics_help": "📊 结果指标",
        "metrics_explanation": "Avg Legit = 可用性 | Std Legit = 稳定性 | Avg Attack = 风险 | Std Attack = 波动",
        "metrics_tooltip": """结果指标详解：

• 平均合法率 (Avg Legit): 合法包的平均接受率
  → 越高越好（接近100% = 系统可用性高）
  → 示例：95% 表示合法包有95%的概率被接受

• 标准差合法率 (Std Legit): 合法包接受率的波动程度
  → 越低越好（接近0% = 系统稳定）
  → 示例：2% 表示结果一致，系统行为稳定
  → 示例：15% 表示结果波动大，系统不稳定

• 平均攻击率 (Avg Attack): 重放攻击的平均成功率
  → 越低越好（接近0% = 安全性高）
  → 示例：5% 表示只有5%的攻击成功

• 标准差攻击率 (Std Attack): 攻击成功率的波动程度
  → 越低表示防御性能越可预测

理想系统：高平均合法率 + 低标准差 + 低攻击率 ✓""",
    },
    "ja": {
        "title": "リプレイ攻撃防御評価",
        "subtitle": "モンテカルロシミュレーションフレームワーク",
        "version": "v1.0 バージョン",
        "tagline": "統計的手法による防御メカニズムの評価研究",
        "scenarios": "実験シナリオ",
        "dashboard": "コントロールパネル",
        "custom_exp": "カスタム設定",
        "defense_mech": "防御メカニズム",
        "all": "全モード（比較研究）",
        "no_def": "防御なし（ベースライン）",
        "rolling": "ローリングカウンタ + MAC",
        "window": "スライディングウィンドウ",
        "challenge": "チャレンジレスポンス",
        "runs": "モンテカルロ実行回数",
        "num_legit": "正規送信回数（実行ごと）",
        "num_replay": "リプレイ攻撃回数（実行ごと）",
        "p_loss": "パケット損失率 (p_loss)",
        "p_reorder": "並び替え率 (p_reorder)",
        "window_size": "ウィンドウサイズ（スライディング）",
        "attack_mode": "攻撃モード",
        "post_run": "事後攻撃（正規トラフィック後）",
        "inline": "インライン攻撃（正規トラフィック中）",
        "seed": "ランダムシード",
        "attacker_loss": "攻撃者記録損失率",
        "advanced": "詳細設定",
        "start_sim": "▶  シミュレーション実行",
        "live_output": "コンソール出力",
        "status_ready": "準備完了",
        "status_running": "実行中",
        "clear_output": "クリア",
        "generate_plots": "図表生成",
        "export_tables": "テーブル出力",
        "quick_test": "クイックテスト",
        "quick_desc": "高速検証実行（30回反復）",
        "baseline": "ベースライン比較",
        "baseline_desc": "理想条件（損失/並び替えなし）",
        "packet_loss": "パケット損失影響",
        "loss_desc": "10% 損失シナリオ",
        "reorder": "並び替え影響",
        "reorder_desc": "30% パケット並び替え",
        "harsh": "厳しいネットワーク",
        "harsh_desc": "損失 + 並び替え組み合わせ",
        "busy_msg": "シミュレーションは既に実行中です。",
        "done": "完了",
        "error": "エラー",
        "language": "言語",
        "params": "パラメータ",
        "desc": "説明",
        "stop_sim": "停止",
        "save_output": "出力を保存",
        "confirm_stop": "実行中の実験を停止してもよろしいですか？",
        "no_results": "結果ディレクトリが見つかりません。まず実験を実行してください。",
        "saved": "出力を保存しました：",
        "metrics_help": "📊 結果指標",
        "metrics_explanation": "Avg Legit = 利便性 | Std Legit = 安定性 | Avg Attack = リスク | Std Attack = 変動",
        "metrics_tooltip": """結果指標の詳細：

• 平均正規率 (Avg Legit): 正規パケットの平均受理率
  → 高いほど良い（100%に近い = 可用性が高い）
  → 例：95% は正規パケットの95%が受理されることを意味

• 標準偏差正規率 (Std Legit): 正規パケット受理率の変動
  → 低いほど良い（0%に近い = 安定）
  → 例：2% は結果が一貫しており、システムが安定
  → 例：15% は結果が大きく変動し、システムが不安定

• 平均攻撃率 (Avg Attack): リプレイ攻撃の平均成功率
  → 低いほど良い（0%に近い = セキュリティが高い）
  → 例：5% は攻撃の5%のみが成功

• 標準偏差攻撃率 (Std Attack): 攻撃成功率の変動
  → 低いほど防御性能が予測可能

理想的なシステム：高平均正規率 + 低標準偏差 + 低攻撃率 ✓""",
    }
}
