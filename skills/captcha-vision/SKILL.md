---
name: captcha-vision
description: >-
  验证码视觉识别模型训练与本地推理 skill。用于用户明确要求训练/微调/加速验证码图片识别模型、GT4 nine/icon 识别、YOLOv8 detect/classify、Chinese-CLIP 伪标注、GPU 训练、server-oracle 标注、pair/assignment ranker、ONNX 导出、PyCharm main.py 入口、批量 fresh 验收或压缩单次运行耗时。协议目标优先级更高：只要任务要恢复 `/load` 到 `/verify`、challenge/PoW/GCT/AES/RSA、`w`、轨迹、verify/check 或通过后的业务回放，即使同时提到 `best.pt`、YOLO 或已有视觉模型，也由 `captcha-reverse` 主责；只有明确模型/识别交付且排除协议恢复时才使用本 skill。不要用于协议壳、PoW/GCT/AES/RSA、w 参数恢复、滑块/文字点选/消消乐/无感协议复现；这些交给 `captcha-reverse`。
---

# 验证码视觉识别训练

本 skill 只负责图片识别模型、排序器、本地推理速度和验收方法。协议层的 `/load`、PoW、GCT `biht`、bundle 动态字段、AES/RSA `w`、`/verify` 参数和服务端通过判据归 `captcha-reverse`；本 skill 通过调用已有协议 runner 做 fresh 验收。

若用户明确要求“只输出阶段门”，按 `../_shared/js-reverse-workflow.md` 的 Stage-Gate Output 返回 `MODE`、`OWNER`、`NEXT_GATE`、`REQUIRED_EVIDENCE` 和 `DO_NOT_USE`，不要开始训练、采集或实现。`skill_checkpoint` 字段规则见同文件 Checkpoint Fields。

## 触发边界

使用本 skill：

- 用户说“训练识别模型”“图标点选识别”“九宫格识别”“YOLOv8 训练”“CLIP 伪标注”“server oracle 标注”“模型提速”“导出 ONNX”“PyCharm 右键运行”。
- 目标目录里有 GT4 nine/icon 图片材料：`imgs`、`ques_*.png`、`tile_*.jpg`、`contact_sheet.jpg`、`manifest.json`、`oracle_cache/`、`runs/detect/.../best.pt`。
- 用户要求输出 `best.pt`、ranker JSON、ONNX、批量 fresh 通过率、失败样本 hard negatives 或单次运行耗时分析。

不要使用本 skill：

- 目标是恢复 `w`、PoW、GCT、AES/RSA、`captcha_type` 的 `/verify` 协议。
- 目标是滑块距离、轨迹、无感、消消乐、五子棋规则解法或验证码通过后的业务接口回放。
- 目标只是普通 OCR、非验证码图片分类或通用目标检测教程。

## 默认判断

先分清题型和模型形态：

- GT4 `nine`：固定 3x3 分类/检索题。识别器输出三个 0 基 tile 索引，协议层再转 1 基 `[row,col]`。
- GT4 `icon`：背景图目标检测 + 三个提示图标按顺序匹配。识别器输出三个背景中心点，协议层再转 `round(ratio*10000)` 坐标。
- `svg_seed`：不是本 skill 的普通检测任务，优先由 `captcha-reverse` 离线解析 SVG 帧和 `passtime`。

不要只看本地 top1/top5 或可视化是否像对了。最终模型验收必须通过 fresh challenge 的真实 `/verify` 响应统计。

## 工程布局

推荐在目标项目下放独立识别目录：

```text
recognition/
  labels.txt
  collect_*_challenges.py
  build_*_dataset.py
  train_yolo_*.py
  run_*_oracle_trials.py
  oracle_cache/
  runs/detect/.../weights/best.pt
  ranker_*.json
  assignment_ranker_*.json
```

项目根目录可放 `main.py` 做 PyCharm 右键运行；运行缓存默认写到根目录 `js_reverse_cache/`，避免污染训练集。

## Maintenance Check

修改视觉/协议边界、fresh 验收规则或触发描述后运行 `python scripts/validate_skill.py <skill-root>`，再运行通用 `quick_validate.py`。

## GPU 环境

先确认 PyTorch CUDA 真可用：

```bash
python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NO CUDA')"
```

Windows + RTX 3050 训练 YOLO 时遇到过：

```text
OSError: [WinError 1455] page file too small ... nvperf_host.dll
```

处理经验：训练命令加 `--workers 0 --close-mosaic 0`，必要时降低 batch；不要把这个报错误判成模型或数据集问题。

## GT4 nine 路线

数据处理：

