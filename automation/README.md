# MIMO 100T Form Automation

## Overview
Automates the Xiaomi MiMo 100T Token Grant application form at `100t.xiaomimimo.com`.

## Features
- 📧 **Temp Email**: Auto-generates disposable emails via MORVO TempMail API
- 🔐 **Captcha Solving**: Handles reCAPTCHA via sctg.xyz / nocaptcha.io
- 🖼️ **Proof Upload**: Auto-uploads 5 proof images
- 🤖 **Full Automation**: Fills all form fields and submits
- 📦 **Batch Mode**: Submit multiple applications with different emails

## Setup

```bash
# Install dependencies
pip install playwright httpx
playwright install chromium

# Set API keys (optional, defaults in script)
export TEMPMAIL_API_KEY="your_key"
export CAPTCHA_API_KEY="your_key"
export NOCAPTCHA_API_KEY="your_key"  # backup
```

## Usage

### Single Application
```bash
python automation/fill_form.py
```

### Batch Applications
```bash
python automation/fill_form.py --batch 5
```

### Dry Run (fill but don't submit)
```bash
python automation/fill_form.py --dry-run
```

### With Specific Email
```bash
python automation/fill_form.py --email "your@email.com"
```

## Form Fields Mapping
1. **Email** → Auto-generated temp email (@morvo.me)
2. **AI Tools** → Claude Code, Hermes Agent, Codex
3. **Model Series** → MiMo 系列
4. **Project Description** → MIMO DevFlow Agent description (1200 chars)
5. **Proof Images** → 5 auto-generated screenshots
6. **GitHub Link** → https://github.com/stitnappp/mimo-devflow

## API Keys
- **MORVO TempMail**: `whsec_95b98cc8f3bdd6f7167e2921a9047fde50952e678f22b236`
- **sctg.xyz Captcha**: `g4eEqP3srQyW92pSLdMTPTDVXAZCMh2s`
- **nocaptcha.io** (backup): Set via `NOCAPTCHA_API_KEY` env var

## Files
```
automation/
├── fill_form.py      # Main automation script
├── README.md         # This file
└── config.py         # Configuration (optional)
proof_images/
├── proof_01_architecture.png
├── proof_02_terminal.png
├── proof_03_dashboard.png
├── proof_04_code.png
└── proof_05_github.png
```
