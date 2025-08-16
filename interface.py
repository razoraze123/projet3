import os
import sys
import json
import re
from pathlib import Path
from datetime import datetime
from uuid import uuid4
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.fonts=false;qt.qpa.*=false")

from typing import Callable

from PySide6.QtCore import (
    Qt,
    QPropertyAnimation,
    QEasingCurve,
    Signal,
    QProcess,
    Slot,
    QTimer,
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
    QSpinBox,
    QSizePolicy,
    QStackedWidget,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QFileDialog,
    QStyle,
    QGraphicsDropShadowEffect,
    QPlainTextEdit,
)

GLOBAL_CONSOLE: QTextEdit | None = None

PROJECT_ROOT = Path(__file__).resolve().parent
SETTINGS_FILE = PROJECT_ROOT / "settings.json"
STYLE_FILE = PROJECT_ROOT / "style.qss"
try:
    PROFILES_PATH = ProfilesStore.path  # si la classe existe déjà
except Exception:
    PROFILES_PATH = Path(__file__).resolve().parent / "profiles.json"

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


class ProfilesStore(QObject):
    """In-memory store with JSON persistence."""

    path = PROJECT_ROOT / "profiles.json"

    def __init__(self) -> None:
        super().__init__()
        self.profiles: list[dict] = self.load()

    def load(self) -> list[dict]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def save(self, profiles: list[dict]) -> None:
        try:
            if self.path.exists():
                bak = self.path.with_suffix(".json.bak")
                bak.write_text(self.path.read_text(encoding="utf-8"), encoding="utf-8")
            self.path.write_text(json.dumps(profiles, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            print_safe(f"[profiles] save error: {e}")

    def new_profile(self) -> dict:
        now = datetime.utcnow().isoformat() + "Z"
        return {
            "id": str(uuid4()),
            "name": "Sans titre",
            "domains": [],
            "tags": [],
            "selectors": {
                "listing": {"image": [], "item_link": []},
                "detail": {"image": []},
                "pagination": {"next": []},
            },
            "transforms": [],
            "fetch": {
                "user_agent": "",
                "delay_ms": 0,
                "max_depth": 0,
                "max_items": 0,
            },
            "notes": "",
            "created_at": now,
            "updated_at": now,
            "version": 1,
        }

    def duplicate(self, profile: dict) -> dict:
        cp = json.loads(json.dumps(profile))
        cp["id"] = str(uuid4())
        cp["name"] = profile.get("name", "") + " (copie)"
        now = datetime.utcnow().isoformat() + "Z"
        cp["created_at"] = now
        cp["updated_at"] = now
        return cp

    def find(self, pid: str) -> dict | None:
        for p in self.profiles:
            if p.get("id") == pid:
                return p
        return None

    def remove(self, pid: str) -> None:
        self.profiles = [p for p in self.profiles if p.get("id") != pid]


class SelectorTester(QObject):
    def split_selector(self, sel: str, key: str) -> tuple[str, str | None]:
        css, attr = sel, None
        if "@" in sel:
            css, attr = sel.split("@", 1)
        else:
            if key == "image":
                attr = "src"
            elif key in {"item_link", "next"}:
                attr = "href"
        return css.strip(), attr

    def apply_transforms(self, val: str, transforms: list[dict]) -> str:
        for tr in transforms:
            try:
                val = re.sub(tr.get("match", ""), tr.get("replace", ""), val)
            except re.error:
                continue
        return val

    def evaluate_html(self, profile: dict, html: str) -> dict:
        results: dict[str, list[dict]] = {}
        selectors = profile.get("selectors", {})
        transforms = profile.get("transforms", [])
        try:
            from lxml import html as lxml_html

            tree = lxml_html.fromstring(html)
            for zone, mapping in selectors.items():
                for key, sels in mapping.items():
                    out_key = f"{zone}.{key}"
                    results[out_key] = []
                    for sel in sels:
                        css, attr = self.split_selector(sel, key)
                        try:
                            nodes = tree.cssselect(css)
                        except Exception:
                            nodes = []
                        for n in nodes:
                            if attr:
                                val = (n.get(attr) or "").strip()
                                if not val and key == "image" and attr == "src":
                                    val = (n.get("data-src") or "").strip()
                            else:
                                val = (n.text_content() or "").strip()
                            val = self.apply_transforms(val, transforms)
                            results[out_key].append({"value": val, "context": lxml_html.tostring(n, encoding="unicode")})
        except Exception:
            from html.parser import HTMLParser

            class Node:
                def __init__(self, tag: str, attrs: dict[str, str]) -> None:
                    self.tag = tag
                    self.attrs = attrs
                    self.children: list["Node"] = []

            class Parser(HTMLParser):
                def __init__(self) -> None:
                    super().__init__()
                    self.stack: list[Node] = []
                    self.root = Node("root", {})
                    self.stack.append(self.root)

                def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
                    node = Node(tag, {k: v or "" for k, v in attrs})
                    self.stack[-1].children.append(node)
                    self.stack.append(node)

                def handle_endtag(self, tag: str) -> None:
                    if len(self.stack) > 1:
                        self.stack.pop()

            parser = Parser()
            parser.feed(html)

            def walk(node: Node) -> list[Node]:
                arr = []
                for c in node.children:
                    arr.append(c)
                    arr.extend(walk(c))
                return arr

            nodes = walk(parser.root)

            def match(node: Node, css: str) -> bool:
                tag = css
                css_id = None
                css_class = None
                attr_name = None
                attr_val = None
                if "#" in tag:
                    tag, css_id = tag.split("#", 1)
                if "." in tag:
                    tag, css_class = tag.split(".", 1)
                m = re.search(r"\[(.+?)\]", tag)
                if m:
                    tag = tag.replace(m.group(0), "")
                    part = m.group(1)
                    if "=" in part:
                        attr_name, attr_val = part.split("=", 1)
                        attr_val = attr_val.strip('"\'')
                    else:
                        attr_name = part
                tag = tag or None
                if tag and node.tag != tag:
                    return False
                if css_id and node.attrs.get("id") != css_id:
                    return False
                if css_class and css_class not in node.attrs.get("class", "").split():
                    return False
                if attr_name:
                    if attr_val is None and attr_name not in node.attrs:
                        return False
                    if attr_val is not None and node.attrs.get(attr_name) != attr_val:
                        return False
                return True

            for zone, mapping in selectors.items():
                for key, sels in mapping.items():
                    out_key = f"{zone}.{key}"
                    results[out_key] = []
                    for sel in sels:
                        css, attr = self.split_selector(sel, key)
                        for n in nodes:
                            if match(n, css):
                                if attr:
                                    val = n.attrs.get(attr, "")
                                    if not val and key == "image" and attr == "src":
                                        val = n.attrs.get("data-src", "")
                                else:
                                    val = ""
                                val = self.apply_transforms(val, transforms)
                                results[out_key].append({"value": val, "context": ""})
        return results


class ProfileEditor(QTabWidget):
    changed = Signal()

    def __init__(self, on_chosen: Callable[[str], None]) -> None:
        super().__init__()
        self.on_chosen = on_chosen
        self.current: dict | None = None

        self.general_tab = QWidget()
        gen_layout = QVBoxLayout(self.general_tab)

        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Nom"))
        self.name_edit = QLineEdit()
        name_layout.addWidget(self.name_edit)
        gen_layout.addLayout(name_layout)

        dom_layout = QHBoxLayout()
        self.domain_edit = QLineEdit()
        add_dom_btn = QPushButton("+")
        dom_layout.addWidget(self.domain_edit)
        dom_layout.addWidget(add_dom_btn)
        gen_layout.addLayout(dom_layout)
        self.domains_list = QListWidget()
        gen_layout.addWidget(self.domains_list)

        fetch_box = QGroupBox("Fetch")
        f_layout = QVBoxLayout(fetch_box)
        ua_layout = QHBoxLayout()
        ua_layout.addWidget(QLabel("User-Agent"))
        self.ua_edit = QLineEdit()
        ua_layout.addWidget(self.ua_edit)
        f_layout.addLayout(ua_layout)

        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("Delay (ms)"))
        self.delay_spin = QSpinBox()
        self.delay_spin.setMaximum(10000)
        delay_layout.addWidget(self.delay_spin)
        f_layout.addLayout(delay_layout)

        depth_layout = QHBoxLayout()
        depth_layout.addWidget(QLabel("Max depth"))
        self.depth_spin = QSpinBox()
        self.depth_spin.setMaximum(100)
        depth_layout.addWidget(self.depth_spin)
        f_layout.addLayout(depth_layout)

        items_layout = QHBoxLayout()
        items_layout.addWidget(QLabel("Max items"))
        self.items_spin = QSpinBox()
        self.items_spin.setMaximum(10000)
        items_layout.addWidget(self.items_spin)
        f_layout.addLayout(items_layout)

        gen_layout.addWidget(fetch_box)
        self.active_btn = QPushButton("Définir comme actif (UI)")
        gen_layout.addWidget(self.active_btn)
        gen_layout.addStretch()
        self.addTab(self.general_tab, "Général")

        add_dom_btn.clicked.connect(self.add_domain)
        self.domains_list.itemDoubleClicked.connect(self.remove_domain)
        self.name_edit.textChanged.connect(self.changed.emit)
        self.domain_edit.textChanged.connect(self.changed.emit)
        self.ua_edit.textChanged.connect(self.changed.emit)
        self.delay_spin.valueChanged.connect(self.changed.emit)
        self.depth_spin.valueChanged.connect(self.changed.emit)
        self.items_spin.valueChanged.connect(self.changed.emit)
        self.active_btn.clicked.connect(self._emit_active)

        self.selectors_tab = QWidget()
        sel_layout = QVBoxLayout(self.selectors_tab)
        self.sel_table = QTableWidget(0, 5)
        self.sel_table.setHorizontalHeaderLabels(["Zone", "Clé", "Sélecteur CSS", "Attr", "Sortie"])
        self.sel_table.horizontalHeader().setStretchLastSection(True)
        sel_layout.addWidget(self.sel_table)
        btn_lay = QHBoxLayout()
        self.sel_add_btn = QPushButton("Ajouter")
        self.sel_dup_btn = QPushButton("Dupliquer")
        self.sel_del_btn = QPushButton("Supprimer")
        btn_lay.addWidget(self.sel_add_btn)
        btn_lay.addWidget(self.sel_dup_btn)
        btn_lay.addWidget(self.sel_del_btn)
        btn_lay.addStretch()
        sel_layout.addLayout(btn_lay)

        sel_layout.addWidget(QLabel("Transforms"))
        self.tr_table = QTableWidget(0, 2)
        self.tr_table.setHorizontalHeaderLabels(["Regex", "Replace"])
        sel_layout.addWidget(self.tr_table)
        self.addTab(self.selectors_tab, "Sélecteurs")

        self.sel_table.itemChanged.connect(self.changed.emit)
        self.tr_table.itemChanged.connect(self.changed.emit)
        self.sel_add_btn.clicked.connect(self.add_selector_row)
        self.sel_dup_btn.clicked.connect(self.duplicate_selector_row)
        self.sel_del_btn.clicked.connect(self.remove_selector_row)

        self.test_tab = QWidget()
        t_layout = QVBoxLayout(self.test_tab)
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("URL test"))
        self.url_edit = QLineEdit()
        url_layout.addWidget(self.url_edit)
        t_layout.addLayout(url_layout)
        self.html_edit = QPlainTextEdit()
        self.html_edit.setPlaceholderText("Collez du HTML ici…")
        t_layout.addWidget(self.html_edit)
        self.eval_btn = QPushButton("Évaluer")
        t_layout.addWidget(self.eval_btn)
        self.summary_tree = QTreeWidget()
        self.summary_tree.setHeaderLabels(["Sélecteur", "Matches"])
        t_layout.addWidget(self.summary_tree)
        self.result_table = QTableWidget(0, 2)
        self.result_table.setHorizontalHeaderLabels(["Clé", "Valeur"])
        self.result_table.horizontalHeader().setStretchLastSection(True)
        t_layout.addWidget(self.result_table)
        self.addTab(self.test_tab, "Test")
        self.eval_btn.clicked.connect(self.evaluate_now)

        self.notes_tab = QWidget()
        notes_layout = QVBoxLayout(self.notes_tab)
        self.notes_edit = QPlainTextEdit()
        notes_layout.addWidget(self.notes_edit)
        self.addTab(self.notes_tab, "Notes")
        self.notes_edit.textChanged.connect(self.changed.emit)

    def add_domain(self) -> None:
        text = self.domain_edit.text().strip()
        if text:
            self.domains_list.addItem(text)
            self.domain_edit.clear()
            self.changed.emit()

    def remove_domain(self, item: QListWidgetItem) -> None:
        row = self.domains_list.row(item)
        self.domains_list.takeItem(row)
        self.changed.emit()

    def _emit_active(self) -> None:
        if self.current:
            self.on_chosen(self.current.get("name", ""))

    def add_selector_row(self) -> None:
        row = self.sel_table.rowCount()
        self.sel_table.insertRow(row)
        for col, val in enumerate(["listing", "image", "", "", "url"]):
            self.sel_table.setItem(row, col, QTableWidgetItem(val))
        self.changed.emit()

    def duplicate_selector_row(self) -> None:
        row = self.sel_table.currentRow()
        if row < 0:
            return
        vals = [self.sel_table.item(row, c).text() for c in range(5)]
        self.sel_table.insertRow(row + 1)
        for c, v in enumerate(vals):
            self.sel_table.setItem(row + 1, c, QTableWidgetItem(v))
        self.changed.emit()

    def remove_selector_row(self) -> None:
        rows = sorted({i.row() for i in self.sel_table.selectedIndexes()}, reverse=True)
        for r in rows:
            self.sel_table.removeRow(r)
        if rows:
            self.changed.emit()

    def load_profile(self, profile: dict) -> None:
        self.current = profile
        self.name_edit.setText(profile.get("name", ""))
        self.domains_list.clear()
        for d in profile.get("domains", []):
            self.domains_list.addItem(d)
        self.ua_edit.setText(profile.get("fetch", {}).get("user_agent", ""))
        self.delay_spin.setValue(profile.get("fetch", {}).get("delay_ms", 0))
        self.depth_spin.setValue(profile.get("fetch", {}).get("max_depth", 0))
        self.items_spin.setValue(profile.get("fetch", {}).get("max_items", 0))

        self.sel_table.setRowCount(0)
        selectors = profile.get("selectors", {})
        for zone, mapping in selectors.items():
            for key, sels in mapping.items():
                for sel in sels:
                    css, attr = sel.split("@", 1) if "@" in sel else (sel, "")
                    row = self.sel_table.rowCount()
                    self.sel_table.insertRow(row)
                    self.sel_table.setItem(row, 0, QTableWidgetItem(zone))
                    self.sel_table.setItem(row, 1, QTableWidgetItem(key))
                    self.sel_table.setItem(row, 2, QTableWidgetItem(css))
                    self.sel_table.setItem(row, 3, QTableWidgetItem(attr))
                    self.sel_table.setItem(row, 4, QTableWidgetItem("url"))

        self.tr_table.setRowCount(0)
        for tr in profile.get("transforms", []):
            r = self.tr_table.rowCount()
            self.tr_table.insertRow(r)
            self.tr_table.setItem(r, 0, QTableWidgetItem(tr.get("match", "")))
            self.tr_table.setItem(r, 1, QTableWidgetItem(tr.get("replace", "")))

        self.notes_edit.setPlainText(profile.get("notes", ""))

    def read_profile(self) -> dict:
        if not self.current:
            return {}
        p = self.current
        p["name"] = self.name_edit.text().strip()
        p["domains"] = [self.domains_list.item(i).text() for i in range(self.domains_list.count())]
        p.setdefault("fetch", {})
        p["fetch"].update({
            "user_agent": self.ua_edit.text().strip(),
            "delay_ms": self.delay_spin.value(),
            "max_depth": self.depth_spin.value(),
            "max_items": self.items_spin.value(),
        })
        selectors: dict[str, dict[str, list[str]]] = {}
        for row in range(self.sel_table.rowCount()):
            zone = self.sel_table.item(row, 0).text().strip()
            key = self.sel_table.item(row, 1).text().strip()
            css = self.sel_table.item(row, 2).text().strip()
            attr = self.sel_table.item(row, 3).text().strip()
            sel = f"{css}@{attr}" if attr else css
            selectors.setdefault(zone, {}).setdefault(key, []).append(sel)
        p["selectors"] = selectors

        transforms: list[dict] = []
        for row in range(self.tr_table.rowCount()):
            reg = self.tr_table.item(row, 0)
            rep = self.tr_table.item(row, 1)
            if reg and rep:
                transforms.append({"match": reg.text(), "replace": rep.text()})
        p["transforms"] = transforms
        p["notes"] = self.notes_edit.toPlainText()
        p["updated_at"] = datetime.utcnow().isoformat() + "Z"
        return p

    def evaluate_now(self) -> None:
        if not self.current:
            return
        profile = self.read_profile()
        tester = SelectorTester()
        html = self.html_edit.toPlainText()
        res = tester.evaluate_html(profile, html)
        self.render_summary(res)

    def render_summary(self, data: dict[str, list[dict]]) -> None:
        self.summary_tree.clear()
        self.result_table.setRowCount(0)
        for key, values in data.items():
            top = QTreeWidgetItem([key, str(len(values))])
            self.summary_tree.addTopLevelItem(top)
            for v in values[:3]:
                QTreeWidgetItem(top, [v.get("value", "")])
            for v in values:
                r = self.result_table.rowCount()
                self.result_table.insertRow(r)
                self.result_table.setItem(r, 0, QTableWidgetItem(key))
                self.result_table.setItem(r, 1, QTableWidgetItem(v.get("value", "")))