1. 保存同轮 `nine.jpg`、`ques_*.png`、`manifest.json`。
2. 透明提示图合成白底 `ques_0_white.jpg`。
3. 按 `nine_nums` 等分 `nine.jpg` 为 `tile_0.jpg` 到 `tile_8.jpg`，0 基索引从左到右、从上到下。
4. 生成 `contact_sheet.jpg` 只用于排错，快速运行可跳过。

没有人工标注集时，先用 Chinese-CLIP 伪标注，再训练 YOLO 分类模型。经验值：120 轮约 1200 张原始图，增强后约 1700+ 训练图可跑出可用初版；提示图数量少，必须做 `question-repeat`，否则线稿类容易被误判。

推荐推理策略是 `fast`：YOLO 能稳定命中时走 `yolo_only`；否则用 CLIP 提示图 top5 + YOLO/CLIP 小格融合。`passtime=0` 可以作为官方 Demo 压测项，但代码必须写成 `args.passtime if args.passtime is not None else random...`，避免 `0` 被 `or random` 吞掉。

## GT4 icon 路线

普通图标点选不要套九宫格分类。它需要检测背景候选并按 `ques_0/1/2` 做 ordered assignment。

已验证的训练路线：

1. 批量采集 `/load`，保存 `bg.jpg`、`ques_0/1/2.png`、`manifest.json` 和真实 `/verify` 响应。
2. 从 `ques_*.png` 建立 icon class 字典；本次官方 Demo 采集到 201 轮、603 个提示图、109 个图标类。
3. 用提示图合成 synthetic YOLO detect 数据，再用 server-oracle 成功样本做 mixed fine-tune。
4. 检测器只解决候选框召回；最终排序要训练 pair ranker 和 assignment ranker。
5. active mining：正常 3 次失败后可继续 24 次 oracle search；成功 assignment 作为 positive，失败 attempts 作为 hard negatives。

本次稳定经验：

```text
v3 detector: recognition/runs/detect/gt4_icon_mixed_finetune_v3/weights/best.pt
pair ranker: recognition/ranker_v3_detector.json
assignment ranker: recognition/assignment_ranker_v3_detector.json
3-attempt stable check: 42/50 = 84%
single attempt: about 55%
```

不要把短跑 `20/20` 当作稳定成功率；稳定口径优先看 50+ fresh rounds。icon 的主要剩余问题通常是相似图标的排序/匹配，不是单纯检测框。

## ONNX 与提速

ONNX 可以导出，但必须先做同图 parity 和 fresh 验收。已验证命令：

```bash
python -c "from ultralytics import YOLO; YOLO(r'recognition/runs/detect/gt4_icon_mixed_finetune_v3/weights/best.pt').export(format='onnx', imgsz=640, opset=12, simplify=False, dynamic=True)"
```

本次 icon 实测结论：ONNX 坐标接近 PT，但类别分数分布和 Ultralytics PT 路径不一致，导致 `/verify` 成功率下降。因此默认入口继续使用 `.pt`，ONNX 只作为实验开关。不要为了启动速度牺牲已验证成功率。

真正压缩右键运行耗时的优先级：

1. 跳过 contact sheet、debug 图片、cookies/load.jsonp 等非必要 artifact。
2. 缓存 bundle metadata，避免每轮重新解析大 JS。
3. 同一轮只下载/计算一次 GCT `biht`。
4. 控制台只打印真实 `/verify` raw response，汇总写 JSON。
5. 若还要继续压，做常驻服务预加载模型；新进程冷启动 `torch/ultralytics/weights` 是最大固定成本。

## 验收规则

批量验收必须用 fresh challenge：

```bash
python recognition/run_yolo_oracle_trials.py --model recognition/runs/detect/gt4_icon_mixed_finetune_v3/weights/best.pt --ranker recognition/ranker_v3_detector.json --ranking-weights recognition/ranking_weights_v3_detector.json --assignment-ranker recognition/assignment_ranker_v3_detector.json --rerank-pool 24 --rounds 20 --max-verify-attempts 3 --primary-attempts 3 --passtime 0
```

报告里至少记录：

- CUDA 是否真实启用。
- 数据集规模、类别数、train/val/test 数量。
- 权重路径、训练指标和 fresh 成功率。
- 失败样本 cache、hard negatives 和是否进入 active mining。
- 推理耗时拆分：冷启动、采集下载、模型推理、排序、`w` 生成、`/verify`。
- PyCharm `main.py` 默认模型和可选 ONNX 开关。

## 清理规则

训练和压测后可清理：

- 根目录 `js_reverse_cache/`
- 采集缓存里的临时 challenge 目录
- `__pycache__/`

不要误删：

- `runs/.../weights/best.pt`：主训练产物。
- `oracle_cache/`、active mining cache：复训和 hard negative 的核心资产。
- `labels.txt`、ranker JSON、assignment ranker JSON。
