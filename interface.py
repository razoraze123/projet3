import os
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.fonts=false;qt.qpa.*=false")

from typing import Callable

from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, Signal
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QFileDialog,
    QStyle,
)

GLOBAL_CONSOLE: QTextEdit | None = None


def print_safe(msg: str) -> None:
    print(msg)
    if GLOBAL_CONSOLE is not None:
        GLOBAL_CONSOLE.append(msg)


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

    def apply(self, theme: str) -> None:
        if theme == "light":
            self.app.setStyleSheet(""
                "QWidget{background:#fff;color:#000;}"
                "QPushButton{background:#f0f0f0;}"
                "QPushButton:hover{background:#e0e0e0;}"
            "")
        else:
            self.app.setStyleSheet(""
                "QWidget{background:#2b2b2b;color:#ddd;}"
                "QPushButton{background:#444;color:#fff;}"
                "QPushButton:hover{background:#555;}"
            "")


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


class ProfileWidget(QWidget):
    profile_chosen = Signal(str)
    profiles_updated = Signal()

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Profil Scraping (stub)", alignment=Qt.AlignCenter))
        choose = QPushButton("Choisir profil")
        refresh = QPushButton("Rafraîchir profils")
        layout.addWidget(choose)
        layout.addWidget(refresh)
        layout.addStretch()
        choose.clicked.connect(lambda: self.profile_chosen.emit("bob crew"))
        refresh.clicked.connect(self.profiles_updated)


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
        self.profile_combo.addItem("bob crew")
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

    def set_selected_profile(self, name: str) -> None:
        idx = self.profile_combo.findText(name)
        if idx >= 0:
            self.profile_combo.setCurrentIndex(idx)

    def refresh_profiles(self) -> None:
        print_safe("Rafraîchissement des profils")


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


class SettingsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        buttons_layout = QHBoxLayout()
        update_btn = QPushButton("Mettre à jour l'app")
        restart_btn = QPushButton("Redémarrer")
        txt_btn = QPushButton("Mettre à jour le txt")
        buttons_layout.addWidget(update_btn)
        buttons_layout.addWidget(restart_btn)
        buttons_layout.addWidget(txt_btn)
        layout.addLayout(buttons_layout)
        self.console = QTextEdit(readOnly=True)
        layout.addWidget(self.console)
        global GLOBAL_CONSOLE
        GLOBAL_CONSOLE = self.console
        update_btn.clicked.connect(lambda: print_safe("Mise à jour simulée… OK"))
        restart_btn.clicked.connect(lambda: print_safe("Redémarrage simulé… OK"))
        txt_btn.clicked.connect(lambda: print_safe("Régénération du txt simulée… OK"))


class MainWindow(QMainWindow):
    def __init__(self, theme: ThemeManager) -> None:
        super().__init__()
        self.theme = theme
        self.theme.apply("light")
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
            self.compta_buttons[name] = btn
            btn.clicked.connect(lambda _, b=btn, h=handler: h(b))
            self.compta_section.add_widget(btn)
            self.button_group.append(btn)
        nav_layout.addWidget(self.compta_section)

        self.scrap_section = CollapsibleSection("🛠️ Scraping")
        self.scrap_btn = SidebarButton("Scrap", get_icon("scrap"))
        self.scrap_btn.clicked.connect(lambda _, b=self.scrap_btn: self.show_scrap_page(b))
        self.scrap_section.add_widget(self.scrap_btn)
        self.button_group.append(self.scrap_btn)

        self.profiles_btn = SidebarButton("Profil Scraping", get_icon("profil_scraping"))
        self.profiles_btn.clicked.connect(lambda _, b=self.profiles_btn: self.show_profiles(b))
        self.scrap_section.add_widget(self.profiles_btn)
        self.button_group.append(self.profiles_btn)

        self.gallery_btn = SidebarButton("Galerie", get_icon("galerie"))
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
        self.settings_btn.clicked.connect(lambda _, b=self.settings_btn: self.show_settings(b))
        self.button_group.append(self.settings_btn)
        sidebar_layout.addWidget(self.settings_btn)

        self.stack = AnimatedStack()
        self.stack.addWidget(SimpleLabelPage("Bienvenue sur COMPTA"))
        main_layout.addWidget(sidebar_container, 1)
        main_layout.addWidget(self.stack, 4)

        self.profile_page = ProfileWidget()
        self.scrap_page = ScrapWidget()
        self.gallery_page = GalleryWidget()
        self.dashboard_page = DashboardWidget()
        self.accounts_page = AccountWidget()
        self.revision_page = RevisionTab()
        self.compta_params_page = SimpleLabelPage("Paramètres compta (stub)")
        self.settings_page = SettingsPage()

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
