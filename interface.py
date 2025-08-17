import os
import sys
import json
import re
from pathlib import Path
from datetime import datetime
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.fonts=false;qt.qpa.*=false")

from typing import Callable, List

from PySide6.QtCore import (
    Qt,
    QPropertyAnimation,
    QEasingCurve,
    QProcess,
    Slot,
    QObject,
)
from PySide6.QtGui import QIcon, QKeySequence, QShortcut, QColor, QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTabWidget,
    QPlainTextEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QFileDialog,
    QStyle,
    QGraphicsDropShadowEffect,
)

GLOBAL_CONSOLE: QTextEdit | None = None

PROJECT_ROOT = Path(__file__).resolve().parent
SETTINGS_FILE = PROJECT_ROOT / "settings.json"
STYLE_FILE = PROJECT_ROOT / "style.qss"

def load_settings() -> dict:
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

def save_settings(d: dict) -> None:
    try:
        SETTINGS_FILE.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print_safe(f"[settings] Erreur sauvegarde: {e}")

def ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

ALLOWED_SUFFIXES = {".py", ".qss", ".ui", ".json", ".md", ".txt", ".yaml", ".yml"}
EXCLUDE_DIRS = {".git", "__pycache__", "venv", "env", ".idea", ".vscode", "build", "dist", ".mypy_cache", ".pytest_cache"}

def generate_code_txt(output_path: Path) -> int:
    count = 0
    print_safe(f"[{ts()}] Génération de {output_path.name}…")
    with output_path.open("w", encoding="utf-8", errors="replace") as out:
        out.write(f"# Code snapshot — {ts()} — root: {PROJECT_ROOT}\n")
        for p in sorted(PROJECT_ROOT.rglob("*")):
            try:
                if any(part in EXCLUDE_DIRS for part in p.parts):
                    continue
                if not p.is_file() or p.name == output_path.name:
                    continue
                if p.suffix.lower() not in ALLOWED_SUFFIXES:
                    continue
                text = p.read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                print_safe(f"[Code.txt] Skip {p}: {e}")
                continue
            rel = p.relative_to(PROJECT_ROOT)
            out.write(f"\n\n# ===== FILE: {rel} =====\n")
            out.write(f"# SIZE: {p.stat().st_size} bytes\n# BEGIN\n")
            out.write(text)
            if not text.endswith("\n"):
                out.write("\n")
            out.write(f"# END FILE: {rel}\n")
            count += 1
    print_safe(f"[{ts()}] {output_path.name} OK — {count} fichiers.")
    return count


def print_safe(msg: str) -> None:
    print(msg)
    if GLOBAL_CONSOLE is not None:
        GLOBAL_CONSOLE.append(msg)


def apply_qss(qss: str, include_sidebar: bool, has_shadow: bool) -> None:
    app = QApplication.instance()
    base = app.styleSheet()
    app.setStyleSheet(base + "\n" + qss)
    for w in QApplication.allWidgets():
        if isinstance(w, QPushButton):
            if not include_sidebar and w.objectName() == "sidebar-item":
                w.setGraphicsEffect(None)
                continue
            if has_shadow:
                eff = QGraphicsDropShadowEffect()
                eff.setBlurRadius(12)
                eff.setOffset(0, 2)
                eff.setColor(QColor("#00000080"))
                w.setGraphicsEffect(eff)
            else:
                w.setGraphicsEffect(None)


def get_icon(name: str) -> QIcon:
    style = QApplication.style()
    mapping = {
        "dashboard": QStyle.SP_ComputerIcon,
        "journal": QStyle.SP_FileIcon,
        "grand_livre": QStyle.SP_DirIcon,
        "bilan": QStyle.SP_DriveHDIcon,
        "resultat": QStyle.SP_DialogApplyButton,
        "comptes": QStyle.SP_DesktopIcon,
        "revision": QStyle.SP_BrowserReload,
        "parametres": QStyle.SP_FileDialogDetailedView,
        "scrap": QStyle.SP_ArrowRight,
        "profil_scraping": QStyle.SP_FileDialogInfoView,
        "galerie": QStyle.SP_DirHomeIcon,
    }
    return style.standardIcon(mapping.get(name, QStyle.SP_FileIcon))


