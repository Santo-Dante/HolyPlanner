"""Gera os ícones locais do app; requer Pillow apenas na preparação da entrega."""
from pathlib import Path
from PIL import Image, ImageDraw

root = Path(__file__).resolve().parents[1] / 'frontend'
image = Image.new('RGB', (1024, 1024), '#7c6acb')
draw = ImageDraw.Draw(image)
for coordinates in ((300,300,300,724),(300,510,570,510),(570,300,570,724),(665,724,770,300)):
    draw.line(coordinates, fill='white', width=70)
    for x,y in (coordinates[:2],coordinates[2:]):
        draw.ellipse((x-35,y-35,x+35,y+35),fill='white')
for size in (192,512):
    image.resize((size,size),Image.Resampling.LANCZOS).save(root/f'icon-{size}.png')
image.save(root/'app.ico',sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
