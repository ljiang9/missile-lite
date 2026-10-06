#!/usr/bin/env python3
"""missile-lite: 极简导弹指挥官（Missile Command）克隆。

玩法：敌方导弹从天而降，瞄准你的城市；从炮台发射拦截弹，
在空中引爆，用爆炸半径消灭敌方导弹。保护城市，守住炮台弹药。

纯标准库（argparse / sys / random / math），Python 3.10+。
"""
from __future__ import annotations

import argparse
import math
import random
import sys

W, H = 40, 20
GROUND = H - 1
BLAST_R = 3.0          # 爆炸半径（格）
BLAST_FRAMES = 4       # 爆炸持续帧数
INTERCEPTOR_SPEED = 3.0
CITY_XS = [4, 9, 14, 23, 28, 33]
BAT_XS = [1, 19, 38]
AMMO_PER_BATTERY = 10
SCORE_PER_KILL = 25
CITY_BONUS = 100       # 每波结束每座存活城市奖励


class EnemyMissile:
    def __init__(self, x, y, tx, ty, speed=0.6):
        self.x, self.y = float(x), float(y)
        dx, dy = tx - x, ty - y
        d = math.hypot(dx, dy) or 1.0
        self.vx, self.vy = dx / d * speed, dy / d * speed
        self.tx, self.ty = tx, ty
        self.alive = True

    def step(self):
        self.x += self.vx
        self.y += self.vy


class Interceptor:
    def __init__(self, x0, y0, tx, ty, speed=INTERCEPTOR_SPEED):
        self.x, self.y = float(x0), float(y0)
        self.tx, self.ty = float(tx), float(ty)
        dx, dy = self.tx - self.x, self.ty - self.y
        d = math.hypot(dx, dy) or 1.0
        self.vx, self.vy = dx / d * speed, dy / d * speed
        self.arrived = False
        self.blast_t = 0  # 爆炸剩余帧数

    def step(self):
        if self.blast_t > 0:
            self.blast_t -= 1
            return
        if self.arrived:
            return
        nx, ny = self.x + self.vx, self.y + self.vy
        # 是否越过目标点（点积变号）或足够近
        px, py = self.tx - self.x, self.ty - self.y
        if (nx - self.tx) * px + (ny - self.ty) * py <= 0 or math.hypot(px, py) < 0.8:
            self.x, self.y = self.tx, self.ty
            self.arrived = True
            self.blast_t = BLAST_FRAMES
        else:
            self.x, self.y = nx, ny


class Game:
    def __init__(self, seed=None, waves=3, missiles_per_wave=8):
        self.rng = random.Random(seed)
        self.cities = [{"x": x, "alive": True} for x in CITY_XS]
        self.batteries = [{"x": x, "ammo": AMMO_PER_BATTERY, "alive": True} for x in BAT_XS]
        self.missiles: list[EnemyMissile] = []
        self.interceptors: list[Interceptor] = []
        self.score = 0
        self.kills = 0
        self.wave = 0
        self.waves = waves
        self.missiles_per_wave = missiles_per_wave
        self.pending = 0       # 本波待发射的敌导弹数
        self.spawn_cd = 0
        self.over = False

    # ---------- 敌方 ----------
    def spawn_missile(self):
        targets = [c["x"] for c in self.cities if c["alive"]] or [self.rng.randrange(W)]
        tx = self.rng.choice(targets) + self.rng.uniform(-2, 2)
        m = EnemyMissile(self.rng.uniform(0, W - 1), 0, tx, GROUND,
                         speed=self.rng.uniform(0.4, 0.7))
        self.missiles.append(m)

    # ---------- 玩家 ----------
    def fire(self, battery_idx, tx, ty):
        """从 battery_idx 号炮台向 (tx,ty) 发射拦截弹。成功返回 True。"""
        if not (0 <= battery_idx < len(self.batteries)):
            return False
        b = self.batteries[battery_idx]
        if not b["alive"] or b["ammo"] <= 0:
            return False
        b["ammo"] -= 1
        self.interceptors.append(Interceptor(b["x"], GROUND - 1, tx, ty))
        return True

    # ---------- 主循环 ----------
    def step(self):
        if self.over:
            return
        # 发射敌方导弹
        if self.pending > 0:
            self.spawn_cd -= 1
            if self.spawn_cd <= 0:
                self.spawn_missile()
                self.pending -= 1
                self.spawn_cd = self.rng.randint(4, 10)
        # 敌导弹移动 / 落地
        for m in self.missiles:
            if not m.alive:
                continue
            m.step()
            if m.y >= GROUND:
                m.alive = False
                # 摧毁最近的城市（2 格内）；炮台被直接命中则摧毁炮台
                for c in self.cities:
                    if c["alive"] and abs(c["x"] - m.x) <= 2:
                        c["alive"] = False
                        break
                for b in self.batteries:
                    if b["alive"] and abs(b["x"] - m.x) <= 1.5:
                        b["alive"] = False
                        b["ammo"] = 0
                        break
        # 拦截弹移动 / 爆炸杀伤
        for it in self.interceptors:
            it.step()
            if it.blast_t > 0:
                for m in self.missiles:
                    if m.alive and math.hypot(m.x - it.x, m.y - it.y) <= BLAST_R:
                        m.alive = False
                        self.kills += 1
                        self.score += SCORE_PER_KILL
        self.missiles = [m for m in self.missiles if m.alive]
        self.interceptors = [it for it in self.interceptors if it.blast_t > 0 or not it.arrived]
        # 波次结算
        if self.pending == 0 and not self.missiles:
            saved = sum(1 for c in self.cities if c["alive"])
            self.score += saved * CITY_BONUS
            self.wave += 1
            if self.wave >= self.waves or saved == 0:
                self.over = True
            else:
                self.pending = self.missiles_per_wave

    def cities_alive(self):
        return sum(1 for c in self.cities if c["alive"])


