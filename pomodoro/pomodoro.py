import pygame
import sys
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

def create_pomodoro_image(total_seconds, remaining_seconds, size):
    width, height = size, size
    img = Image.new('RGBA', (width, height), (0,0,0,0))
    draw = ImageDraw.Draw(img)

    # 畫背景圓
    if remaining_seconds == 0:
        draw.ellipse((10, 10, width-10, height-10), fill='black', outline='black', width=2)
    else:
        draw.ellipse((10, 10, width-10, height-10), fill='red', outline='red', width=2)
        # 畫進度
        angle = 360 * (remaining_seconds / total_seconds)
        draw.pieslice((10, 10, width-10, height-10), start=270, end=270 - angle, fill='black')

    # 標示剩餘時間
    font = ImageFont.truetype("/System/Library/Fonts/STHeiti Light.ttc", 72)

    time_str = f"{remaining_seconds // 60:02d}:{remaining_seconds % 60:02d}"
    bbox = draw.textbbox((0, 0), time_str, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    draw.text(((width - 10 - text_width) / 2, (height - 10 - text_height) / 2), time_str, font=font, fill='white')

    return img

pygame.init()
pygame.mixer.init()
beep = pygame.mixer.Sound(BASE_DIR / "ding.wav")
info = pygame.display.Info()
width = height = min(info.current_w, info.current_h-100)

screen = pygame.display.set_mode((width,height))
pygame.display.set_caption("番茄鐘 Countdown Timer")

font = pygame.font.SysFont(None, 72)
clock = pygame.time.Clock()
durations = [1, 5, 25, 50]
index = 2
total_seconds = 25 * 60
time_left = total_seconds

# 自訂一個計時事件，每1000毫秒（1秒）觸發一次
TIMER_EVENT = pygame.USEREVENT + 1
pygame.time.set_timer(TIMER_EVENT, 1000)

running = True
counting = False
finished = False
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == TIMER_EVENT:
            if time_left > 0 and counting:
                time_left -= 1
                if time_left == 0:
                    counting = False
                    finished = True
        elif event.type == pygame.KEYDOWN:
            if not counting:
                if event.key == pygame.K_LEFT:
                    index = (index - 1) % len(durations)
                    total_seconds = durations[index] * 60
                    time_left = total_seconds
                elif event.key == pygame.K_RIGHT:
                    index = (index + 1) % len(durations)
                    total_seconds = durations[index] * 60
                    time_left = total_seconds
                elif event.key == pygame.K_SPACE:
                    counting = True
                    finished = False
                elif event.key == pygame.K_ESCAPE:
                    running = False
            else:
                if event.key == pygame.K_SPACE:
                    # 暫停／繼續功能（可選）
                    counting = False
                elif event.key == pygame.K_ESCAPE:
                    counting = False
                    finished = False
    mins = time_left // 60
    secs = time_left % 60
    time_str = f"{mins:02d}:{secs:02d}"

    screen.fill((30, 30, 30))
    
    # 繪製倒數文字
    #text_surface = font.render(time_str, True, (255, 100, 0))
    #text_rect = text_surface.get_rect(center=(width//2, height//2))
    # 範例：總時間25分鐘，剩餘15分鐘
    img = create_pomodoro_image(total_seconds, time_left, width)
    pygame_img = pygame.image.fromstring(img.tobytes(), img.size, img.mode)
    screen.blit(pygame_img, (0,0))
    #screen.blit(text_surface, text_rect)
    if finished == True:
        beep.play()
    pygame.display.flip()
    clock.tick(2)

pygame.quit()
sys.exit()
