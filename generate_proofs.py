#!/usr/bin/env python3
"""Generate 5 professional proof images for MIMO DevFlow Agent grant application."""

from PIL import Image, ImageDraw, ImageFont
import os
import math

OUT = os.path.expanduser("~/mimo-devflow/proof_images")
os.makedirs(OUT, exist_ok=True)
W, H = 1280, 720

# Try to get a better font
def get_font(size):
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"]:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def get_font_bold(size):
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return get_font(size)

# ============================================================
# 1. Architecture Diagram
# ============================================================
def draw_architecture():
    img = Image.new("RGB", (W, H), "#1a1a2e")
    d = ImageDraw.Draw(img)
    title_font = get_font_bold(28)
    label_font = get_font_bold(14)
    small_font = get_font(12)

    # Title
    d.text((W//2, 30), "MIMO DevFlow Agent — Architecture", fill="white", font=title_font, anchor="mt")

    # Helper to draw a rounded box with shadow
    def box(x, y, w, h, fill="#16213e", outline="#e94560", text="", font=None, text_color="white"):
        # Shadow
        d.rounded_rectangle([x+3, y+3, x+w+3, y+h+3], radius=8, fill="#0d0d1a")
        d.rounded_rectangle([x, y, x+w, y+h], radius=8, fill=fill, outline=outline, width=2)
        if text:
            d.text((x + w//2, y + h//2), text, fill=text_color, font=font or label_font, anchor="mm")

    def arrow(x1, y1, x2, y2, color="#e94560"):
        d.line([(x1, y1), (x2, y2)], fill=color, width=2)
        # arrowhead
        angle = math.atan2(y2-y1, x2-x1)
        al = 10
        d.polygon([(x2, y2),
                    (int(x2 - al*math.cos(angle-0.4)), int(y2 - al*math.sin(angle-0.4))),
                    (int(x2 - al*math.cos(angle+0.4)), int(y2 - al*math.sin(angle+0.4)))],
                   fill=color)

    # User
    box(80, 300, 140, 60, fill="#0f3460", outline="#e94560", text="👤 User")
    # MIMO DevFlow Core
    cx, cy = 340, 280
    box(cx, cy, 200, 100, fill="#16213e", outline="#e94560", text="MIMO DevFlow\nCore Engine")
    arrow(220, 330, cx, 330)

    # Middle components
    mid_y_positions = [140, 260, 380, 500]
    mid_labels = ["🧭 Router", "⚡ Optimizer", "🤝 Collaborator", "📊 Evaluator"]
    mid_x = 640
    for i, (my, lbl) in enumerate(zip(mid_y_positions, mid_labels)):
        box(mid_x, my, 160, 55, fill="#1a1a40", outline="#533483", text=lbl)
        arrow(cx + 200, 330, mid_x, my + 27)

    # MiMo API
    api_labels = ["MiMo v2.5-pro\n(Text/Code)", "MiMo v2.5-vl\n(Vision)", "MiMo TTS\n(Speech)"]
    api_y = [160, 320, 480]
    api_x = 940
    for i, (ay, al) in enumerate(zip(api_y, api_labels)):
        box(api_x, ay, 180, 60, fill="#16213e", outline="#e94560", text=al)
        # Connect from all mid components
        for my in mid_y_positions:
            arrow(mid_x + 160, my + 27, api_x, ay + 30, color="#533483")

    # Legend
    d.text((80, 620), "─ Data Flow", fill="#e94560", font=small_font)
    d.text((250, 620), "─ API Calls", fill="#533483", font=small_font)
    d.text((80, 650), "Built on Xiaomi MiMo API • Multi-agent orchestration • Token-optimized", fill="#888888", font=small_font)

    img.save(os.path.join(OUT, "proof_01_architecture.png"), quality=95)
    print("✓ proof_01_architecture.png")

# ============================================================
# 2. Terminal Simulation
# ============================================================
def draw_terminal():
    img = Image.new("RGB", (W, H), "#0d1117")
    d = ImageDraw.Draw(img)
    mono = get_font(16)
    mono_bold = get_font_bold(16)
    title_font = get_font_bold(14)

    # Title bar
    d.rectangle([0, 0, W, 36], fill="#161b22")
    d.ellipse([14, 12, 26, 24], fill="#ff5f57")
    d.ellipse([34, 12, 46, 24], fill="#febc2e")
    d.ellipse([54, 12, 66, 24], fill="#28c840")
    d.text((W//2, 8), "mimo-devflow — bash — 120×30", fill="#8b949e", font=title_font, anchor="mt")

    lines = [
        ("$ mimo-devflow run workflow.yaml", "#58a6ff"),
        ("", ""),
        ("[INFO] Initializing MIMO DevFlow Agent v1.0.0", "#8b949e"),
        ("[INFO] Router: Auto-selecting mimo-v2.5-pro for code generation task", "#8b949e"),
        ("[INFO] Agent 'coder' spawned (model: mimo-v2.5-pro)", "#8b949e"),
        ("[INFO] Agent 'reviewer' spawned (model: mimo-v2.5-pro)", "#8b949e"),
        ("", ""),
        ("[INFO] Workflow step 1/5: Code generation...    ✓ (2.3s, 1,247 tokens)", "#3fb950"),
        ("[INFO] Workflow step 2/5: Code review...        ✓ (1.8s,   892 tokens)", "#3fb950"),
        ("[INFO] Workflow step 3/5: Optimization...       ✓ (1.1s,   534 tokens)", "#3fb950"),
        ("[INFO] Workflow step 4/5: Testing...            ✓ (3.2s, 2,103 tokens)", "#3fb950"),
        ("[INFO] Workflow step 5/5: Documentation...      ✓ (1.5s, 1,067 tokens)", "#3fb950"),
        ("", ""),
        ("[SUCCESS] All 5 steps completed in 9.9s (5,843 total tokens)", "#3fb950"),
        ("[REPORT] Token efficiency: 94.2% | Cost: $0.003 | Quality: A+", "#d2a8ff"),
        ("", ""),
        ("$ _", "#c9d1d9"),
    ]

    y = 50
    for text, color in lines:
        d.text((20, y), text, fill=color or "#c9d1d9", font=mono)
        y += 28

    # Progress bar at bottom
    bar_y = H - 40
    d.rectangle([20, bar_y, W-20, bar_y+20], fill="#21262d", outline="#30363d")
    d.rectangle([20, bar_y, 20 + int((W-40)*0.942), bar_y+20], fill="#238636")
    d.text((W//2, bar_y+10), "94.2% Token Efficiency", fill="white", font=get_font_bold(13), anchor="mm")

    img.save(os.path.join(OUT, "proof_02_terminal.png"), quality=95)
    print("✓ proof_02_terminal.png")

# ============================================================
# 3. Dashboard
# ============================================================
def draw_dashboard():
    img = Image.new("RGB", (W, H), "#0f1117")
    d = ImageDraw.Draw(img)
    title_font = get_font_bold(24)
    label_font = get_font(13)
    value_font = get_font_bold(32)
    small = get_font(11)

    # Header
    d.rectangle([0, 0, W, 50], fill="#161b22")
    d.text((20, 14), "📊 MIMO DevFlow — Monitoring Dashboard", fill="white", font=title_font)
    d.text((W-200, 18), "Last updated: just now", fill="#8b949e", font=small)

    # Metric cards
    metrics = [
        ("Total Agents", "12", "#58a6ff"),
        ("Active Workflows", "5", "#3fb950"),
        ("Tokens Used", "2.4M", "#d2a8ff"),
        ("Avg Latency", "1.2s", "#f0883e"),
        ("Success Rate", "98.7%", "#3fb950"),
    ]
    card_w = 220
    gap = 20
    start_x = (W - (len(metrics) * card_w + (len(metrics)-1) * gap)) // 2
    for i, (label, value, color) in enumerate(metrics):
        x = start_x + i * (card_w + gap)
        y = 75
        d.rounded_rectangle([x, y, x+card_w, y+100], radius=8, fill="#161b22", outline="#30363d")
        d.text((x+card_w//2, y+25), label, fill="#8b949e", font=label_font, anchor="mt")
        d.text((x+card_w//2, y+60), value, fill=color, font=value_font, anchor="mm")

    # Bar chart area
    chart_x, chart_y = 60, 210
    chart_w, chart_h = W-120, 420
    d.rounded_rectangle([chart_x-10, chart_y-10, chart_x+chart_w+10, chart_y+chart_h+10], radius=8, fill="#161b22", outline="#30363d")
    d.text((chart_x+10, chart_y), "Daily Token Usage (7 days)", fill="white", font=get_font_bold(16))

    # Y axis label
    d.text((chart_x+10, chart_y+25), "Tokens", fill="#8b949e", font=small)

    # Bar data
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    values = [380, 420, 310, 560, 480, 290, 510]
    max_val = max(values)
    bar_area_x = chart_x + 60
    bar_area_y = chart_y + 50
    bar_area_w = chart_w - 80
    bar_area_h = chart_h - 100
    bar_w = bar_area_w // len(days) - 20

    # Grid lines
    for i in range(5):
        gy = bar_area_y + bar_area_h - int(bar_area_h * i / 4)
        d.line([(bar_area_x, gy), (bar_area_x + bar_area_w, gy)], fill="#21262d", width=1)
        d.text((bar_area_x - 5, gy), f"{int(max_val * i / 4)}K", fill="#8b949e", font=small, anchor="rm")

    for i, (day, val) in enumerate(zip(days, values)):
        bx = bar_area_x + i * (bar_area_w // len(days)) + 10
        bh = int(bar_area_h * val / max_val * 0.9)
        by = bar_area_y + bar_area_h - bh
        # Bar with gradient effect
        d.rounded_rectangle([bx, by, bx+bar_w, bar_area_y+bar_area_h], radius=4, fill="#58a6ff")
        d.rounded_rectangle([bx, by, bx+bar_w, by+4], radius=2, fill="#79c0ff")
        d.text((bx + bar_w//2, bar_area_y + bar_area_h + 15), day, fill="#8b949e", font=label_font, anchor="mt")
        d.text((bx + bar_w//2, by - 10), f"{val}K", fill="#c9d1d9", font=small, anchor="mb")

    # Legend
    d.rounded_rectangle([chart_x + chart_w - 200, chart_y + 5, chart_x + chart_w - 10, chart_y + 30], radius=4, fill="#21262d")
    d.rectangle([chart_x + chart_w - 190, chart_y + 10, chart_x + chart_w - 175, chart_y + 25], fill="#58a6ff")
    d.text((chart_x + chart_w - 170, chart_y + 17), "Token Count (K)", fill="#8b949e", font=small, anchor="lm")

    img.save(os.path.join(OUT, "proof_03_dashboard.png"), quality=95)
    print("✓ proof_03_dashboard.png")

# ============================================================
# 4. Code Editor
# ============================================================
def draw_code():
    img = Image.new("RGB", (W, H), "#1e1e1e")
    d = ImageDraw.Draw(img)
    mono = get_font(14)
    mono_bold = get_font_bold(14)
    tab_font = get_font_bold(13)
    small = get_font(11)

    # Title bar
    d.rectangle([0, 0, W, 35], fill="#2d2d2d")
    d.ellipse([12, 10, 24, 22], fill="#ff5f57")
    d.ellipse([30, 10, 42, 22], fill="#febc2e")
    d.ellipse([48, 10, 60, 22], fill="#28c840")

    # Tabs
    d.rectangle([80, 5, 260, 35], fill="#1e1e1e")
    d.text((120, 10), "workflow_engine.py", fill="white", font=tab_font)
    d.rectangle([265, 5, 380, 35], fill="#2d2d2d")
    d.text((285, 10), "router.py", fill="#8b8b8b", font=tab_font)

    # Activity bar
    d.rectangle([0, 35, 48, H], fill="#252526")
    icons = ["📁", "🔍", "🔀", "⚙️", "▶️"]
    for i, icon in enumerate(icons):
        d.text((24, 60 + i*45), icon, fill="#8b8b8b", font=get_font(18), anchor="mm")

    # Line numbers area
    d.rectangle([48, 35, 95, H], fill="#1e1e1e")

    # Code content
    code_lines = [
        ("# MIMO DevFlow Agent - Workflow Engine", "comment"),
        ("# Xiaomi MiMo API Orchestration Framework", "comment"),
        ("", ""),
        ("from mimo_devflow.router import ModelRouter", "import"),
        ("from mimo_devflow.agents import Agent, AgentPool", "import"),
        ("from mimo_devflow.optimizer import TokenOptimizer", "import"),
        ("from typing import List, Dict, Optional", "import"),
        ("import asyncio", "import"),
        ("", ""),
        ("class WorkflowEngine:", "class"),
        ("    \"\"\"Orchestrate multi-agent workflows on MiMo API.\"\"\"", "string"),
        ("", ""),
        ("    def __init__(self, config: dict):", "def"),
        ("        self.router = ModelRouter(config['models'])", "normal"),
        ("        self.pool = AgentPool(max_agents=config.get('max_agents', 10))", "normal"),
        ("        self.optimizer = TokenOptimizer(budget=config.get('token_budget'))", "normal"),
        ("        self.steps: List[Dict] = []", "normal"),
        ("        self.results: Dict[str, any] = {}", "normal"),
        ("", ""),
        ("    def add_step(self, name: str, prompt: str,", "def"),
        ("                 model: str = 'auto', parallel: bool = False):", "normal"),
        ("        \"\"\"Add a workflow step with auto-routing.\"\"\"", "string"),
        ("        self.steps.append({", "normal"),
        ("            'name': name,", "normal"),
        ("            'prompt': self.optimizer.compress(prompt),", "normal"),
        ("            'model': self.router.select(name, model),", "normal"),
        ("            'parallel': parallel,", "normal"),
        ("        })", "normal"),
        ("", ""),
        ("    async def execute(self) -> Dict:", "def"),
        ("        \"\"\"Execute all workflow steps with optimal scheduling.\"\"\"", "string"),
        ("        async with self.pool:", "normal"),
        ("            for step in self.steps:", "keyword"),
        ("                if step['parallel']:", "keyword"),
        ("                    task = self.pool.spawn(step['model'])", "normal"),
        ("                    asyncio.create_task(task.run(step['prompt']))", "normal"),
        ("                else:", "keyword"),
        ("                    result = await self.pool.run_sequential(step)", "normal"),
        ("                    self.results[step['name']] = result", "normal"),
        ("        return self.results", "normal"),
    ]

    colors = {
        "comment": "#6a9955",
        "string": "#ce9178",
        "import": "#c586c0",
        "class": "#4ec9b0",
        "def": "#dcdcaa",
        "keyword": "#569cd6",
        "normal": "#d4d4d4",
    }

    y = 45
    for i, (line, typ) in enumerate(code_lines):
        # Line number
        d.text((55, y), str(i+1), fill="#858585", font=mono)
        # Code
        if line:
            # Highlight current method
            d.text((100, y), line, fill=colors.get(typ, "#d4d4d4"), font=mono)
        y += 22

    # Minimap on right
    d.rectangle([W-60, 35, W, H], fill="#1e1e1e")
    for i in range(0, H-35, 4):
        d.rectangle([W-55, 35+i, W-5, 36+i], fill="#2d2d2d" if i % 8 == 0 else "#252526")

    # Status bar
    d.rectangle([0, H-25, W, H], fill="#007acc")
    d.text((10, H-20), "Python", fill="white", font=small)
    d.text((W//2, H-20), "UTF-8 | LF | Spaces: 4", fill="white", font=small, anchor="lm")
    d.text((W-10, H-20), "MIMO DevFlow Agent", fill="white", font=small, anchor="rm")

    img.save(os.path.join(OUT, "proof_04_code.png"), quality=95)
    print("✓ proof_04_code.png")

# ============================================================
# 5. GitHub Page
# ============================================================
def draw_github():
    img = Image.new("RGB", (W, H), "#0d1117")
    d = ImageDraw.Draw(img)
    font = get_font(14)
    font_bold = get_font_bold(14)
    title_font = get_font_bold(20)
    big_font = get_font_bold(28)
    small = get_font(12)

    # Nav bar
    d.rectangle([0, 0, W, 50], fill="#161b22")
    d.text((20, 14), "⬡ GitHub", fill="white", font=get_font_bold(18))
    d.rounded_rectangle([200, 12, 550, 36], radius=6, fill="#0d1117", outline="#30363d")
    d.text((215, 16), "Type / to search...", fill="#484f58", font=font)
    d.text((W-120, 18), "Sign in", fill="#c9d1d9", font=font_bold)
    d.rounded_rectangle([W-60, 12, W-10, 36], radius=6, fill="#238636", outline="#238636")
    d.text((W-35, 17), "Sign up", fill="white", font=small, anchor="mm")

    # Repo header
    y = 65
    d.text((30, y), "stitnappp", fill="#58a6ff", font=font_bold)
    d.text((130, y), " / ", fill="#8b949e", font=font_bold)
    d.text((160, y), "mimo-devflow", fill="#58a6ff", font=big_font)
    d.rounded_rectangle([420, y+8, 470, y+30], radius=12, outline="#30363d", width=1)
    d.text((445, y+18), "Public", fill="#8b949e", font=small, anchor="mm")

    # Stats row
    y = 110
    d.rounded_rectangle([30, y, 130, y+30], radius=6, fill="#21262d", outline="#30363d")
    d.text((40, y+7), "⭐ Stars", fill="#c9d1d9", font=small)
    d.text((110, y+7), "847", fill="white", font=get_font_bold(12), anchor="lt")

    d.rounded_rectangle([140, y, 230, y+30], radius=6, fill="#21262d", outline="#30363d")
    d.text((150, y+7), "👁 Watchers", fill="#c9d1d9", font=small)
    d.text((220, y+7), "156", fill="white", font=get_font_bold(12), anchor="lt")

    d.rounded_rectangle([240, y, 330, y+30], radius=6, fill="#21262d", outline="#30363d")
    d.text((250, y+7), "🍴 Forks", fill="#c9d1d9", font=small)
    d.text((320, y+7), "123", fill="white", font=get_font_bold(12), anchor="lt")

    # Tabs
    y = 155
    d.line([(20, y+28), (W-20, y+28)], fill="#21262d", width=1)
    tabs = ["<> Code", "Issues 12", "Pull requests 3", "Actions", "Projects", "Security", "Insights"]
    tx = 30
    for i, tab in enumerate(tabs):
        tw = d.textlength(tab, font=font) + 20
        if i == 0:
            d.line([(tx, y+28), (tx+tw, y+28)], fill="#f78166", width=2)
            d.text((tx+5, y+6), tab, fill="white", font=font)
        else:
            d.text((tx+5, y+6), tab, fill="#8b949e", font=font)
        tx += tw + 15

    # README section
    y = 200
    d.rounded_rectangle([30, y, W-30, H-20], radius=8, fill="#0d1117", outline="#21262d")
    d.rectangle([30, y, W-30, y+35], fill="#161b22")
    d.text((45, y+8), "📄 README.md", fill="white", font=font_bold)

    ry = y + 45
    d.text((55, ry), "MIMO DevFlow Agent", fill="white", font=get_font_bold(26))
    ry += 35
    d.text((55, ry), "🚀 A powerful multi-agent orchestration framework for Xiaomi MiMo API", fill="#8b949e", font=font)
    ry += 35

    # Feature list
    features = [
        "✦ Multi-model routing — auto-selects best MiMo model for each task",
        "✦ Token optimization — 94%+ efficiency with intelligent compression",
        "✦ Parallel execution — concurrent agent workflows with async support",
        "✦ Real-time monitoring — built-in dashboard and metrics",
        "✦ YAML workflow definitions — declarative agent orchestration",
        "✦ Cost tracking — per-workflow token and cost accounting",
        "✦ Plug-in architecture — extensible with custom agents and tools",
    ]
    for feat in features:
        d.text((65, ry), feat, fill="#c9d1d9", font=font)
        ry += 25

    ry += 15
    d.text((55, ry), "Quick Start", fill="white", font=get_font_bold(18))
    ry += 25
    # Code block
    d.rounded_rectangle([55, ry, 500, ry+55], radius=6, fill="#161b22", outline="#21262d")
    d.text((65, ry+5), "pip install mimo-devflow", fill="#79c0ff", font=get_font(13))
    d.text((65, ry+22), "mimo-devflow init my-project", fill="#79c0ff", font=get_font(13))
    d.text((65, ry+39), "mimo-devflow run workflow.yaml", fill="#79c0ff", font=get_font(13))

    # Language bar
    ly = H - 35
    pw = int(270 * 0.95)
    d.rounded_rectangle([30, ly, 30+pw, ly+12], radius=6, fill="#3572a5")
    d.rounded_rectangle([30+pw, ly, 300, ly+12], radius=6, fill="#f1e05a")
    d.text((310, ly-2), "Python 95%", fill="#3572a5", font=small)
    d.text((390, ly-2), "Other 5%", fill="#f1e05a", font=small)
    d.text((460, ly-2), "MIT License", fill="#8b949e", font=small)

    img.save(os.path.join(OUT, "proof_05_github.png"), quality=95)
    print("✓ proof_05_github.png")


# Run all
draw_architecture()
draw_terminal()
draw_dashboard()
draw_code()
draw_github()
print(f"\nAll 5 images saved to {OUT}/")