class ThemeManager:
    def __init__(self, app: QApplication) -> None:
        self.app = app
        self.current = "dark"

    def apply(self, theme: str) -> None:
        self.current = theme
        if theme == "light":
            self.app.setStyleSheet(
                "QWidget{background:#ffffff;color:#111;}"
                "QPushButton{background:#f2f2f2;color:#111;border:1px solid #ddd;}"
                "QPushButton:hover{background:#e9e9e9;}"
                "QLineEdit,QTextEdit,QComboBox,QListWidget{background:#fff;color:#111;border:1px solid #ccc;}"
                "QTabBar::tab{background:#f6f6f6;padding:6px;border:1px solid #ddd;}"
                "QTabBar::tab:selected{background:#eaeaea;}"
            )
        else:
            self.app.setStyleSheet(
                "QWidget{background:#222;color:#ddd;}"
                "QPushButton{background:#444;color:#fff;border:1px solid #333;}"
                "QPushButton:hover{background:#555;}"
                "QLineEdit,QTextEdit,QComboBox,QListWidget{background:#2b2b2b;color:#eee;border:1px solid #3a3a3a;}"
                "QTabBar::tab{background:#333;padding:6px;border:1px solid #3a3a3a;}"
                "QTabBar::tab:selected{background:#3b3b3b;}"
            )


class AnimatedStack(QStackedWidget):
    pass


class SidebarButton(QPushButton):
    def __init__(self, text: str, icon: QIcon | None = None) -> None:
        super().__init__(text)
        if icon:
            self.setIcon(icon)
        self.setCheckable(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet(
            "QPushButton{padding:8px;text-align:left;border:none;}"
            "QPushButton:hover{background:#d0d0d0;}"
            "QPushButton:checked{background:#c0c0c0;font-weight:bold;}"
        )


class CollapsibleSection(QWidget):
    def __init__(self, title: str, *, hide_title_when_collapsed: bool = False) -> None:
        super().__init__()
        self.original_title = title
        self.hide_title_when_collapsed = hide_title_when_collapsed
        self.toggle_button = QPushButton(title)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setStyleSheet(
            "QPushButton{background:#444;color:white;padding:8px;text-align:left;}"
            "QPushButton:checked{background:#666;}"
        )
        self.content_area = QWidget()
        self.content_area.setMaximumHeight(0)
        self.toggle_animation = QPropertyAnimation(self.content_area, b"maximumHeight")
        self.toggle_animation.setDuration(300)
        self.toggle_animation.setEasingCurve(QEasingCurve.InOutCubic)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.toggle_button)
        main_layout.addWidget(self.content_area)
        self.inner_layout = QVBoxLayout(self.content_area)
        self.inner_layout.setContentsMargins(0, 0, 0, 0)
        self.toggle_button.clicked.connect(self.toggle)
        if hide_title_when_collapsed:
            self.toggle_button.setText("")

    def toggle(self) -> None:
        checked = self.toggle_button.isChecked()
        end_val = self.inner_layout.sizeHint().height() if checked else 0
        self.toggle_animation.stop()
        self.toggle_animation.setStartValue(self.content_area.maximumHeight())
        self.toggle_animation.setEndValue(end_val)
        self.toggle_animation.start()
        if self.hide_title_when_collapsed:
            self.toggle_button.setText(self.original_title if checked else "")

    def collapse(self) -> None:
        if self.toggle_button.isChecked():
            self.toggle_button.setChecked(False)
            self.toggle()

    def expand(self) -> None:
        if not self.toggle_button.isChecked():
            self.toggle_button.setChecked(True)
            self.toggle()

    def add_widget(self, w: QWidget) -> None:
        self.inner_layout.addWidget(w)


