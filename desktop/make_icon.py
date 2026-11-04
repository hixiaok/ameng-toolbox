from PIL import Image, ImageDraw

S = 512
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
grad = Image.new("RGB", (S, S))
gd = ImageDraw.Draw(grad)
for y in range(S):
    t = y / S
    gd.line(
        [(0, y), (S, y)],
        fill=(int(63 + (15 - 63) * t), int(140 + (95 - 140) * t), int(255 + (196 - 255) * t)),
    )
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=112, fill=255)
img.paste(grad, (0, 0), mask)

d = ImageDraw.Draw(img)
w = 84
cx = S // 2
d.rounded_rectangle([cx - 92, 128, cx + 92, 128 + w], radius=24, fill="white")
d.rounded_rectangle([cx - 92, S - 128 - w, cx + 92, S - 128], radius=24, fill="white")
d.rounded_rectangle([cx - w // 2, 128, cx + w // 2, S - 128], radius=24, fill="white")

img.save(r"D:\deepseek\iris\desktop\iris.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
img.save(r"D:\deepseek\iris\desktop\iris-preview.png")
print("ok")