class ProfileScrapingWidget(QWidget):
    profile_chosen = Signal(str)
    profiles_updated = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.store = ProfilesStore()
        self.current_id: str | None = None

        main_layout = QHBoxLayout(self)

        left = QVBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Recherche…")
        left.addWidget(self.search_edit)
        self.list_widget = QListWidget()
        left.addWidget(self.list_widget, 1)
        btn_lay = QHBoxLayout()
        self.new_btn = QPushButton("+ Nouveau")
        self.dup_btn = QPushButton("Dupliquer")
        self.exp_btn = QPushButton("Exporter")
        self.imp_btn = QPushButton("Importer")
        self.del_btn = QPushButton("Supprimer")
        for b in [self.new_btn, self.dup_btn, self.exp_btn, self.imp_btn, self.del_btn]:
            btn_lay.addWidget(b)
        left.addLayout(btn_lay)
        main_layout.addLayout(left, 1)

        self.editor = ProfileEditor(lambda name: self.profile_chosen.emit(name))
        main_layout.addWidget(self.editor, 3)

        bottom = QVBoxLayout()
        self.status_label = QLabel("Profil: - | Sauvegardé: -")
        bottom.addWidget(self.status_label)
        main_layout.addLayout(bottom)

        for p in self.store.profiles:
            self._add_list_item(p)

        self.list_widget.currentItemChanged.connect(self._on_select)
        self.search_edit.textChanged.connect(self._filter_list)

        self.new_btn.clicked.connect(self._create_new)
        self.dup_btn.clicked.connect(self._duplicate)
        self.del_btn.clicked.connect(self._delete)
        self.exp_btn.clicked.connect(self._export)
        self.imp_btn.clicked.connect(self._import)

        self.editor.changed.connect(self._schedule_save)
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(500)
        self.save_timer.timeout.connect(self._autosave)

        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def _add_list_item(self, profile: dict) -> None:
        item = QListWidgetItem(profile.get("name", ""))
        item.setData(Qt.UserRole, profile.get("id"))
        item.setToolTip(", ".join(profile.get("domains", [])))
        imgs = profile.get("selectors", {}).get("listing", {}).get("image", [])
        if imgs:
            item.setForeground(QColor("green"))
        else:
            item.setForeground(QColor("orange"))
        self.list_widget.addItem(item)

    def _filter_list(self, text: str) -> None:
        t = text.lower()
        for i in range(self.list_widget.count()):
            it = self.list_widget.item(i)
            name = it.text().lower()
            dom = it.toolTip().lower()
            it.setHidden(t not in name and t not in dom)

    def _on_select(self, item: QListWidgetItem) -> None:
        if not item:
            return
        pid = item.data(Qt.UserRole)
        self.current_id = pid
        prof = self.store.find(pid)
        if prof:
            self.editor.load_profile(prof)
            self.status_label.setText(f"Profil: {prof.get('name')} | Sauvegardé: {prof.get('updated_at')}")

    def _create_new(self) -> None:
        p = self.store.new_profile()
        self.store.profiles.append(p)
        self._add_list_item(p)
        self.list_widget.setCurrentRow(self.list_widget.count() - 1)
        self._autosave()
        print_safe("Profil créé")

    def _duplicate(self) -> None:
        item = self.list_widget.currentItem()
        if not item:
            return
        prof = self.store.find(item.data(Qt.UserRole))
        if not prof:
            return
        p = self.store.duplicate(prof)
        self.store.profiles.append(p)
        self._add_list_item(p)
        self.list_widget.setCurrentRow(self.list_widget.count() - 1)
        self._autosave()
        print_safe("Profil dupliqué")

    def _delete(self) -> None:
        item = self.list_widget.currentItem()
        if not item:
            return
        if QMessageBox.question(self, "Confirmer", "Supprimer ce profil ?") != QMessageBox.Yes:
            return
        pid = item.data(Qt.UserRole)
        self.store.remove(pid)
        row = self.list_widget.row(item)
        self.list_widget.takeItem(row)
        self._autosave()
        self.profiles_updated.emit()
        print_safe("Profil supprimé")

    def _export(self) -> None:
        item = self.list_widget.currentItem()
        if not item:
            return
        prof = self.store.find(item.data(Qt.UserRole))
        if not prof:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exporter profil", "profile.json", "JSON (*.json)")
        if path:
            try:
                Path(path).write_text(json.dumps(prof, indent=2, ensure_ascii=False), encoding="utf-8")
                print_safe("Profil exporté")
            except Exception as e:
                print_safe(f"Export erreur: {e}")

    def _import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Importer profil", "", "JSON (*.json)")
        if not path:
            return
        try:
            prof = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception as e:
            print_safe(f"Import erreur: {e}")
            return
        if not isinstance(prof, dict) or "id" not in prof or "name" not in prof or "selectors" not in prof:
            print_safe("Profil invalide")
            return
        if self.store.find(prof["id"]):
            prof["id"] = str(uuid4())
        self.store.profiles.append(prof)
        self._add_list_item(prof)
        self.list_widget.setCurrentRow(self.list_widget.count() - 1)
        self._autosave()
        print_safe("Profil importé")

    def _schedule_save(self) -> None:
        self.save_timer.start()

    def _autosave(self) -> None:
        if not self.current_id:
            return
        prof = self.store.find(self.current_id)
        if not prof:
            return
        self.editor.read_profile()
        self.store.save(self.store.profiles)
        self.status_label.setText(f"Profil: {prof.get('name')} | Sauvegardé: {prof.get('updated_at')}")
        self.profiles_updated.emit()
        print_safe("Profil sauvegardé")