class SimpleLabelPage(QWidget):
    def __init__(self, text: str) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addStretch()
        layout.addWidget(QLabel(text, alignment=Qt.AlignCenter))
        layout.addStretch()


class DashboardWidget(SimpleLabelPage):
    def __init__(self) -> None:
        super().__init__("Tableau de bord")


class AchatWidget(SimpleLabelPage):
    def __init__(self) -> None:
        super().__init__("Achat (stub)")


class VenteWidget(SimpleLabelPage):
    def __init__(self) -> None:
        super().__init__("Vente (stub)")


class AccountWidget(SimpleLabelPage):
    def __init__(self) -> None:
        super().__init__("Comptes (stub)")


class RevisionTab(SimpleLabelPage):
    def __init__(self) -> None:
        super().__init__("Révision (stub)")


class SupplierTab(SimpleLabelPage):
    def __init__(self) -> None:
        super().__init__("Fournisseurs (stub)")


class GalleryWidget(SimpleLabelPage):
    def __init__(self) -> None:
        super().__init__("Galerie (stub)")





class BetaWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)

        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("URL:"))
        self.url_edit = QLineEdit()
        url_layout.addWidget(self.url_edit)
        self.launch_btn = QPushButton("Lancer")
        url_layout.addWidget(self.launch_btn)
        layout.addLayout(url_layout)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        layout.addWidget(self.console)

        self.progress_label = QLabel("En attente…")
        layout.addWidget(self.progress_label)

        self.process: QProcess | None = None
        self.launch_btn.clicked.connect(self.start_process)

    @Slot()
    def start_process(self) -> None:
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "Beta", "Veuillez entrer une URL.")
            return
        self.console.clear()
        self.progress_label.setText("Démarrage…")
        self.launch_btn.setEnabled(False)

        self.process = QProcess(self)
        self.process.setProgram(sys.executable)
        args = [
            "-m",
            "scraper.images_csv",
            "--url",
            url,
            "--css",
            ".product-gallery__media-list img",
            "--images-mode",
            "wp-prefix",
            "--wp-prefix-url",
            "https://www.planetebob.fr/wp-content/uploads",
        ]
        self.process.setArguments(args)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._handle_output)
        self.process.finished.connect(self._process_finished)
        self.process.start()

    @Slot()
    def _handle_output(self) -> None:
        if not self.process:
            return
        data = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
        if not data:
            return
        for line in data.splitlines():
            self.console.append(line)
            lower = line.lower()
            if "image(s) détectée" in lower or "csv upsert" in lower or "terminé" in lower:
                self.progress_label.setText(line)

    @Slot(int, QProcess.ExitStatus)
    def _process_finished(self, code: int, status: QProcess.ExitStatus) -> None:
        msg = "✅ Terminé" if code == 0 else f"❌ Erreur (code {code})"
        self.console.append(msg)
        self.progress_label.setText(msg)
        self.launch_btn.setEnabled(True)

class ScrapWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        for name in [
            "Collections",
            "Serveur Flask",
            "Historique",
            "Fiche Produit WooCommerce",
            "Stockage",
        ]:
            self.tabs.addTab(SimpleLabelPage(name), name)


