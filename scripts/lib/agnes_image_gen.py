#!/usr/bin/env python3
"""
Agnes Image Generation — 通过 Agnes API 生成图像
Key 从同目录 agnes_token.json 读取，不硬编码

用法:
  python agnes_image_gen.py "一只可爱的猫"
  python agnes_image_gen.py "山水画" --model agnes-image-2.1-flash --size 1024x1024
"""
import argparse, json, urllib.request, sys, os

API_URL = "https://apihub.agnes-ai.com/v1/images/generations"


def _load_key():
    key_file = os.path.join(os.path.dirname(__file__), "agnes_token.json")
    try:
        with open(key_file, "r") as f:
            return json.load(f).get("token", "")
    except Exception as e:
        print("[ERR] 读取 token 失败: %s" % e, file=sys.stderr)
        return ""


def generate(prompt, model="agnes-image-2.1-flash", n=1, size="1024x1024", output_dir=None):
    api_key = _load_key()
    if not api_key:
        return []

    payload = {
        "model": model,
        "prompt": prompt,
        "n": n,
        "size": size,
    }
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": "Bearer %s" % api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "generated")
    os.makedirs(output_dir, exist_ok=True)

    saved = []
    for i, item in enumerate(data.get("data", [])):
        url = item.get("url", "")
        if not url:
            continue
        name = "agnes_%s_%d.png" % (model.replace("/", "_"), i)
        path = os.path.join(output_dir, name)
        urllib.request.urlretrieve(url, path)
        saved.append(path)
        print("[OK] %s" % path)
    return saved


def main():
    parser = argparse.ArgumentParser(description="Agnes 图像生成")
    parser.add_argument("prompt", help="图像描述提示词")
    parser.add_argument("--model", "-m", default="agnes-image-2.1-flash",
                        help="模型 (默认: agnes-image-2.1-flash)")
    parser.add_argument("--size", "-s", default="1024x1024",
                        help="尺寸 (默认: 1024x1024)")
    parser.add_argument("--output", "-o", help="输出目录")
    args = parser.parse_args()

    try:
        generate(args.prompt, args.model, output_dir=args.output)
    except Exception as e:
        print("[ERR] 生成失败: %s" % e)
        sys.exit(1)


if __name__ == "__main__":
    main()
