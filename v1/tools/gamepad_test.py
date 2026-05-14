"""手柄诊断"""
import pygame, time, sys

pygame.init()
screen = pygame.display.set_mode((300, 100))
count = pygame.joystick.get_count()

print(f"\n找到 {count} 个手柄:")
for i in range(count):
    j = pygame.joystick.Joystick(i)
    j.init()
    print(f"  [{i}] {j.get_name()}")

if count == 0:
    sys.exit(0)

idx = 0
j = pygame.joystick.Joystick(idx)
j.init()
print(f"\n测试 [{idx}] {j.get_name()}")
print("请在5秒内:")
print("  1) 左摇杆转圈")
print("  2) 按L2再松开")
print("  3) 按几个按键")
print("-" * 30)

start = time.time()
while time.time() - start < 5:
    pygame.event.pump()
    for i in range(j.get_numaxes()):
        v = j.get_axis(i)
        if abs(v) > 0.05:
            print(f"  轴{i}={v:.3f}")
    for k in range(j.get_numbuttons()):
        if j.get_button(k):
            print(f"  按钮{k}")
    time.sleep(0.03)

print("完成")
pygame.quit()