class MaintenanceTab(QWidget):
    def __init__(self, theme_manager: ThemeManager) -> None:
        super().__init__()
        self.theme_manager = theme_manager

        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        self.theme_switch = QCheckBox("Mode sombre")
        update_btn = QPushButton("Mettre à jour l'app")
        restart_btn = QPushButton("Redémarrer")
        txt_btn = QPushButton("Mettre à jour le txt")
        top.addWidget(self.theme_switch)
        top.addStretch()
        top.addWidget(update_btn)
        top.addWidget(restart_btn)
        top.addWidget(txt_btn)
        layout.addLayout(top)

        self.console = QTextEdit(readOnly=True)
        layout.addWidget(self.console)
        global GLOBAL_CONSOLE
        GLOBAL_CONSOLE = self.console

        s = load_settings()
        current = s.get("theme", self.theme_manager.current)
        self.theme_switch.setChecked(current == "dark")
        self.apply_theme_from_switch(init=True)

        self.theme_switch.toggled.connect(lambda _: self.apply_theme_from_switch())
        update_btn.clicked.connect(self.run_git_pull)
        restart_btn.clicked.connect(self.restart_app)
        txt_btn.clicked.connect(self.update_code_txt)

        self.git_proc = QProcess(self)
        self.git_proc.setWorkingDirectory(str(PROJECT_ROOT))
        self.git_proc.readyReadStandardOutput.connect(self._pipe_stdout)
        self.git_proc.readyReadStandardError.connect(self._pipe_stderr)
        self.git_proc.finished.connect(self._git_finished)

    def apply_theme_from_switch(self, init: bool = False) -> None:
        theme = "dark" if self.theme_switch.isChecked() else "light"
        self.theme_manager.apply(theme)
        s = load_settings()
        s["theme"] = theme
        save_settings(s)
        if not init:
            print_safe(f"[{ts()}] Thème appliqué: {theme}")

    def run_git_pull(self) -> None:
        if self.git_proc.state() != QProcess.NotRunning:
            print_safe(f"[{ts()}] git déjà en cours…")
            return
        print_safe(f"[{ts()}] git pull origin main …")
        self.git_proc.setProgram("git")
        self.git_proc.setArguments(["pull", "origin", "main"])
        self.git_proc.start()

    @Slot()
    def _pipe_stdout(self) -> None:
        data = self.git_proc.readAllStandardOutput().data().decode(errors="replace")
        if data:
            for line in data.splitlines():
                print_safe(line)

    @Slot()
    def _pipe_stderr(self) -> None:
        data = self.git_proc.readAllStandardError().data().decode(errors="replace")
        if data:
            for line in data.splitlines():
                print_safe("[git] " + line)

    @Slot(int, QProcess.ExitStatus)
    def _git_finished(self, code: int, status) -> None:
        print_safe(f"[{ts()}] git terminé avec code={code}")

    def restart_app(self) -> None:
        print_safe(f"[{ts()}] Redémarrage demandé…")
        QProcess.startDetached(sys.executable, sys.argv)
        QApplication.instance().quit()

    def update_code_txt(self) -> None:
        out = PROJECT_ROOT / "Code.txt"
        try:
            n = generate_code_txt(out)
            print_safe(f"[{ts()}] Fini: {n} fichiers dans {out}")
        except Exception as e:
            print_safe(f"[{ts()}] Erreur génération Code.txt: {e}")


class StyleTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        main = QHBoxLayout(self)

        self.editors = QTabWidget()
        self.html_edit = QPlainTextEdit()
        self.css_edit = QPlainTextEdit()
        self.js_edit = QPlainTextEdit()
        mono = QFont("monospace")
        self.html_edit.setFont(mono)
        self.css_edit.setFont(mono)
        self.js_edit.setFont(mono)
        self.editors.addTab(self.html_edit, "HTML")
        self.editors.addTab(self.css_edit, "CSS")
        self.editors.addTab(self.js_edit, "JS")
        main.addWidget(self.editors, 3)

        right = QVBoxLayout()
        self.preview_buttons: List[QPushButton] = []
        for text, var in [
            ("Primary", "primary"),
            ("Secondary", "secondary"),
            ("Danger", "danger"),
            ("Ghost", "ghost"),
        ]:
            b = QPushButton(text)
            b.setProperty("variant", var)
            self.preview_buttons.append(b)
            right.addWidget(b)

        self.apply_cb = QCheckBox("Appliquer à toute l'app")
        self.apply_cb.setChecked(True)
        self.sidebar_cb = QCheckBox("Inclure la sidebar")
        right.addWidget(self.apply_cb)
        right.addWidget(self.sidebar_cb)

        btns = QHBoxLayout()
        preview_btn = QPushButton("Aperçu Qt")
        apply_btn = QPushButton("Appliquer")
        save_btn = QPushButton("Enregistrer")
        btns.addWidget(preview_btn)
        btns.addWidget(apply_btn)
        btns.addWidget(save_btn)
        right.addLayout(btns)
        right.addStretch()
        main.addLayout(right, 2)

        s = load_settings()
        self.html_edit.setPlainText(s.get("style_html", ""))
        self.css_edit.setPlainText(s.get("style_css", ""))
        self.js_edit.setPlainText(s.get("style_js", ""))
        self.sidebar_cb.setChecked(s.get("style_include_sidebar", False))
        self.current_qss = ""
        if STYLE_FILE.exists():
            self.current_qss = STYLE_FILE.read_text(encoding="utf-8")

        self._has_box_shadow = "box-shadow" in self.css_edit.toPlainText()

        preview_btn.clicked.connect(self.preview_qt)
        apply_btn.clicked.connect(self.apply_clicked)
        save_btn.clicked.connect(self.save_style)

    def css_to_qss(self, css: str, include_sidebar: bool) -> str:
        """
        Convertit un sous-ensemble de CSS en QSS ciblant QPushButton.
        Règles :
          - '.custom-btn', '.btn', '.button', 'button', 'qpushbutton' => base: QPushButton
          - alias variantes : .primary/.secondary/.danger/.ghost, .btn-1..4
          - :active => :pressed ; :disabled conservé ; :hover conservé
          - propriétés supportées : background/background-color, color,
            border/border-color/border-width/border-style, border-radius,
            padding, font-size, font-weight
          - autres propriétés : ignorées (ex: transition, transform, filter)
        """
        import re

        self._has_box_shadow = "box-shadow" in css

        # --- helpers ---
        def parse_decls(block: str) -> dict[str, str]:
            props: dict[str, str] = {}
            for raw in block.split(";"):
                if ":" not in raw:
                    continue
                k, v = raw.split(":", 1)
                k = k.strip().lower()
                v = v.strip()
                if not k or not v:
                    continue
                # normalisation basique
                if k in ("background", "background-color"):
                    props["background"] = v
                elif k == "color":
                    props["color"] = v
                elif k == "border":
                    props["border"] = v
                elif k == "border-color":
                    props["border-color"] = v
                elif k == "border-width":
                    props["border-width"] = v
                elif k == "border-style":
                    props["border-style"] = v
                elif k == "border-radius":
                    props["border-radius"] = v
                elif k == "padding":
                    props["padding"] = v
                elif k == "font-size":
                    props["font-size"] = v
                elif k == "font-weight":
                    props["font-weight"] = v
                elif k == "box-shadow":
                    # Indice pour ajouter un QGraphicsDropShadowEffect ailleurs si besoin
                    props["box-shadow"] = v
                # sinon: ignoré
            return props

        def join_decls(d: dict[str, str]) -> str:
            # ordre stable pour un QSS propre
            order = [
                "background", "color",
                "border", "border-color", "border-width", "border-style",
                "border-radius", "padding",
                "font-size", "font-weight",
            ]
            seq = []
            for k in order:
                if k in d:
                    seq.append(f"{k}:{d[k]};")
            # on n'écrit pas box-shadow en QSS
            return " ".join(seq)

        # dictionnaires d'accumulation
        base = {"": {}, "hover": {}, "pressed": {}, "disabled": {}}
        variants: dict[str, dict[str, dict[str, str]]] = {}

        # alias de variantes usuelles
        alias_variants = {
            ".primary": "primary",
            ".secondary": "secondary",
            ".danger": "danger",
            ".ghost": "ghost",
            ".btn-1": "primary",
            ".btn-2": "secondary",
            ".btn-3": "danger",
            ".btn-4": "ghost",
        }

        # découpe des règles CSS
        for sel, decl in re.findall(r"([^{]+)\{([^}]*)\}", css, flags=re.S):
            props = parse_decls(decl)
            if not props:
                continue

            # sel peut contenir plusieurs parties séparées par ","
            for sel_part in sel.split(","):
                sel_part = sel_part.strip()
                if not sel_part:
                    continue

                # extraire pseudo-état
                pseudo = ""
                if ":" in sel_part:
                    _base, _pseudo = sel_part.split(":", 1)
                    sel_part = _base.strip()
                    pseudo = _pseudo.strip().lower()

                # mapping pseudo-états
                state = ""
                if pseudo == "hover":
                    state = "hover"
                elif pseudo in ("active", "pressed"):
                    state = "pressed"
                elif pseudo == "disabled":
                    state = "disabled"

                # 1) cas "base" -> QPushButton
                if sel_part.lower() in {"button", "qpushbutton"} or sel_part in {".custom-btn", ".btn", ".button"}:
                    target = base
                    target[state].update({k: v for k, v in props.items() if k != "box-shadow"})
                    continue

                # 2) alias de variantes connues
                if sel_part in alias_variants:
                    var = alias_variants[sel_part]
                    target = variants.setdefault(var, {"": {}, "hover": {}, "pressed": {}, "disabled": {}})
                    target[state].update({k: v for k, v in props.items() if k != "box-shadow"})
                    continue

                # 3) classes inconnues => on les considère comme variantes (facultatif)
                if sel_part.startswith("."):
                    var = sel_part[1:]
                    target = variants.setdefault(var, {"": {}, "hover": {}, "pressed": {}, "disabled": {}})
                    target[state].update({k: v for k, v in props.items() if k != "box-shadow"})
                    continue

                # autres sélecteurs: ignorés

        # construction du QSS
        parts: list[str] = []

        # base
        for st_key, decls in base.items():
            if decls:
                pseudo = f":{st_key}" if st_key else ""
                parts.append(f"QPushButton{pseudo}{{{join_decls(decls)}}}")

        # variantes -> propriété dynamique [variant="..."]
        for var, states in variants.items():
            for st_key, decls in states.items():
                if not decls:
                    continue
                pseudo = f":{st_key}" if st_key else ""
                parts.append(f'QPushButton[variant="{var}"]{pseudo}' + "{" + join_decls(decls) + "}")

        # exclusion sidebar si demandé
        if not include_sidebar:
            parts.append(
                "QPushButton#sidebar-item{background:transparent;color:inherit;border:none;padding:8px;}"
                "QPushButton#sidebar-item:hover{background:rgba(0,0,0,0.08);}" \
                "QPushButton#sidebar-item:checked{background:rgba(0,0,0,0.12);font-weight:bold;}"
            )

        return "\n".join(parts)

    def apply_qss_to_app(self, qss: str, include_sidebar: bool) -> None:
        apply_qss(qss, include_sidebar, self._has_box_shadow)

    def preview_qt(self) -> None:
        qss = self.css_to_qss(self.css_edit.toPlainText(), self.sidebar_cb.isChecked())
        for b in self.preview_buttons:
            b.setStyleSheet(qss)
        print_safe(f"[{ts()}] Aperçu Qt mis à jour")

    def apply_clicked(self) -> None:
        css = self.css_edit.toPlainText()
        include = self.sidebar_cb.isChecked()
        qss = self.css_to_qss(css, include)
        if self.apply_cb.isChecked():
            self.apply_qss_to_app(qss, include)
        self.preview_qt()
        self.current_qss = qss
        print_safe(f"[{ts()}] Style appliqué")

    def save_style(self) -> None:
        include = self.sidebar_cb.isChecked()
        css = self.css_edit.toPlainText()
        qss = self.css_to_qss(css, include)
        STYLE_FILE.write_text(qss, encoding="utf-8")
        s = load_settings()
        s["style_html"] = self.html_edit.toPlainText()
        s["style_css"] = css
        s["style_js"] = self.js_edit.toPlainText()
        s["style_include_sidebar"] = include
        save_settings(s)
        print_safe(f"[{ts()}] Style sauvegardé")


