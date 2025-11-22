# プロジェクト著作権声明 / Project Authorship Declaration

> **中文说明**: 本文档的中文版说明请参见 [README_CH.md](README_CH.md) 的作者信息部分。

---

## 📋 日本語版 / Japanese Version

### 基本情報

**プロジェクト名**: IoT Replay Attack Defense Simulator  
**氏名**: 盧 銘騰（Romeitou / LU MINGTENG）  
**GitHub**: https://github.com/tammakiiroha  
**リポジトリ**: https://github.com/tammakiiroha/IoT-Replay-Defense-Simulator  
**ライセンス**: MIT License

### 開発経緯

本プロジェクトは、以下の卒業研究の一環として開発されました：

**研究題目**: リプレイ攻撃（Replay Attack）に対する防御手法の検討と評価  
**研究年度**: 2025年  
**研究分野**: ネットワークセキュリティ、IoTセキュリティ

**開発履歴**:
- 2025年4月～: 卒業設計の実験と設計を開始
- 2025年11月18日以降: 本リポジトリにてコード整理、文書化、実験スクリプト追加

### 開発証明

本プロジェクトの開発過程は、以下の方法で確認できます：

**Git コミット履歴**:
```bash
git log --all --author="tammakiiroha"
git shortlog -sn --all
```

**GitHub での確認**:
- コミット履歴: https://github.com/tammakiiroha/IoT-Replay-Defense-Simulator/commits/main
- 貢献統計: https://github.com/tammakiiroha/IoT-Replay-Defense-Simulator/graphs/contributors

### 開発内容

**実装した主要コンポーネント**:
- 4種類のリプレイ攻撃防御メカニズムのシミュレーション
- パケットロスと順序入れ替えを含むチャネルモデル
- 2種類の攻撃モード（事後攻撃・リアルタイム混入攻撃）
- モンテカルロシミュレーション実験フレームワーク（200回実行）

**主要な研究成果**:
1. Rolling Counter メカニズムがパケット順序入れ替え下で顕著な制約を持つことを観察
2. 本シミュレーション条件下で Sliding Window の適切なパラメータ範囲（W=3-7）を示唆
3. 3種類の系統的実験を設計・実行

### 参考資料と引用

本プロジェクトは以下の標準仕様を参考にしています：
- RFC 6479: IPsec Anti-Replay Algorithm without Bit Shifting
- RFC 2104: HMAC: Keyed-Hashing for Message Authentication

参考にした資料やコードについては、該当箇所にコメントまたは文書で明記しています。

### 声明

本プロジェクトの目的は、2.4GHz 帯無線リモコンシステムを対象として、リプレイ攻撃に対する防御手法を評価するための実験用シミュレーション環境を構築することである。

システム全体の設計（モジュール構成・データフロー）、攻撃・防御モデルおよび実験条件・評価指標の設計、主要なアルゴリズムや実装コードは、著者自身によって行われた。

開発の過程では、ChatGPT などの AI ベースのツールを、主にバグ調査、コードの改善提案、ドキュメントの推敲といった補助的な用途で利用している。AI ツールは一部コード片の修正や書き換えに貢献しているが、システム設計やコアロジックの実装方針は著者が決定している。

Git コミット履歴は開発プロセスの一つの証拠として参照できるが、最終的には、著者が本システムの設計意図と主要な処理の挙動を説明し、必要に応じて実験条件や実装を修正・拡張できることによって、本プロジェクトへの実質的な貢献を示すものとする。

**著者**: Romeitou (tammakiiroha)  
**日付**: 2025年11月  
**連絡先**: lumingteng9@gmail.com

---

## 📋 English Version

### Basic Information

**Project Name**: IoT Replay Attack Defense Simulator  
**Full Name**: LU MINGTENG (Romeitou)  
**GitHub**: https://github.com/tammakiiroha  
**Repository**: https://github.com/tammakiiroha/IoT-Replay-Defense-Simulator  
**License**: MIT License

### Development Background

This project was developed as part of the following thesis research:

**Thesis Title**: Study and Evaluation of Defense Methods Against Replay Attacks  
**Academic Year**: 2025  
**Research Area**: Network Security, IoT Security

**Development Timeline**:
- From April 2025: Started thesis experiments and design
- From November 18, 2025: Code restructuring, documentation, and experimental scripts in this repository

### Development Evidence

The development process of this project can be verified through:

**Git Commit History**:
```bash
git log --all --author="tammakiiroha"
git shortlog -sn --all
```

**GitHub Verification**:
- Commit history: https://github.com/tammakiiroha/IoT-Replay-Defense-Simulator/commits/main
- Contribution stats: https://github.com/tammakiiroha/IoT-Replay-Defense-Simulator/graphs/contributors

### Development Content

**Main Components Implemented**:
- Simulation of 4 replay attack defense mechanisms
- Channel model including packet loss and reordering
- 2 attack modes (post-run attack and inline real-time injection)
- Monte Carlo simulation framework (200 runs per experiment)

**Key Research Contributions**:
1. Observed that Rolling Counter mechanism has significant limitations under packet reordering in our simulation settings
2. Suggested that Sliding Window with W=3-7 may offer a good trade-off between usability and security under our experimental conditions
3. Designed and executed 3 systematic experiments

### References and Citations

This project references the following standard specifications:
- RFC 6479: IPsec Anti-Replay Algorithm without Bit Shifting
- RFC 2104: HMAC: Keyed-Hashing for Message Authentication

Referenced materials and code are properly cited in comments or documentation where applicable.

### Declaration

The goal of this project is to build an experimental simulation environment for evaluating replay-attack defense mechanisms on low-cost 2.4 GHz wireless remote systems.

The overall system design (module structure and data flow), the attack/defense models, the experimental conditions and evaluation metrics, and the main algorithms and implementation code were created by the author.

During development, AI-based tools such as ChatGPT were used in a supportive manner, mainly for bug investigation, code improvement suggestions, and documentation polishing. These tools helped fix or rewrite some code fragments, but the system architecture and core implementation decisions were made by the author.

The Git commit history can be used as one form of evidence of the development process. Ultimately, the author's substantive contribution is demonstrated by being able to explain the system design and the behavior of the main components, and by being able to adjust or extend the experiments and implementation when necessary.

**Author**: Romeitou (tammakiiroha)  
**Date**: November 2025

---

## 📝 Copyright Notice / 著作権表示

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

**Last Updated / 最終更新**: November 2025

