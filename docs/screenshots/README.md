# Screenshots / 项目截图

## 如何添加截图

1. **运行GUI**：
   ```bash
   ./run_gui.sh
   ```

2. **截取以下画面**：
   - `gui-main.png` - 主界面全览（英文版）
   - `gui-japanese.png` - 日文界面
   - `gui-chinese.png` - 中文界面
   - `gui-running.png` - 实验运行中的状态
   - `gui-results.png` - 实验结果输出

3. **截图要求**：
   - 分辨率：1400x900 或更高
   - 格式：PNG（无损压缩）
   - 确保界面清晰可读
   - 避免包含敏感信息

4. **保存位置**：
   将截图保存到此目录 `/Users/romeitou/Desktop/卒業論文/Replay/docs/screenshots/`

5. **更新README**：
   截图完成后，在主README.md中添加图片链接

## 推荐的截图内容

### 1. gui-main.png（主界面）
- 显示英文版
- 左侧显示所有场景按钮
- 右侧显示初始状态
- 确保顶部标题栏清晰可见

### 2. gui-experiment.png（实验运行）
- 选择"Baseline Comparison"场景
- 截取实验运行到50%的状态
- 显示实时输出和进度信息

### 3. gui-results.png（实验结果）
- 显示完整的实验结果表格
- 包含所有4种防御机制的对比
- 确保数字清晰可读

### 4. gui-multilang.png（多语言）
- 制作一个组合图，展示三种语言的界面
- 使用图片编辑器并排放置3张截图

## 截图后的使用

在主README.md的"Quick start"部分添加：

```markdown
## GUI Preview

<table>
  <tr>
    <td><img src="docs/screenshots/gui-main.png" width="400"/></td>
    <td><img src="docs/screenshots/gui-experiment.png" width="400"/></td>
  </tr>
  <tr>
    <td align="center">Academic-style Interface</td>
    <td align="center">Real-time Experiment Output</td>
  </tr>
</table>
```