class SettingsPage(QWidget):
    def __init__(self, theme_manager: ThemeManager) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)
        self.maintenance_tab = MaintenanceTab(theme_manager)
        self.style_tab = StyleTab()
        tabs.addTab(self.maintenance_tab, "Maintenance")
        tabs.addTab(self.style_tab, "Style")


class MainWindow(QMainWindow):
    def __init__(self, theme: ThemeManager) -> None:
        super().__init__()
        self.theme = theme
        s = load_settings()
        self.theme.apply(s.get("theme", "dark"))
        if STYLE_FILE.exists():
            try:
                qss = STYLE_FILE.read_text(encoding="utf-8")
                include_sidebar = s.get("style_include_sidebar", False)
                has_shadow = "box-shadow" in s.get("style_css", "")
                apply_qss(qss, include_sidebar, has_shadow)
            except Exception as e:
                print_safe(f"[{ts()}] Erreur application style.qss: {e}")
        self.setWindowTitle("COMPTA - Interface de gestion comptable")
        self.setMinimumSize(1200, 700)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)

        sidebar_container = QWidget()
        sidebar_layout = QVBoxLayout(sidebar_container)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll_content = QWidget()
        nav_layout = QVBoxLayout(scroll_content)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(0)
        scroll.setWidget(scroll_content)
        sidebar_layout.addWidget(scroll)

        self.button_group: list[SidebarButton] = []
        self.compta_buttons: dict[str, SidebarButton] = {}

        self.compta_section = CollapsibleSection("📁 Comptabilité")
        compta_items = [
            ("Tableau de bord", "dashboard", self.show_dashboard_page),
            ("Journal", "journal", lambda b: self.display_content("Comptabilité : Journal", b)),
            ("Grand Livre", "grand_livre", lambda b: self.display_content("Comptabilité : Grand Livre", b)),
            ("Bilan", "bilan", lambda b: self.display_content("Comptabilité : Bilan", b)),
            ("Résultat", "resultat", lambda b: self.display_content("Comptabilité : Résultat", b)),
            ("Comptes", "comptes", self.show_accounts_page),
            ("Révision", "revision", self.show_revision_page),
            ("Paramètres", "parametres", self.show_compta_params),
        ]
        for name, icon_name, handler in compta_items:
            btn = SidebarButton(name, get_icon(icon_name))
            btn.setObjectName("sidebar-item")
            self.compta_buttons[name] = btn
            btn.clicked.connect(lambda _, b=btn, h=handler: h(b))
            self.compta_section.add_widget(btn)
            self.button_group.append(btn)
        nav_layout.addWidget(self.compta_section)

        self.scrap_section = CollapsibleSection("🛠️ Scraping")
        self.scrap_btn = SidebarButton("Scrap", get_icon("scrap"))
        self.scrap_btn.setObjectName("sidebar-item")
        self.scrap_btn.clicked.connect(lambda _, b=self.scrap_btn: self.show_scrap_page(b))
        self.scrap_section.add_widget(self.scrap_btn)
        self.button_group.append(self.scrap_btn)

        self.gallery_btn = SidebarButton("Galerie", get_icon("galerie"))
        self.gallery_btn.setObjectName("sidebar-item")
        self.gallery_btn.clicked.connect(lambda _, b=self.gallery_btn: self.show_gallery_tab())
        self.scrap_section.add_widget(self.gallery_btn)
        self.button_group.append(self.gallery_btn)

        self.beta_btn = SidebarButton("Beta", get_icon("scrap"))
        self.beta_btn.setObjectName("sidebar-item")
        self.beta_btn.clicked.connect(lambda _, b=self.beta_btn: self.show_beta_page(b))
        self.scrap_section.add_widget(self.beta_btn)
        self.button_group.append(self.beta_btn)

        nav_layout.addWidget(self.scrap_section)

        self.compta_section.toggle_button.clicked.connect(lambda: self._collapse_other(self.compta_section))
        self.scrap_section.toggle_button.clicked.connect(lambda: self._collapse_other(self.scrap_section))
        nav_layout.addStretch()

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("margin:6px 0;")
        sidebar_layout.addWidget(line)

        self.settings_btn = SidebarButton("Paramètres", get_icon("parametres"))
        self.settings_btn.setObjectName("sidebar-item")
        self.settings_btn.clicked.connect(lambda _, b=self.settings_btn: self.show_settings(b))
        self.button_group.append(self.settings_btn)
        sidebar_layout.addWidget(self.settings_btn)

        self.stack = AnimatedStack()
        self.stack.addWidget(SimpleLabelPage("Bienvenue sur COMPTA"))
        main_layout.addWidget(sidebar_container, 1)
        main_layout.addWidget(self.stack, 4)

        self.scrap_page = ScrapWidget()
        self.gallery_page = GalleryWidget()
        self.beta_page = BetaWidget()
        self.dashboard_page = DashboardWidget()
        self.accounts_page = AccountWidget()
        self.revision_page = RevisionTab()
        self.compta_params_page = SimpleLabelPage("Paramètres compta (stub)")
        self.settings_page = SettingsPage(self.theme)

        for w in [
            self.scrap_page,
            self.gallery_page,
            self.beta_page,
            self.dashboard_page,
            self.accounts_page,
            self.revision_page,
            self.compta_params_page,
            self.settings_page,
        ]:
            self.stack.addWidget(w)

        self._install_shortcuts()

    def clear_selection(self) -> None:
        for btn in self.button_group:
            btn.setChecked(False)

    def _collapse_other(self, active: CollapsibleSection) -> None:
        if active.toggle_button.isChecked():
            other = self.scrap_section if active is self.compta_section else self.compta_section
            other.collapse()

    def _install_shortcuts(self) -> None:
        try:
            def add(key: str, fn: Callable[[], None]) -> None:
                sc = QShortcut(QKeySequence(key), self)
                sc.activated.connect(fn)

            add("Ctrl+1", lambda: self.show_scrap_page(self.scrap_btn))
            add("Ctrl+3", self.show_gallery_tab)
            add("Ctrl+5", lambda: self.show_settings(self.settings_btn))
        except Exception as e:
            print(f"Shortcuts disabled: {e}")

    def display_content(self, text: str, button: SidebarButton) -> None:
        self.clear_selection()
        button.setChecked(True)
        page = SimpleLabelPage(text)
        self.stack.addWidget(page)
        self.stack.setCurrentWidget(page)

    def show_scrap_page(self, button: SidebarButton, tab_index: int = 0) -> None:
        self.clear_selection()
        button.setChecked(True)
        self.scrap_page.tabs.setCurrentIndex(tab_index)
        self.stack.setCurrentWidget(self.scrap_page)

    def show_gallery_tab(self) -> None:
        self.clear_selection()
        self.gallery_btn.setChecked(True)
        self.stack.setCurrentWidget(self.gallery_page)

    def show_beta_page(self, button: SidebarButton) -> None:
        self.clear_selection()
        button.setChecked(True)
        self.stack.setCurrentWidget(self.beta_page)

    def show_dashboard_page(self, button: SidebarButton) -> None:
        self.clear_selection()
        button.setChecked(True)
        self.stack.setCurrentWidget(self.dashboard_page)

    def show_accounts_page(self, button: SidebarButton) -> None:
        self.clear_selection()
        button.setChecked(True)
        self.stack.setCurrentWidget(self.accounts_page)

    def show_revision_page(self, button: SidebarButton) -> None:
        self.clear_selection()
        button.setChecked(True)
        self.stack.setCurrentWidget(self.revision_page)

    def show_compta_params(self, button: SidebarButton) -> None:
        self.clear_selection()
        button.setChecked(True)
        self.stack.setCurrentWidget(self.compta_params_page)

    def show_settings(self, button: SidebarButton) -> None:
        self.clear_selection()
        button.setChecked(True)
        self.stack.setCurrentWidget(self.settings_page)


def main() -> None:
    app = QApplication([])
    theme = ThemeManager(app)
    win = MainWindow(theme)
    win.show()
    app.exec()


if __name__ == "__main__":
    main()
