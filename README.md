# 🌌 RZMenu (RZM)
### A powerful UI creation tool for 3DMigoto, and much more.

![Version](https://img.shields.io/badge/version-4.0-blueviolet?style=for-the-badge)
![Blender](https://img.shields.io/badge/Blender-4.1%2B-orange?style=for-the-badge&logo=blender)
![License](https://img.shields.io/badge/license-MIT-green?style=for-the-badge)
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

## 📖 What's Next?

There are currently **no guides**. You'll have to suffer on your own. Good luck!

...Just kidding. Here is a link to a **Quick Start Guide (Temporary)**:
👉 [Google Docs Guide](https://docs.google.com/document/d/19RNpMQVn_tSZ7FjX7ggFLNdNhG4fa-SVRfNrYVnXrkQ/edit?usp=sharing)

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

Stay tuned and happy modding!
