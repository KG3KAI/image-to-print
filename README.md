# image-to-print

把照片、手绘、Logo 或 AI 生成的图片转成可 3D 打印的 STL/3MF，并输出打印前检查报告。Codex 和 Claude Code 通用。

## 路线

| 需求 | 方式 |
|---|---|
| 手办、宠物、物件（立体模型） | AI 图生 3D：Hugging Face 免费空间（混元 3D 2.1 / 2、TripoSG、TRELLIS.2），或付费 Meshy / Tripo |
| 浮雕、透光浮雕、浮凸 Logo / 钥匙扣 | 本地高度图算法，不需要 AI，输出必闭合 |

所有路线最后都经过 `printprep.py`：修复、合并重叠部件、摆正朝向、按毫米缩放、可选加底座或挖空，然后检查（闭合、实体数、平台尺寸、接触面积、重心、悬垂）。

## 安装

```bash
git clone git@github.com:KG3KAI/image-to-print.git
cd image-to-print && ./install.sh
```

`install.sh` 创建 `~/.image-to-print-venv`，并把 Skill 软链接到 `~/.codex/skills` 和 `~/.claude/skills`。

可选环境变量：`HF_TOKEN`（免费空间额度）、`MESHY_API_KEY`、`TRIPO_API_KEY`。

## 脚本

- `gen3d.py`：图片 → 3D 网格
- `relief.py`：图片 → 浮雕 / 透光浮雕 / 浮凸 STL
- `printprep.py`：修复 + 缩放 + 检查，退出码 2 表示未通过
- `preview.py`：四视图 PNG
- `slice_bambu.sh`：Bambu Studio 离线切片验证（不发送到打印机）

## 状态

浮雕类和打印前处理已验证，可通过 Bambu Studio 切片。AI 图生 3D 需要 `HF_TOKEN` 或付费 Key，尚未用真实模型跑通，见 `CONTINUATION.md`。

注意：用 AI 后端时，图片会上传到 Hugging Face / Meshy / Tripo。
