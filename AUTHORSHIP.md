# 项目所有权声明 / Project Authorship Declaration

## 📋 基本信息 / Basic Information

**项目名称 / Project Name**: IoT Replay Attack Defense Simulator  
**作者 / Author**: Romeitou (tammakiiroha)  
**GitHub**: https://github.com/tammakiiroha  
**邮箱 / Email**: lumingteng9@gmail.com  
**项目仓库 / Repository**: https://github.com/tammakiiroha/IoT-Replay-Defense-Simulator  
**创建时间 / Creation Date**: 2025-11-18  
**许可证 / License**: MIT License

---

## 🔐 所有权证明 / Proof of Ownership

### 1. Git 提交历史 / Git Commit History

本项目的完整开发历史可通过 Git 提交记录验证：

```bash
# 查看完整提交历史
git log --all --author="tammakiiroha"

# 查看提交统计
git shortlog -sn --all
```

**关键信息**：
- 首次提交：2025-11-18
- 提交者：tammakiiroha <lumingteng9@gmail.com>
- 提交总数：94+ commits

### 2. GitHub 账号验证 / GitHub Account Verification

- **GitHub Profile**: https://github.com/tammakiiroha
- **User ID**: 153071074
- **仓库所有者**: tammakiiroha
- **仓库创建者**: tammakiiroha
- **仓库管理员**: tammakiiroha

### 3. 邮箱验证 / Email Verification

所有 Git 提交都使用以下邮箱：
- `lumingteng9@gmail.com` (主要开发邮箱)
- `153071074+tammakiiroha@users.noreply.github.com` (GitHub 关联邮箱)

### 4. 时间戳证明 / Timestamp Proof

所有提交都包含不可篡改的时间戳：
- 首次提交：2025-11-18 03:16:45 +0900
- 开发时区：+0900 (日本标准时间)

---

## 📚 项目贡献证明 / Contribution Proof

### 核心代码文件 / Core Code Files

以下文件均由本人原创开发：

**仿真核心 / Simulation Core**:
- `sim/types.py` - 数据结构定义
- `sim/sender.py` - 发送方实现
- `sim/receiver.py` - 接收方和防御机制
- `sim/channel.py` - 信道模拟
- `sim/attacker.py` - 攻击者模型
- `sim/experiment.py` - 实验控制
- `sim/security.py` - 密码学实现
- `sim/commands.py` - 命令序列管理

**测试代码 / Test Code**:
- `tests/test_receiver.py` - 接收方测试
- `tests/test_sender.py` - 发送方测试
- `tests/test_channel.py` - 信道测试
- `tests/test_attacker.py` - 攻击者测试
- `tests/test_experiment.py` - 实验测试

**脚本工具 / Scripts**:
- `scripts/run_sweeps.py` - 参数扫描
- `scripts/plot_results.py` - 图表生成
- `scripts/export_tables.py` - 表格导出
- `scripts/benchmark.py` - 性能基准测试

**文档 / Documentation**:
- `README.md` (English)
- `README_CH.md` (中文)
- `README_JP.md` (日本語)
- `PRESENTATION_EN.md` (2000+ lines)
- `PRESENTATION_CH.md` (2000+ lines)
- `PRESENTATION_JP.md` (1700+ lines)
- `EXPERIMENTAL_PARAMETERS_EN.md`
- `EXPERIMENTAL_PARAMETERS_CH.md`
- `EXPERIMENTAL_PARAMETERS_JP.md`
- `CONTRIBUTING.md`

### 代码统计 / Code Statistics

```bash
# 查看代码统计
find . -name "*.py" -not -path "./.venv/*" | xargs wc -l
find . -name "*.md" | xargs wc -l
```

---

## 🎓 学术用途声明 / Academic Use Declaration

本项目作为我的毕业论文/研究项目的一部分：

**论文信息 / Thesis Information**:
- 标题：リプレイ攻撃（Replay Attack）に対する防御手法の検討と評価
- 作者：Romeitou (tammakiiroha)
- 学年：2025
- 研究方向：网络安全、物联网安全

**研究贡献 / Research Contributions**:
1. 实现了 4 种重放攻击防御机制的完整仿真
2. 设计并执行了 3 组系统性实验（200 次蒙特卡洛运行）
3. 发现了 Rolling Counter 机制在包乱序下的显著局限性
4. 提供了 Sliding Window 最优参数配置建议（W=3-7）

---

## 🔍 验证方法 / Verification Methods

### GitHub 在线验证

- **提交历史**: https://github.com/tammakiiroha/IoT-Replay-Defense-Simulator/commits/main
- **贡献统计**: https://github.com/tammakiiroha/IoT-Replay-Defense-Simulator/graphs/contributors

### Git 本地验证

```bash
git clone https://github.com/tammakiiroha/IoT-Replay-Defense-Simulator.git
cd IoT-Replay-Defense-Simulator
git log --all --author="tammakiiroha"
git shortlog -sn --all
```

---

## 📝 版权声明 / Copyright Notice

```
Copyright (c) 2025 Romeitou (tammakiiroha)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
```

---

## 🌐 在线身份验证 / Online Identity Verification

- **GitHub Profile**: https://github.com/tammakiiroha (User ID: 153071074)
- **项目仓库**: https://github.com/tammakiiroha/IoT-Replay-Defense-Simulator

---

## 📧 联系方式 / Contact Information

- **GitHub**: [@tammakiiroha](https://github.com/tammakiiroha)
- **Email**: lumingteng9@gmail.com

---

## ✅ 声明 / Declaration

我，Romeitou (tammakiiroha)，特此声明：

1. 本项目的所有代码、文档和设计均为本人原创
2. 本项目的开发过程完全可通过 Git 历史追溯
3. 本项目遵循 MIT 开源许可证
4. 本项目作为我的学术研究成果的一部分
5. 本项目的所有权归属清晰，证据充分

**签名 / Signature**: Romeitou (tammakiiroha)  
**日期 / Date**: 2025-11-23  
**GitHub**: https://github.com/tammakiiroha

---

## 🔗 相关链接 / Related Links

- **项目主页**: https://github.com/tammakiiroha/IoT-Replay-Defense-Simulator
- **完整文档**: [PRESENTATION_EN.md](PRESENTATION_EN.md)
- **贡献指南**: [CONTRIBUTING.md](CONTRIBUTING.md)
- **许可证**: [LICENSE](LICENSE)

---

**最后更新 / Last Updated**: 2025-11-23  
**文档版本 / Document Version**: 1.0