def render(g: Game) -> str:
    grid = [[" " for _ in range(W)] for _ in range(H)]
    for i in range(W):
        grid[GROUND][i] = "="
    for c in g.cities:
        if c["alive"]:
            grid[GROUND - 1][c["x"]] = "⌂"
    for bi, b in enumerate(g.batteries):
        if b["alive"]:
            grid[GROUND - 1][b["x"]] = str(bi)
    for m in g.missiles:
        x, y = int(m.x), int(m.y)
        if 0 <= x < W and 0 <= y < GROUND:
            grid[y][x] = "v"
    for it in g.interceptors:
        x, y = int(it.x), int(it.y)
        if 0 <= x < W and 0 <= y < GROUND:
            grid[y][x] = "*" if it.blast_t > 0 else "^"
    return "\n".join("".join(r) for r in grid)


# ---------- AI 无头演示 ----------
def auto_play(seed=None, waves=3, missiles_per_wave=8, verbose=False):
    g = Game(seed=seed, waves=waves, missiles_per_wave=missiles_per_wave)
    g.pending = missiles_per_wave
    frames = 0
    while not g.over and frames < 20000:
        # AI：为每枚敌导弹指派最近的、有弹药的炮台，瞄准其预测位置
        for m in g.missiles:
            if not m.alive:
                continue
            # 是否已有拦截弹正在处理它
            covered = any(
                it.blast_t > 0 and math.hypot(m.x - it.x, m.y - it.y) <= BLAST_R + 1.5
                for it in g.interceptors
            )
            if covered:
                continue
            best, best_d = None, 1e9
            for bi, b in enumerate(g.batteries):
                if b["alive"] and b["ammo"] > 0:
                    d = abs(b["x"] - m.x)
                    if d < best_d:
                        best, best_d = bi, d
            if best is None:
                continue
            bx = g.batteries[best]["x"]
            travel = math.hypot(m.x - bx, m.y - (GROUND - 1)) / INTERCEPTOR_SPEED
            px = m.x + m.vx * travel
            py = m.y + m.vy * travel
            g.fire(best, px, py)
        g.step()
        frames += 1
    if verbose:
        print(render(g))
    return g, frames


def play_interactive(seed=None):
    if not sys.stdin.isatty():
        print("交互模式需要终端；请用 --auto 观看无头演示。", file=sys.stderr)
        sys.exit(2)
    g = Game(seed=seed)
    g.pending = g.missiles_per_wave
    print("导弹指挥官！命令：fire <炮台0-2> <x> <y> | q 退出")
    while not g.over:
        print(render(g))
        print(f"波次 {g.wave + 1}/{g.waves} 城市 {g.cities_alive()}/6 "
              f"弹药 {[b['ammo'] for b in g.batteries]} 得分 {g.score}")
        try:
            line = input("> ").strip()
        except EOFError:
            break
        if line == "q":
            break
        parts = line.split()
        if len(parts) == 4 and parts[0] == "fire":
            try:
                bi, tx, ty = int(parts[1]), float(parts[2]), float(parts[3])
            except ValueError:
                print("格式：fire <炮台> <x> <y>")
                continue
            if not g.fire(bi, tx, ty):
                print("发射失败（炮台被毁或无弹药）")
        else:
            print("格式：fire <炮台> <x> <y>")
        g.step()
    print(f"游戏结束！得分 {g.score}，击杀 {g.kills}，存活城市 {g.cities_alive()}/6")


def main(argv=None):
    ap = argparse.ArgumentParser(description="missile-lite：极简导弹指挥官")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--auto", action="store_true", help="无头 AI 演示")
    ap.add_argument("--waves", type=int, default=3)
    ap.add_argument("--missiles", type=int, default=8, help="每波敌导弹数")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)
    if args.auto:
        g, frames = auto_play(seed=args.seed, waves=args.waves,
                              missiles_per_wave=args.missiles, verbose=args.verbose)
        print(f"自动演示结束：波次 {g.wave}/{args.waves}，得分 {g.score}，"
              f"击杀 {g.kills}，存活城市 {g.cities_alive()}/6，帧数 {frames}")
    else:
        play_interactive(seed=args.seed)


if __name__ == "__main__":
    main()