class GalleryWidget(SimpleLabelPage):
    def __init__(self) -> None:
        super().__init__("Galerie (stub)")


class ImagesWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)

        file_layout = QHBoxLayout()
        file_layout.addWidget(QLabel("Fichier :"))
        self.file_edit = QLineEdit()
        file_layout.addWidget(self.file_edit)
        browse_file = QPushButton("Parcourir…")
        browse_file.clicked.connect(self.browse_file)
        file_layout.addWidget(browse_file)
        layout.addLayout(file_layout)

        profile_layout = QHBoxLayout()
        profile_layout.addWidget(QLabel("Profil :"))
        self.profile_combo = QComboBox()
        profile_layout.addWidget(self.profile_combo)
        layout.addLayout(profile_layout)

        folder_layout = QHBoxLayout()
        folder_layout.addWidget(QLabel("Dossier :"))
        self.folder_edit = QLineEdit()
        folder_layout.addWidget(self.folder_edit)
        browse_folder = QPushButton("Parcourir…")
        browse_folder.clicked.connect(self.browse_folder)
        folder_layout.addWidget(browse_folder)
        layout.addLayout(folder_layout)

        self.variants_cb = QCheckBox("Scraper aussi les variantes")
        self.isolate_cb = QCheckBox("Isoler (QProcess)")
        layout.addWidget(self.variants_cb)
        layout.addWidget(self.isolate_cb)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.launch_btn = QPushButton("Lancer")
        copy_btn = QPushButton("Copier")
        export_btn = QPushButton("Exporter")
        btn_layout.addWidget(self.launch_btn)
        btn_layout.addWidget(copy_btn)
        btn_layout.addWidget(export_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)
        self.progress_label = QLabel("Progression 0/0")
        layout.addWidget(self.progress_label)
        self.launch_btn.clicked.connect(self.run_example)
        copy_btn.clicked.connect(lambda: print_safe("Copier simulé"))
        export_btn.clicked.connect(lambda: print_safe("Exporter simulé"))
        self.profile_combo.currentTextChanged.connect(self._save_last_profile)

    def browse_file(self) -> None:
        QFileDialog.getOpenFileName(self, "Choisir fichier")

    def browse_folder(self) -> None:
        QFileDialog.getExistingDirectory(self, "Choisir dossier")

    def run_example(self) -> None:
        self.list_widget.clear()
        for i in range(2):
            item = QListWidgetItem(f"Image {i+1}")
            item.setCheckState(Qt.Checked)
            self.list_widget.addItem(item)
        self.progress_label.setText("Progression 2/2")
        print_safe("Scrap simulé : 2 éléments")

    def _save_last_profile(self, name: str) -> None:
        try:
            s = load_settings()
            s["last_profile_name"] = name
            save_settings(s)
        except Exception:
            pass

    def set_selected_profile(self, name: str) -> None:
        if not name:
            return
        idx = self.profile_combo.findText(name)
        if idx < 0:
            # si le profil vient d’être créé et n’est pas encore dans la liste
            self.profile_combo.addItem(name)
            idx = self.profile_combo.count() - 1
        self.profile_combo.setCurrentIndex(idx)

    def refresh_profiles(self) -> None:
        """Recharge la liste des profils depuis profiles.json."""
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        names: list[str] = []
        try:
            path = PROFILES_PATH
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                # récupère les noms valides
                names = [str(p.get("name", "")).strip() for p in data if p.get("name")]
        except Exception as e:
            print_safe(f"[profiles] Chargement impossible: {e}")
        # dédoublonne + trie
        names = sorted(dict.fromkeys([n for n in names if n]))
        if names:
            self.profile_combo.addItems(names)
        else:
            self.profile_combo.addItem("(aucun profil)")
        self.profile_combo.blockSignals(False)


class ScrapWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self.images_widget = ImagesWidget()
        self.tabs.addTab(self.images_widget, "Images")
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
        self.preview_buttons: list[QPushButton] = []
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

        self.profiles_btn = SidebarButton("Profil Scraping", get_icon("profil_scraping"))
        self.profiles_btn.setObjectName("sidebar-item")
        self.profiles_btn.clicked.connect(lambda _, b=self.profiles_btn: self.show_profiles(b))
        self.scrap_section.add_widget(self.profiles_btn)
        self.button_group.append(self.profiles_btn)

        self.gallery_btn = SidebarButton("Galerie", get_icon("galerie"))
        self.gallery_btn.setObjectName("sidebar-item")
        self.gallery_btn.clicked.connect(lambda _, b=self.gallery_btn: self.show_gallery_tab())
        self.scrap_section.add_widget(self.gallery_btn)
        self.button_group.append(self.gallery_btn)
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

        self.profile_page = ProfileScrapingWidget()
        self.scrap_page = ScrapWidget()
        self.gallery_page = GalleryWidget()
        self.dashboard_page = DashboardWidget()
        self.accounts_page = AccountWidget()
        self.revision_page = RevisionTab()
        self.compta_params_page = SimpleLabelPage("Paramètres compta (stub)")
        self.settings_page = SettingsPage(self.theme)

        for w in [
            self.profile_page,
            self.scrap_page,
            self.gallery_page,
            self.dashboard_page,
            self.accounts_page,
            self.revision_page,
            self.compta_params_page,
            self.settings_page,
        ]:
            self.stack.addWidget(w)

        self.profile_page.profile_chosen.connect(self.scrap_page.images_widget.set_selected_profile)
        self.profile_page.profiles_updated.connect(self.scrap_page.images_widget.refresh_profiles)
        self.scrap_page.images_widget.refresh_profiles()
        last = load_settings().get("last_profile_name", "")
        if last:
            self.scrap_page.images_widget.set_selected_profile(last)

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
            add("Ctrl+2", lambda: self.show_profiles(self.profiles_btn))
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

    def show_profiles(self, button: SidebarButton) -> None:
        self.clear_selection()
        button.setChecked(True)
        self.stack.setCurrentWidget(self.profile_page)

    def show_gallery_tab(self) -> None:
        self.clear_selection()
        self.gallery_btn.setChecked(True)
        self.stack.setCurrentWidget(self.gallery_page)

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
