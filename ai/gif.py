from pathlib import Path
from typing import Any, Dict

from ai.exceptions import AIError


def generate_gif(question_text: str, simplified_text: str, out_path: str | Path) -> Dict[str, Any]:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return {"status": "failed", "gif_path": None}

    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    width, height = 600, 340
    bg_colors = [(240, 244, 248), (230, 242, 255), (235, 248, 245), (255, 250, 240)]

    # Split texts into readable lines
    def wrap_text(txt, max_chars=40):
        words = txt.split()
        lines = []
        cur = []
        for w in words:
            if sum(len(x) for x in cur) + len(w) + len(cur) <= max_chars:
                cur.append(w)
            else:
                lines.append(" ".join(cur))
                cur = [w]
        if cur:
            lines.append(" ".join(cur))
        return lines

    q_lines = wrap_text(question_text, 45)[:3]
    s_lines = wrap_text(simplified_text, 45)[:4]

    frames = []

    # Frame 1: Problem Overview
    im1 = Image.new("RGB", (width, height), bg_colors[0])
    d1 = ImageDraw.Draw(im1)
    d1.rectangle([(20, 20), (width - 20, height - 20)], outline=(59, 130, 246), width=3)
    d1.text((40, 40), "NEURA VISUAL EXPLAINER", fill=(30, 58, 138))
    d1.text((40, 70), "Step 1: The Core Question", fill=(100, 116, 139))
    y = 110
    for l in q_lines:
        d1.text((40, y), l, fill=(15, 23, 42))
        y += 28
    frames.append(im1)

    # Frame 2: Breakdown / Concept
    im2 = Image.new("RGB", (width, height), bg_colors[1])
    d2 = ImageDraw.Draw(im2)
    d2.rectangle([(20, 20), (width - 20, height - 20)], outline=(16, 185, 129), width=3)
    d2.text((40, 40), "NEURA VISUAL EXPLAINER", fill=(6, 95, 70))
    d2.text((40, 70), "Step 2: Simplified Principle", fill=(100, 116, 139))
    y = 110
    for l in s_lines:
        d2.text((40, y), l, fill=(15, 23, 42))
        y += 28
    frames.append(im2)

    # Frame 3: Key Insight / Method
    im3 = Image.new("RGB", (width, height), bg_colors[2])
    d3 = ImageDraw.Draw(im3)
    d3.rectangle([(20, 20), (width - 20, height - 20)], outline=(245, 158, 11), width=3)
    d3.text((40, 40), "NEURA VISUAL EXPLAINER", fill=(180, 83, 9))
    d3.text((40, 70), "Step 3: Path to Solution", fill=(100, 116, 139))
    d3.text((40, 120), "Apply the simplified principle step by step:", fill=(15, 23, 42))
    d3.text((60, 160), "1. Identify knowns and unknowns", fill=(51, 65, 85))
    d3.text((60, 195), "2. Match with standard formula", fill=(51, 65, 85))
    d3.text((60, 230), "3. Check units and signs carefully", fill=(51, 65, 85))
    frames.append(im3)

    try:
        frames[0].save(
            target,
            save_all=True,
            append_images=frames[1:],
            duration=1500,
            loop=0,
            optimize=True,
        )
        return {"status": "ready", "gif_path": str(target)}
    except Exception as exc:
        return {"status": "failed", "gif_path": None}

