# DeepSeek 蓝鲸吉祥物 — 反向提示词

> 目标：在 Midjourney / Stable Diffusion / DALL-E / Flux 等模型中复现类似风格的卡通蓝鲸形象

---

## 一、核心风格定义

```
flat vector illustration, cute cartoon style, soft rounded shapes, 
clean bold outlines, minimal shading, solid flat colors, 
modern tech mascot design, friendly and approachable, 
white background, high contrast, vibrant but soft palette
```

---

## 二、多平台提示词

### 🎯 Midjourney

**正向：**
```
A cute cartoon blue whale sitting at a laptop, flat vector illustration style, 
clean bold outlines, solid flat colors, soft blue body with lighter belly, 
large expressive eye, small fin touching keyboard, laptop screen showing 
simple UI elements, white background, minimalist tech mascot design, 
modern flat art, friendly expression --ar 3:4 --niji 6 --s 50
```

**反向（--no）：**
```
--no shading, gradient, realistic, 3D render, photorealistic, dark background, 
complex details, noisy, grunge, messy lines, over-detailed, watercolor, 
oil painting, pixel art, chibi, kawaii overload, furry
```

**关键词包：**
```
flat vector, blue whale mascot, tech illustration, clean outline, 
solid colors, minimalist, cute but professional, white bg
```

---

### 🎯 Stable Diffusion / Flux

**正向 Prompt：**
```
flat vector illustration of a cute blue cartoon whale mascot sitting at a 
desk using a laptop, clean solid outlines, flat colors, simple shapes, 
minimalist design, tech company mascot style, friendly face, large eye, 
white background, high quality, sharp focus, modern illustration style
```

**Negative Prompt：**
```
shading, gradient, realistic, photorealistic, 3D render, dark background, 
complex details, noise, messy lines, over-detailed, watercolor, 
oil painting, pixel art, chibi, furry, extra limbs, bad anatomy, 
blurry, low quality, distorted, text, signature, watermark
```

**LoRA / 风格推荐：**
- `flat2` (flat illustration LoRA)
- `vector art style` LoRA
- 采样器：DPM++ 2M Karras / Euler a
- CFG：7
- 步数：25-30

---

### 🎯 DALL-E 3

```
A cute flat vector illustration of a blue whale mascot using a laptop on a desk. 
The style is clean minimalist flat art with bold outlines and solid colors, 
white background, modern tech company mascot style, friendly and approachable. 
The whale has a soft blue body, lighter belly, large cute eye, 
and a small fin resting on the keyboard. No shading, no gradients, no 3D.
```

---

## 三、色彩参数

| 元素 | 色值参考 |
|------|---------|
| 鲸鱼身体 | `#4A90D9` ~ `#3B82F6`（中蓝） |
| 鲸鱼肚皮 | `#D4E8FF` ~ `#BFDBFE`（浅蓝） |
| 鲸鱼眼睛 | `#1E3A5F`（深蓝黑） |
| 电脑/UI元素 | `#1F2937`（深灰） |
| 高亮/点缀 | `#60A5FA`（亮蓝） |

色调特征：低饱和度、柔和、不刺眼，蓝白为主色调，少量深灰点缀。

---

## 四、构图描述

```
- 中心主体：蓝鲸正面/微侧坐姿
- 场景：书桌前使用笔记本电脑
- 视角：平视，主体居中占画面约 50-60%
- 背景：纯白负空间
- 氛围：轻松、友好、科技感
- 鲸鱼姿态：一只鳍放在键盘上，眼睛注视屏幕
- 表情：专注中带一丝微笑
```

---

## 五、风格关键词汇总（可用于任何模型）

```
Style: flat vector illustration, minimalist mascot design, 
clean bold outlines, solid flat colors, no gradients, 
modern tech illustration, friendly corporate mascot, 
cartoon but professional, soft rounded shapes, 
high contrast, simple background, vector art

Character: cute blue whale, large single visible eye, 
light blue belly, small fins, rounded head, 
friendly expression, simple geometric body

Mood: approachable, smart, helpful, warm tech
```

---

## 六、如果想把文字也生成进去

大多数生图模型不擅长生成精确文字。建议：
- 生图时不带文字
- 后期用设计软件（Canva / PS / PPT）加上

---

## 七、变体方向

如果想要不同感觉，可以微调以下参数：

| 变体 | 修改方向 |
|------|---------|
| 更萌 | 增大眼睛占比，身体比例 1:1 → 2:1（头大身小） |
| 更专业 | 减少萌感，加入眼镜/领带元素 |
| 场景扩展 | 鲸鱼站在白板前讲解 / 鲸鱼和用户击掌 |
| 四季版 | 给鲸鱼加围巾/圣诞帽/墨镜 |
