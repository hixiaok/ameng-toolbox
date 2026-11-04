from PIL import Image, ImageDraw
S = 512
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
# 圆角方块 + 渐变
grad = Image.new("RGB", (S, S))
gd = ImageDraw.Draw(grad)
for y in range(S):
    t = y / S
    r = int(47 + (24 - 47) * t)
    g = int(111 + (79 - 111) * t)
    b = int(235 + (196 - 235) * t)
    gd.line([(0, y), (S, y)], fill=(r, g, b))
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=112, fill=255)
img.paste(grad, (0, 0), mask)
d = ImageDraw.Draw(img)
# 白色的 I：上下横 + 竖
w = 84
cx = S // 2
d.rounded_rectangle([cx - 92, 128, cx + 92, 128 + w], radius=24, fill="white")
d.rounded_rectangle([cx - 92, S - 128 - w, cx + 92, S - 128], radius=24, fill="white")
d.rounded_rectangle([cx - w // 2, 128, cx + w // 2, S - 128], radius=24, fill="white")
img.save(r"D:\deepseek\iris\android\res\mipmap-xxxhdpi\ic_launcher.png")
print("icon written")
