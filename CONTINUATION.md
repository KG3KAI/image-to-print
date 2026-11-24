# image-to-print — 交接

## 目标
自研 Skill（Codex + Claude Code 通用）：图片 → 可 3D 打印文件（STL/3MF），并给出打印前检查报告。

## 结构
- `skill/image-to-print/SKILL.md`：路由（立体模型 / 浮雕 / 透光浮雕 / 浮凸 Logo）与流程
- `scripts/gen3d.py`：图片转 3D。后端：免费 HF Space（hunyuan21 / hunyuan2 / triposg / trellis2）、Meshy（`MESHY_API_KEY`）、Tripo（`TRIPO_API_KEY`）；`auto` 依次回退
- `scripts/relief.py`：图片转浮雕 / 透光浮雕 / 浮凸 STL（确定性算法，保证闭合）
- `scripts/printprep.py`：修复（碎片、法线、补洞、manifold 重建、体素重建、合并重叠壳体）、朝向、按毫米缩放、底座、挖空、简化面数、检查 → JSON 报告，退出码 2 = 未通过
- `scripts/preview.py`：四视图 PNG 预览
- `scripts/slice_bambu.sh`：Bambu Studio 命令行离线切片验证（不发送到打印机）
- `install.sh`：创建 `~/.image-to-print-venv`，并软链接到 `~/.codex/skills` 和 `~/.claude/skills`

## 仓库
- GitHub：https://github.com/KG3KAI/image-to-print（私有，main 分支）
- 本仓库的提交身份：KG3KAI <45382119+KG3KAI@users.noreply.github.com>，不要用公司账号

## 已验证（2026-11-24）
- relief.py 浮雕 / 透光浮雕：输出闭合，打印前检查通过；Bambu 切片成功
- printprep.py：带破洞的多壳体 GLB → 合并为 1 个实体、闭合、加底座，检查通过；Bambu 切片成功（3h）
- gen3d.py：HF 匿名 ZeroGPU 额度为 0 → 免费 Space 不可用（报额度超限 / 排队超时）。**还没用真实 AI 模型跑通全流程**

## 待办
1. 设置 `HF_TOKEN`（免费账号）或提供 Meshy/Tripo Key，用 `work/cat.png` 跑通 `gen3d → printprep → preview → slice`
2. 如果 Space 接口签名变了，按 `references/backends.md` 调整 `gen3d.py`
3. 可选：多色 3MF（贴图分色映射到 AMS）、更严格的壁厚检查

## 安全红线
- 不自动发送到打印机；只有用户明确要求时才连接打印机
- 用户照片会上传到 HF / Meshy / Tripo，使用前要告知用户

## 下一段开场白
> 读本仓库的 CONTINUATION.md，我已设置 HF_TOKEN（或 MESHY_API_KEY），用 work/cat.png 跑通 image-to-print 全流程。
