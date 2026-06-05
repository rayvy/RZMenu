# 🌌 RZMenu (RZM)
### A powerful UI creation tool for 3DMigoto, and much more.

![Version](https://img.shields.io/badge/version-4.0-blueviolet?style=for-the-badge)
![Blender](https://img.shields.io/badge/Blender-4.1%2B-orange?style=for-the-badge&logo=blender)
![License](https://img.shields.io/badge/license-GPL--3.0-green?style=for-the-badge)
![Target](https://img.shields.io/badge/Games-GIMI/ZZMI/EFMI-success?style=for-the-badge)

---

## 🎮 Compatibility & Support

Currently, **EFMI-Tools** is natively supported (**Arknights: Endfield**). Support for **XXMI** games is coming soon:
- ✅ **Arknights: Endfield** (Primary Support)
- ✅ **Genshin Impact** (Tested)
- ✅ **Zenless Zone Zero** (Tested)
- ❓ **Honkai Star Rail** (Current status unknown/untested)
- ⏳ **Wuthering Waves (WWMI-Tools)** (Support planned)

---

## ⚠️ Beta Disclaimer

This tool is currently in a **near Alpha/Beta** stage. Please use it at your own risk.
- **Always make backups!** 
- Stability has been significantly improved in recent updates, but Blender may still crash occasionally due to the addon's complexity.

---

## 📦 Installation

1.  **Download:** Get the latest project ZIP file.
2.  **Install:** In Blender, go to `Edit > Preferences > Add-ons > Install...` and select the ZIP.
3.  **Dependencies:** Once enabled, look for the dependency installation panel at the bottom of the addon preferences.
    - **PySide6:** This is **MANDATORY**. The RZMenu graphical interface will not work without it.
    - **Other Packages:** Optional, but highly recommended to install all of them for the full experience.

---

## 📖 Documentation & Guides

For a detailed technical overview and element reference, please check the local documentation:
👉 **[Technical Documentation (DOCUMENTATION.md)](./DOCUMENTATION.md)**

### 💎 Zero-Dependency Export
When you export a mod, **end-users do not need to download any additional libraries**. 
- The rendering core is embedded directly inside the `.ini` file.
- The system automatically includes the necessary `modules` and `resources` folders in the mod's root directory.

### ⚙️ Technical Note: Shapekey Logic
The tool uses a non-standard shapekey export logic which may be unpredictable in some scenarios. 
- **Successful Tests:** Genshin Impact, Zenless Zone Zero, and Arknights: Endfield.
- **Why Public Beta?** I haven't accounted for every possible situation yet. This test period is crucial for gathering data to improve the instrumentation.

### Auto-Pilot Feature
I have implemented several safety mechanisms so that **RZ Construct** can automatically set up the project for you. However, since the tool is still unstable and under active development, I cannot guarantee it will handle everything perfectly 100% of the time.

---

## Special Thanks

### оп оп гоп стоп:
- **[Zlevir](https://www.patreon.com/cw/zlevir)** - RZMenu grew out of experiments on his mod menu. The `Z` in `RZMenu` is in his honor <3

### 🛠️ Modding Tool Developers
- **[leotorrez](https://ko-fi.com/leotorrez)** ([Profile](https://github.com/leotorrez) / [XXMITools](https://github.com/leotorrez/XXMITools)) and all XXMI contributors - RZMenu leans on the XXMI ecosystem and is not a fully standalone exporter **+ advised with code idea stuff.**
- - **[SinsOfSeven](https://ko-fi.com/sinsofseven)** ([Profile](https://github.com/SinsOfSeven)) - for MathLib (copy pasted) / TexFX (used on drawcall object modification, not the lib itself)  **+ advised with code idea stuff.**
- **[SpectrumQT](https://www.patreon.com/SpectrumQT)** ([Profile](https://github.com/SpectrumQT) / [EFMI-Tools](https://github.com/SpectrumQT/EFMI-Tools)) - for the EFMI tooling foundation RZMenu integrates with.
- **[SilentNightSound](https://ko-fi.com/silentnightsound)** ([Profile](https://github.com/SilentNightSound)) - Сахароза.
- **[caverabbit](https://www.patreon.com/Caverabbit)** - RabbitFX (used on drawcall object modification, not the lib itself).
- **[Greisane](https://github.com/greisane)** ([Gret](https://github.com/greisane/gret)) - Shape Key Apply functionality copy pasted and slightly adapted from Gret (see [operators/gret_shape_key_utils.py](operators/gret_shape_key_utils.py)).
- **[Grim-es](https://github.com/Grim-es)** ([Material Combiner](https://github.com/Grim-es/material-combiner-addon)) - As of 05.06.2026, I haven't yonked anything from this project yet. However, there is a statistically significant chance that I will either get inspired by it or shamelessly yoink something in the future. I haven't decided which one it will be yet. Thanks in advance. :*
- **[Gustav0](https://ko-fi.com/gustav0_)** ([Profile](https://github.com/Seris0)) - currently I didn't yonk anything, but same as Grim-es Material Combiner, I'm planning to inspire/yonk part of code of XXMIsetup addon + XXMI dev.

### 🌐 Translations
- **HaoWooooo [AGMG]** ([ChouDan6](https://github.com/ChouDan6/)) - for Simplified Chinese translation fixes and live proofreading.

### 🧪 Alpha Testers
- **[Xsolaris](https://gamebanana.com/members/3591485)** - the very first alpha tester.
- **[QVANT-D](https://www.patreon.com/cw/QVANT_D/home)** - another alpha tester.
- **АнонимныйКот** - another alpha tester, listed anonymously by request.
- **HaoWooooo [AGMG]** ([ChouDan6](https://github.com/ChouDan6/)) - Also tester.
- **[RAZUMNO](https://gamebanana.com/members/2868653)** - tester + proposed the idea of element helpers, which was successfully integrated ~~и ебёт меня постоянно с тем чтобы я добавил нормальные якорные системы в GUI)~~

### 💡 Other Contributions
- **[DiXiaoO](https://github.com/DiXiaoO)** - suggested the buffer idea.
- **[Satan1c](https://github.com/Satan1c)** - for advising on various optimization strategies for the project.


---

### Nurarihyuon:
Also try [MenuCreator](https://github.com/NurarihyonMaou/MenuCreator) (+ i got referenced buffer ini work stuff on his InGameMenu mod manager)

Stay tuned and happy modding!
