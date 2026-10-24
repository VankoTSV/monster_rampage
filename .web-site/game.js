"use strict";

(() => {
  const VW = 1280, VH = 720, HUD = 96, BORDER = 6, MAX_HP = 5, FPS = 60;
  const ARENA = { x: 0, y: HUD, w: VW, h: VH - HUD };
  const canvas = document.getElementById("game");
  const ctx = canvas.getContext("2d");
  const bg = new Image();
  bg.src = "castle.jpg";
  const keys = new Set();
  const pointer = { x: VW / 2, y: VH / 2, down: false };
  const colors = { white: "#f0f0f0", gray: "#969ba5", yellow: "#ffd640", red: "#eb4646" };
  const saveKey = "monster-rampage-save-v1";

  function readSave() {
    const fallback = { record_score: 0, record_coins: 0, record_level: 0 };
    try { return { ...fallback, ...JSON.parse(localStorage.getItem(saveKey) || "{}") }; }
    catch { return fallback; }
  }
  function writeSave() {
    try { localStorage.setItem(saveKey, JSON.stringify(game.save)); } catch { /* storage may be disabled */ }
  }
  const game = {
    state: "menu", t: 0, sel: 0, save: readSave(), runActive: false, newRecord: false,
    level: 1, coinsCollected: 0, kills: 0, player: null, enemies: [], bullets: [],
    coins: [], particles: [], obstacles: [], hazards: [], coinTimer: 2,
    clearT: 0, introT: 0, hurtT: 0, deco: []
  };

  const rand = (a, b) => a + Math.random() * (b - a);
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const dist2 = (a, b) => (a.x - b.x) ** 2 + (a.y - b.y) ** 2;
  const score = () => game.coinsCollected * 10 + game.kills * 25 + (game.level - 1) * 100;
  const rect = (x, y, w, h) => ({ x, y, w, h });
  const inside = (p, r) => p.x >= r.x && p.x <= r.x + r.w && p.y >= r.y && p.y <= r.y + r.h;

  function circleRect(p, radius, r) {
    const x = clamp(p.x, r.x, r.x + r.w), y = clamp(p.y, r.y, r.y + r.h);
    return (p.x - x) ** 2 + (p.y - y) ** 2 < radius * radius;
  }
  function pushOut(p, radius, r) {
    const x = clamp(p.x, r.x, r.x + r.w), y = clamp(p.y, r.y, r.y + r.h);
    let dx = p.x - x, dy = p.y - y, d2 = dx * dx + dy * dy;
    if (d2 >= radius * radius) return;
    if (d2 > 1e-6) {
      const d = Math.sqrt(d2), k = (radius - d) / d;
      p.x += dx * k; p.y += dy * k;
    } else {
      const edges = [p.x - r.x, r.x + r.w - p.x, p.y - r.y, r.y + r.h - p.y];
      const edge = Math.min(...edges);
      if (edge === edges[0]) p.x = r.x - radius;
      else if (edge === edges[1]) p.x = r.x + r.w + radius;
      else if (edge === edges[2]) p.y = r.y - radius;
      else p.y = r.y + r.h + radius;
    }
  }
  function clampArena(p, radius) {
    p.x = clamp(p.x, ARENA.x + BORDER + radius, ARENA.x + ARENA.w - BORDER - radius);
    p.y = clamp(p.y, ARENA.y + BORDER + radius, ARENA.y + ARENA.h - BORDER - radius);
  }
  function randPoint(r, margin = 0) {
    return { x: rand(r.x + margin, r.x + r.w - margin), y: rand(r.y + margin, r.y + r.h - margin) };
  }

  function tryPlace(area, w, h, avoid, occupied, padX = 0, padY = 0, margin = 46) {
    for (let i = 0; i < 80; i++) {
      if (area.w - w - padX * 2 <= 0 || area.h - h - padY * 2 <= 0) return null;
      const r = rect(rand(area.x + padX, area.x + area.w - w - padX),
        rand(area.y + padY, area.y + area.h - h - padY), w, h);
      const bound = rect(r.x - padX, r.y - padY, r.w + padX * 2, r.h + padY * 2);
      if (dist2(avoid, { x: clamp(avoid.x, bound.x, bound.x + bound.w), y: clamp(avoid.y, bound.y, bound.y + bound.h) }) < 130 ** 2) continue;
      if (occupied.some(o => bound.x - margin < o.x + o.w + margin && bound.x + bound.w + margin > o.x &&
          bound.y - margin < o.y + o.h + margin && bound.y + bound.h + margin > o.y)) continue;
      occupied.push(bound);
      return r;
    }
    return null;
  }
  function genLevel(level, avoid) {
    const obstacles = [], hazards = [], occupied = [];
    const area = rect(40, HUD + 40, VW - 80, VH - HUD - 80);
    const complex = Math.min(.15 * (level - 1), .65);
    for (let n = 0; n < Math.min(3 + level, 11); n++) {
      const roll = Math.random();
      if (roll < complex * .5) {
        const w = rand(110, 200), h = rand(110, 190), r = tryPlace(area, w, h, avoid, occupied);
        if (r) {
          const t = 26, top = Math.random() < .5, left = Math.random() < .5;
          obstacles.push({ r: rect(r.x, top ? r.y : r.y + h - t, w, t), moving: false });
          obstacles.push({ r: rect(left ? r.x : r.x + w - t, r.y, t, h), moving: false });
        }
      } else if (roll < complex) {
        const length = rand(160, 300), t = 24, horizontal = Math.random() < .5;
        const r = tryPlace(area, horizontal ? length : t, horizontal ? t : length, avoid, occupied);
        if (r) obstacles.push({ r, moving: false });
      } else {
        const r = tryPlace(area, rand(56, 110), rand(56, 110), avoid, occupied);
        if (r) obstacles.push({ r, moving: false });
      }
    }
    for (let i = 0; i < Math.max(0, Math.min(level - 2, 5)); i++) {
      const vertical = Math.random() < .5, length = rand(100, 150), amp = rand(70, 140), thick = 28;
      const r = tryPlace(area, vertical ? thick : length, vertical ? length : thick, avoid, occupied,
        vertical ? amp : 0, vertical ? 0 : amp);
      if (r) obstacles.push({ r, moving: true, axis: vertical ? "x" : "y", base: { x: r.x, y: r.y },
        amp, speed: rand(.8, 1.8), phase: rand(0, Math.PI * 2), t: 0 });
    }
    for (let i = 0; i < Math.max(0, Math.min(level - 4, 4)); i++) {
      const s = rand(90, 130), r = tryPlace(area, s, s, avoid, occupied, 0, 0, 30);
      if (r) hazards.push(r);
    }
    return { obstacles, hazards };
  }

  function makeEnemy(p, level) {
    const maxHp = Math.min(2 + Math.floor(level / 3), 6);
    return { x: p.x, y: p.y, r: 17, hp: maxHp, maxHp,
      speed: Math.min(70 + 6 * level, 150) * rand(.85, 1.15),
      interval: Math.max(.6, 2.4 - .2 * (level - 1)), shootT: rand(.8, 3.2),
      target: { ...p }, retarget: 0, flash: 0, phase: rand(0, Math.PI * 2) };
  }
  function startLevel(n) {
    game.level = n;
    const generated = genLevel(n, game.player);
    game.obstacles = generated.obstacles; game.hazards = generated.hazards;
    game.bullets = [];
    game.coins = game.coins.filter(c => !game.obstacles.some(o => circleRect(c, 12, o.r)));
    game.enemies = [];
    for (let i = 0; i < Math.min(3 + n, 14); i++) {
      for (let tries = 0; tries < 120; tries++) {
        const p = randPoint(ARENA, 50);
        if (Math.sqrt(dist2(p, game.player)) < 300) continue;
        if (game.obstacles.some(o => circleRect(p, 30, o.r)) || game.hazards.some(h => circleRect(p, 20, h))) continue;
        game.enemies.push(makeEnemy(p, n)); break;
      }
    }
    game.clearT = 0; game.introT = 1.6;
  }
  function resetRun() {
    game.level = 1; game.coinsCollected = 0; game.kills = 0;
    game.player = { x: VW / 2, y: VH - 90, hp: MAX_HP, cd: 0, invuln: 0, angle: -Math.PI / 2 };
    game.bullets = []; game.coins = []; game.enemies = []; game.particles = [];
    game.obstacles = []; game.hazards = []; game.coinTimer = 2;
    game.clearT = 0; game.introT = 0; game.hurtT = 0;
  }
  function newGame() {
    resetRun(); startLevel(1); game.state = "playing"; game.runActive = true; game.newRecord = false;
  }
  function finishRun() {
    if (!game.runActive) return;
    game.runActive = false;
    if (score() > game.save.record_score) {
      game.save.record_score = score(); game.save.record_coins = game.coinsCollected;
      game.save.record_level = game.level; game.newRecord = true; writeSave();
    }
  }
  function setState(s) { game.state = s; game.sel = 0; }
  function endRun() { finishRun(); setState("gameover"); }
  function menuItems() {
    if (game.state === "menu") return [{ label: "Start new game", action: newGame }, { label: "Settings", action: () => setState("settings") }];
    if (game.state === "settings") return [{ label: "Back", action: () => setState("menu") }];
    if (game.state === "paused") return [{ label: "Resume", action: () => setState("playing") }, { label: "End run", action: endRun }];
    if (game.state === "gameover") return [{ label: "Play again", action: newGame }, { label: "Main menu", action: () => setState("menu") }];
    return [];
  }
  function buttonRect(i) {
    const y = game.state === "paused" ? 360 : game.state === "gameover" ? 540 : 330;
    return rect(VW / 2 - 200, y + i * 66, 400, 54);
  }
  function chooseItem(i) { const items = menuItems(); if (items[i]) items[i].action(); }

  function eventPoint(e) {
    const b = canvas.getBoundingClientRect(), s = Math.min(b.width / VW, b.height / VH);
    return { x: (e.clientX - b.left - (b.width - VW * s) / 2) / s,
      y: (e.clientY - b.top - (b.height - VH * s) / 2) / s };
  }
  canvas.addEventListener("pointermove", e => {
    const p = eventPoint(e); pointer.x = p.x; pointer.y = p.y;
    if (["menu", "settings", "paused", "gameover"].includes(game.state)) {
      menuItems().forEach((_, i) => { if (inside(p, buttonRect(i))) game.sel = i; });
    }
  });
  canvas.addEventListener("pointerdown", e => {
    e.preventDefault(); canvas.focus();
    const p = eventPoint(e); pointer.x = p.x; pointer.y = p.y;
    if (["menu", "settings", "paused", "gameover"].includes(game.state)) {
      menuItems().forEach((_, i) => { if (inside(p, buttonRect(i))) { game.sel = i; chooseItem(i); } });
    } else if (game.state === "playing") pointer.down = true;
  });
  window.addEventListener("pointerup", () => { pointer.down = false; });
  window.addEventListener("keydown", e => {
    const k = e.key.toLowerCase();
    if (["arrowup", "arrowdown", "arrowleft", "arrowright", " "].includes(k)) e.preventDefault();
    keys.add(k);
    if (["menu", "settings", "paused", "gameover"].includes(game.state)) {
      const items = menuItems();
      if (k === "arrowup" || k === "w") game.sel = (game.sel + items.length - 1) % items.length;
      else if (k === "arrowdown" || k === "s") game.sel = (game.sel + 1) % items.length;
      else if (k === "enter" || k === " ") chooseItem(game.sel);
      else if (k === "escape") {
        if (game.state === "settings" || game.state === "gameover") setState("menu");
        else if (game.state === "paused") setState("playing");
      }
    } else if (game.state === "playing" && k === "escape") setState("paused");
  });
  window.addEventListener("keyup", e => keys.delete(e.key.toLowerCase()));
  window.addEventListener("blur", () => { pointer.down = false; keys.clear(); });

  function spawnParticles(p, color, n) {
    for (let i = 0; i < n; i++) {
      const a = rand(0, Math.PI * 2), speed = rand(40, 220), life = rand(.25, .6);
      game.particles.push({ x: p.x, y: p.y, vx: Math.cos(a) * speed, vy: Math.sin(a) * speed,
        life, maxLife: life, color });
    }
  }
  function damagePlayer() {
    const p = game.player;
    if (p.invuln > 0) return;
    p.hp--; p.invuln = 1.2; game.hurtT = .3; spawnParticles(p, "#5aa0ff", 12);
  }
  function updateWorld(dt) {
    const p = game.player;
    for (const o of game.obstacles) if (o.moving) {
      o.t += dt; const off = Math.sin(o.t * o.speed + o.phase) * o.amp;
      o.r[o.axis] = Math.round(o.base[o.axis] + off);
    }
    let mx = Number(keys.has("d") || keys.has("arrowright")) - Number(keys.has("a") || keys.has("arrowleft"));
    let my = Number(keys.has("s") || keys.has("arrowdown")) - Number(keys.has("w") || keys.has("arrowup"));
    const ml = Math.hypot(mx, my);
    if (ml) { p.x += mx / ml * 270 * dt; p.y += my / ml * 270 * dt; }
    for (const o of game.obstacles) pushOut(p, 14, o.r);
    clampArena(p, 14);
    const aim = { x: pointer.x - p.x, y: pointer.y - p.y };
    if (aim.x * aim.x + aim.y * aim.y > 4) p.angle = Math.atan2(aim.y, aim.x);
    p.cd -= dt; p.invuln = Math.max(0, p.invuln - dt); game.hurtT = Math.max(0, game.hurtT - dt);
    if ((pointer.down || keys.has(" ")) && p.cd <= 0) {
      const dx = Math.cos(p.angle), dy = Math.sin(p.angle);
      game.bullets.push({ x: p.x + dx * 22, y: p.y + dy * 22, vx: dx * 680, vy: dy * 680, owner: "player", r: 4, life: 3 });
      p.cd = .17;
    }
    const level = game.level, bSpeed = Math.min(210 + 14 * level, 400), spread = Math.max(.04, .2 - level * .015);
    for (const e of game.enemies) {
      e.flash = Math.max(0, e.flash - dt); e.retarget -= dt;
      if (e.retarget <= 0 || Math.sqrt(dist2(e, e.target)) < 10) { e.target = randPoint(ARENA, 50); e.retarget = rand(.8, 2.2); }
      let dx = e.target.x - e.x, dy = e.target.y - e.y, d = Math.hypot(dx, dy);
      if (d > 1) { e.x += dx / d * e.speed * dt; e.y += dy / d * e.speed * dt; }
      for (const o of game.obstacles) pushOut(e, e.r, o.r);
      clampArena(e, e.r); e.shootT -= dt;
      if (e.shootT <= 0) {
        e.shootT = e.interval * rand(.7, 1.3);
        const base = Math.atan2(p.y - e.y, p.x - e.x) + rand(-spread, spread);
        const angles = level >= 6 && Math.random() < .25 ? [base - .28, base, base + .28] : [base];
        for (const a of angles) {
          const vx = Math.cos(a), vy = Math.sin(a);
          game.bullets.push({ x: e.x + vx * (e.r + 4), y: e.y + vy * (e.r + 4), vx: vx * bSpeed, vy: vy * bSpeed, owner: "enemy", r: 5, life: 3 });
        }
      }
      if (dist2(e, p) < (e.r + 12) ** 2) damagePlayer();
    }
    for (const b of game.bullets) {
      b.x += b.vx * dt; b.y += b.vy * dt; b.life -= dt;
      if (b.life <= 0 || b.x < ARENA.x || b.x > ARENA.w || b.y < ARENA.y || b.y > VH || game.obstacles.some(o => circleRect(b, b.r, o.r))) { b.dead = true; continue; }
      if (b.owner === "player") {
        const e = game.enemies.find(e => dist2(b, e) < (e.r + b.r) ** 2);
        if (e) { b.dead = true; e.hp--; e.flash = .1; spawnParticles(b, "#78ff78", 4); }
      } else if (dist2(b, p) < (14 + b.r) ** 2) { b.dead = true; damagePlayer(); }
    }
    game.bullets = game.bullets.filter(b => !b.dead);
    const alive = [];
    for (const e of game.enemies) {
      if (e.hp > 0) { alive.push(e); continue; }
      game.kills++; spawnParticles(e, "#5adc5a", 18);
      for (let i = 0; i < 1 + (Math.random() < .5 ? 1 : 0); i++) {
        const c = { x: clamp(e.x + rand(-14, 14), ARENA.x + 10, VW - 10), y: clamp(e.y + rand(-14, 14), ARENA.y + 10, VH - 10), age: 0, life: 15, phase: rand(0, 6.28) };
        game.coins.push(c);
      }
    }
    game.enemies = alive;
    for (const h of game.hazards) if (circleRect(p, 12, h)) damagePlayer();
    game.coinTimer -= dt;
    if (game.coinTimer <= 0) {
      game.coinTimer = rand(2.5, 4.5);
      if (game.coins.length < 6) for (let i = 0; i < 40; i++) {
        const c = randPoint(ARENA, 40);
        if (game.obstacles.some(o => circleRect(c, 16, o.r)) || game.hazards.some(h => circleRect(c, 12, h))) continue;
        game.coins.push({ ...c, age: 0, life: 15, phase: rand(0, 6.28) }); break;
      }
    }
    const coins = [];
    for (const c of game.coins) {
      c.age += dt; if (c.age >= c.life) continue;
      if (dist2(c, p) < 24 ** 2) { game.coinsCollected++; spawnParticles(c, colors.yellow, 8); continue; }
      coins.push(c);
    }
    game.coins = coins;
    for (const q of game.particles) { q.life -= dt; q.x += q.vx * dt; q.y += q.vy * dt; q.vx *= .94; q.vy *= .94; }
    game.particles = game.particles.filter(q => q.life > 0);
    game.introT = Math.max(0, game.introT - dt);
    if (p.hp <= 0) { finishRun(); setState("gameover"); return; }
    if (!game.enemies.length) {
      if (game.clearT <= 0) game.clearT = 2.2;
      else if ((game.clearT -= dt) <= 0) { p.hp = Math.min(MAX_HP, p.hp + 1); startLevel(game.level + 1); }
    }
  }
  function update(dt) {
    game.t += dt;
    if (game.state === "menu" || game.state === "settings") {
      for (const d of game.deco) {
        d.x += d.vx * dt; d.y += d.vy * dt;
        if (d.x < 40 || d.x > VW - 40) d.vx *= -1;
        if (d.y < 40 || d.y > VH - 40) d.vy *= -1;
      }
    } else if (game.state === "playing") updateWorld(dt);
  }

  function coverImage() {
    if (!bg.complete || !bg.naturalWidth) { ctx.fillStyle = "#183448"; ctx.fillRect(0, 0, VW, VH); return; }
    const scale = Math.max(VW / bg.naturalWidth, VH / bg.naturalHeight);
    const w = bg.naturalWidth * scale, h = bg.naturalHeight * scale;
    ctx.drawImage(bg, (VW - w) / 2, (VH - h) / 2, w, h);
  }
  function dim(alpha) { ctx.fillStyle = `rgba(0,0,0,${alpha / 255})`; ctx.fillRect(0, 0, VW, VH); }
  function text(s, size, color, x, y, align = "left", bold = true) {
    ctx.font = `${bold ? "bold " : ""}${size}px Arial, sans-serif`; ctx.textAlign = align; ctx.textBaseline = "middle";
    ctx.fillStyle = "#000"; ctx.fillText(s, x + 2, y + 2);
    ctx.fillStyle = color; ctx.fillText(s, x, y);
  }
  function drawHeart(x, y, size, color) {
    const r = size / 4; ctx.fillStyle = color;
    ctx.beginPath(); ctx.arc(x + r, y + r, r, 0, Math.PI * 2); ctx.arc(x + 3 * r, y + r, r, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.moveTo(x, y + r + 2); ctx.lineTo(x + 4 * r, y + r + 2); ctx.lineTo(x + 2 * r, y + 4 * r + 2); ctx.closePath(); ctx.fill();
  }
  function drawMonster(p, r, look, phase = 0, flash = 0, hpFrac = 1) {
    const wob = Math.sin(game.t * 6 + phase) * 2, x = p.x, y = p.y + wob * .3;
    ctx.fillStyle = "#0f140f"; ctx.beginPath(); ctx.ellipse(x, y + r + 1, r, 5, 0, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = "#1c6926";
    ctx.beginPath(); ctx.moveTo(x - r + 3, y - r + 6); ctx.lineTo(x - r + 1, y - r - 9); ctx.lineTo(x - r / 2, y - r + 2); ctx.fill();
    ctx.beginPath(); ctx.moveTo(x + r - 3, y - r + 6); ctx.lineTo(x + r - 1, y - r - 9); ctx.lineTo(x + r / 2, y - r + 2); ctx.fill();
    ctx.fillStyle = "#1c6926"; ctx.beginPath(); ctx.arc(x, y, r + 2, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = flash > 0 ? "#e6ffe6" : "#46c846"; ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
    const ex = r / 2, ey = y - r * .2;
    for (const sx of [-ex, ex]) {
      ctx.fillStyle = "#f0f0f0"; ctx.beginPath(); ctx.arc(x + sx, ey, Math.max(4, r / 3), 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = "#aa1414"; ctx.beginPath(); ctx.arc(x + sx + Math.cos(look) * 2, ey + Math.sin(look) * 2, Math.max(2, r / 6), 0, Math.PI * 2); ctx.fill();
    }
    const my = y + r * .45; ctx.strokeStyle = "#143219"; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(x - ex, my); ctx.lineTo(x + ex, my); ctx.stroke();
    ctx.fillStyle = "#f0f0f0"; for (const tx of [-ex + 4, 0, ex - 4]) { ctx.beginPath(); ctx.moveTo(x + tx - 3, my); ctx.lineTo(x + tx + 3, my); ctx.lineTo(x + tx, my + 5); ctx.fill(); }
    if (hpFrac < 1) { ctx.fillStyle = "#3c0000"; ctx.fillRect(x - r, y - r - 14, 2 * r, 4); ctx.fillStyle = "#e63c3c"; ctx.fillRect(x - r, y - r - 14, 2 * r * hpFrac, 4); }
  }
  function drawMenuBackground() {
    coverImage(); dim(110);
    for (const d of game.deco) drawMonster(d, 30, Math.atan2(VH / 2 - d.y, VW / 2 - d.x), d.phase);
    dim(110);
    if (game.state === "menu") {
      text("MONSTER RAMPAGE", 74, "#6eeb6e", VW / 2, 150, "center");
      text("Time to defeat the monsters hiding under your bed!!!", 22, "#6eeb6e", VW / 2, 215, "center", false);
      if (game.save.record_score > 0) text(`Record: ${game.save.record_score}   (Coins collected: ${game.save.record_coins}; Level: ${game.save.record_level})`, 22, colors.yellow, VW / 2, 270, "center", false);
      else text("No record yet - go set one!", 22, colors.gray, VW / 2, 270, "center", false);
      text("WASD move  |  Mouse aim  |  LMB / SPACE shoot  |  ESC pause", 22, colors.gray, VW / 2, VH - 40, "center", false);
    } else {
      text("SETTINGS", 52, colors.white, VW / 2, 170, "center");
      text("Browser mode", 34, colors.gray, VW / 2, 260, "center");
      text("Use Chrome's full-screen control to expand the game", 22, colors.gray, VW / 2, 300, "center", false);
    }
  }
  function drawButtons() {
    menuItems().forEach((item, i) => {
      const r = buttonRect(i), selected = i === game.sel;
      ctx.fillStyle = selected ? "#327837" : "#262c38"; ctx.beginPath(); ctx.roundRect(r.x, r.y, r.w, r.h, 8); ctx.fill();
      ctx.strokeStyle = selected ? "#8cff8c" : "#5a6273"; ctx.lineWidth = 3; ctx.stroke();
      text(item.label, 34, selected ? colors.white : "#c8cdd7", r.x + r.w / 2, r.y + r.h / 2, "center");
    });
  }
  function drawHazards() {
    const pulse = .5 + .5 * Math.sin(game.t * 4);
    for (const h of game.hazards) {
      ctx.fillStyle = `rgb(${Math.floor(110 + 80 * pulse)},25,25)`; ctx.fillRect(h.x, h.y, h.w, h.h);
      ctx.strokeStyle = "#ff5a3c"; ctx.lineWidth = 3; ctx.strokeRect(h.x, h.y, h.w, h.h);
      ctx.save(); ctx.beginPath(); ctx.rect(h.x, h.y, h.w, h.h); ctx.clip(); ctx.strokeStyle = "#3c0808"; ctx.lineWidth = 3;
      for (let x = h.x - h.h; x < h.x + h.w + h.h; x += 26) { ctx.beginPath(); ctx.moveTo(x, h.y + h.h); ctx.lineTo(x + h.h, h.y); ctx.stroke(); }
      ctx.restore();
    }
  }
  function drawMiniMap() {
    const m = rect(VW - 180, 8, 164, 80);
    ctx.fillStyle = "#0a0c10"; ctx.fillRect(m.x, m.y, m.w, m.h);
    const mm = p => ({ x: m.x + (p.x - ARENA.x) / ARENA.w * m.w, y: m.y + (p.y - ARENA.y) / ARENA.h * m.h });
    for (const h of game.hazards) { const p = mm(h); ctx.fillStyle = "#963232"; ctx.fillRect(p.x, p.y, Math.max(2, h.w / ARENA.w * m.w), Math.max(2, h.h / ARENA.h * m.h)); }
    for (const o of game.obstacles) { const p = mm(o.r); ctx.fillStyle = o.moving ? "#e6aa3c" : "#aab2c3"; ctx.fillRect(p.x, p.y, Math.max(2, o.r.w / ARENA.w * m.w), Math.max(2, o.r.h / ARENA.h * m.h)); }
    const p = mm(game.player); ctx.fillStyle = "#4696ff"; ctx.beginPath(); ctx.arc(p.x, p.y, 4, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = colors.white; ctx.lineWidth = 2; ctx.strokeRect(m.x, m.y, m.w, m.h);
  }
  function drawHud() {
    ctx.fillStyle = "#000000"; ctx.fillRect(0, 0, VW, HUD);
    ctx.strokeStyle = "#5a6273"; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(0, HUD - 1); ctx.lineTo(VW, HUD - 1); ctx.stroke();
    for (let i = 0; i < MAX_HP; i++) drawHeart(20 + i * 38, 30, 28, i < game.player.hp ? "#eb3c50" : "#3c2830");
    text("HEALTH", 16, colors.gray, 20, 18);
    const stat = (x, label, value, color = colors.white) => { text(label, 16, colors.gray, x, 18); text(String(value), 52, color, x, 54); };
    stat(250, "LEVEL", game.level); stat(390, "COINS", game.coinsCollected, colors.yellow);
    stat(560, "SCORE", score()); stat(760, "MONSTERS", game.enemies.length, "#6eeb6e"); stat(930, "RECORD", Math.max(game.save.record_score, 0), colors.gray);
    drawMiniMap();
  }
  function drawWorld() {
    coverImage(); dim(110);
    ctx.save(); ctx.beginPath(); ctx.rect(ARENA.x, ARENA.y, ARENA.w, ARENA.h); ctx.clip();
    drawHazards();
    for (const o of game.obstacles) {
      const r = o.r;
      ctx.fillStyle = o.moving ? "#966928" : "#545a68"; ctx.fillRect(r.x, r.y, r.w, r.h);
      ctx.strokeStyle = o.moving ? "#ffc346" : "#969eae"; ctx.lineWidth = 3; ctx.strokeRect(r.x, r.y, r.w, r.h);
      ctx.strokeStyle = o.moving ? "#5f4119" : "#3c414e"; ctx.lineWidth = 2; ctx.strokeRect(r.x + 6, r.y + 6, r.w - 12, r.h - 12);
    }
    for (const c of game.coins) {
      if (c.life - c.age < 3 && Math.floor(game.t * 8) % 2) continue;
      const bob = Math.sin(game.t * 5 + c.phase), w = Math.max(3, 9 * Math.abs(Math.cos(game.t * 3 + c.phase)));
      ctx.fillStyle = "#96690a"; ctx.beginPath(); ctx.ellipse(c.x, c.y + bob * 2, w + 1, 11, 0, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = colors.yellow; ctx.beginPath(); ctx.ellipse(c.x, c.y + bob * 2, w, 10, 0, 0, Math.PI * 2); ctx.fill();
    }
    for (const b of game.bullets) {
      ctx.fillStyle = b.owner === "player" ? "#5adcff" : "#ff5a28"; ctx.beginPath(); ctx.arc(b.x, b.y, b.r + (b.owner === "player" ? 2 : 3), 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = b.owner === "player" ? colors.white : "#ffdc78"; ctx.beginPath(); ctx.arc(b.x, b.y, Math.max(1, b.r - 1), 0, Math.PI * 2); ctx.fill();
    }
    for (const e of game.enemies) drawMonster(e, e.r, Math.atan2(game.player.y - e.y, game.player.x - e.x), e.phase, e.flash, e.hp / e.maxHp);
    const p = game.player;
    if (!(p.invuln > 0 && Math.floor(game.t * 20) % 2)) {
      ctx.fillStyle = "#0a0c0e"; ctx.beginPath(); ctx.ellipse(p.x, p.y + 13, 14, 5, 0, 0, Math.PI * 2); ctx.fill();
      const dx = Math.cos(p.angle), dy = Math.sin(p.angle);
      ctx.strokeStyle = "#3c414b"; ctx.lineWidth = 8; ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(p.x + dx * 28, p.y + dy * 28); ctx.stroke();
      ctx.strokeStyle = "#aaafbe"; ctx.lineWidth = 4; ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(p.x + dx * 26, p.y + dy * 26); ctx.stroke();
      ctx.fillStyle = "#193778"; ctx.beginPath(); ctx.arc(p.x, p.y, 16, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = "#468cff"; ctx.beginPath(); ctx.arc(p.x, p.y, 14, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = "#b4d7ff"; ctx.beginPath(); ctx.arc(p.x - 4, p.y - 4, 5, 0, Math.PI * 2); ctx.fill();
    }
    for (const q of game.particles) { ctx.globalAlpha = Math.max(0, q.life / q.maxLife); ctx.fillStyle = q.color; ctx.beginPath(); ctx.arc(q.x, q.y, Math.max(1, 4 * q.life / q.maxLife), 0, Math.PI * 2); ctx.fill(); }
    ctx.globalAlpha = 1;
    ctx.restore();
    ctx.strokeStyle = "#787f90"; ctx.lineWidth = BORDER; ctx.strokeRect(ARENA.x + BORDER / 2, ARENA.y + BORDER / 2, ARENA.w - BORDER, ARENA.h - BORDER);
    ctx.strokeStyle = "#3c4250"; ctx.lineWidth = 2; ctx.strokeRect(BORDER * 2, HUD + BORDER * 2, VW - BORDER * 4, VH - HUD - BORDER * 4);
    if (game.hurtT > 0) { ctx.fillStyle = `rgba(225,0,0,${110 * game.hurtT / .3 / 255})`; ctx.fillRect(0, HUD, VW, VH - HUD); }
    drawHud();
    if (game.state === "playing" && game.clearT > 0) {
      text("LEVEL CLEARED!", 52, "#6eff6e", VW / 2, ARENA.y + ARENA.h / 2, "center");
      text("+1 heart  -  grab the coins!", 22, colors.white, VW / 2, ARENA.y + ARENA.h / 2 + 46, "center", false);
    } else if (game.state === "playing" && game.introT > 0) text(`LEVEL ${game.level}`, 52, colors.white, VW / 2, ARENA.y + ARENA.h / 2, "center");
  }
  function drawGameOver() {
    text("GAME OVER", 52, colors.red, VW / 2, 130, "center");
    text(`Coins collected: ${game.coinsCollected}`, 34, colors.yellow, VW / 2, 215, "center");
    text(`Level: ${game.level}`, 34, colors.white, VW / 2, 262, "center");
    text(`Monsters killed: ${game.kills}`, 22, colors.gray, VW / 2, 305, "center", false);
    text(`Score: ${score()}`, 52, colors.white, VW / 2, 365, "center");
    if (game.newRecord) text("NEW RECORD!", 52, "#6eff6e", VW / 2, 440, "center");
    else {
      text(`Record: ${game.save.record_score}  (Coins collected: ${game.save.record_coins}; Level: ${game.save.record_level})`, 22, colors.yellow, VW / 2, 430, "center", false);
      text(`${game.save.record_score - score()} points to beat the record`, 22, colors.gray, VW / 2, 465, "center", false);
    }
  }
  function draw() {
    ctx.clearRect(0, 0, VW, VH);
    if (game.state === "menu" || game.state === "settings") drawMenuBackground();
    else {
      drawWorld();
      if (game.state === "paused") { dim(150); text("PAUSED", 52, colors.white, VW / 2, 270, "center"); }
      else if (game.state === "gameover") { dim(190); drawGameOver(); }
    }
    if (["menu", "settings", "paused", "gameover"].includes(game.state)) drawButtons();
  }
  function resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(VW * dpr); canvas.height = Math.round(VH * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  game.deco = Array.from({ length: 7 }, () => ({ x: rand(60, VW - 60), y: rand(60, VH - 60),
    vx: rand(-60, 60), vy: rand(-60, 60), phase: rand(0, 6.28) }));
  resetRun();
  window.addEventListener("resize", resize); resize();
  let last = performance.now();
  function frame(now) {
    const dt = Math.min((now - last) / 1000, .05); last = now;
    update(dt); draw(); requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
})();
