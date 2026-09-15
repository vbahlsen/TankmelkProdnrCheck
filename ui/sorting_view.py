"""Den enorme sorteringsparameter-visningen som brukes i Sorteringsmodus.

Et eget, vanlig (ikke ekte fullskjerm) vindu som kan dras/endres i størrelse.
Størrelse og posisjon lagres debounced til settings.json og gjenopprettes ved
neste oppstart. Vi parser/skriver geometry()-strengen direkte (ikke
winfo_x()/winfo_y()) siden de kan rapportere ramme- vs. klientkoordinater
inkonsistent på Windows.
"""

import re

import customtkinter as ctk

_GEOMETRY_RE = re.compile(r"(\d+)x(\d+)\+(-?\d+)\+(-?\d+)")


class SortingView:
    def __init__(self, root, app_settings: dict, on_settings_changed, on_closed_by_user, on_retry_save):
        self.root = root
        self.app_settings = app_settings
        self.on_settings_changed = on_settings_changed
        self.on_closed_by_user = on_closed_by_user
        self.on_retry_save = on_retry_save

        self.window = None
        self.number_label = None
        self.status_label = None
        self.save_status_label = None
        self.retry_button = None
        self._resize_after_id = None

    def _ensure_built(self):
        if self.window is not None and self.window.winfo_exists():
            return
        self._build()

    def _build(self):
        self.window = ctk.CTkToplevel(self.root)
        self.window.title("Sortering")

        geo = self.app_settings["window_geometry"]["sorting"]
        if geo.get("width") and geo.get("height"):
            w, h = geo["width"], geo["height"]
            x = geo["x"] if geo["x"] is not None else 100
            y = geo["y"] if geo["y"] is not None else 100
            self.window.geometry(f"{w}x{h}+{x}+{y}")
        else:
            sw = self.window.winfo_screenwidth()
            sh = self.window.winfo_screenheight()
            w, h = int(sw * 0.9), int(sh * 0.9)
            x, y = int(sw * 0.05), int(sh * 0.05)
            self.window.geometry(f"{w}x{h}+{x}+{y}")

        self.number_label = ctk.CTkLabel(
            self.window, text="", font=ctk.CTkFont(size=380, weight="bold"),
        )
        self.number_label.pack(expand=True, fill="both")

        bottom = ctk.CTkFrame(self.window, fg_color="transparent")
        bottom.pack(side="bottom", fill="x", pady=10)

        self.status_label = ctk.CTkLabel(bottom, text="", font=ctk.CTkFont(size=22))
        self.status_label.pack()

        self.save_status_label = ctk.CTkLabel(
            bottom, text="", font=ctk.CTkFont(size=16, weight="bold"), text_color="#e74c3c",
        )
        self.save_status_label.pack(pady=(4, 0))

        self.retry_button = ctk.CTkButton(
            bottom, text="Prøv igjen", command=self._retry_clicked, font=ctk.CTkFont(size=14),
        )
        # pakkes inn/ut av set_pending_save()

        self.window.bind("<Configure>", self._on_configure)
        self.window.protocol("WM_DELETE_WINDOW", self._on_close_clicked)

    def show(self):
        self._ensure_built()
        self.window.deiconify()
        # Hovedvinduet har -topmost=True, så uten dette havner sorteringsvisningen
        # bak hovedvinduet i stedet for foran -- den er det viktige mens
        # sorteringsmodus er aktiv, så den skal vinne kappestriden om å være øverst.
        self.window.attributes("-topmost", True)
        self.window.lift()
        self.window.focus_force()

    def hide(self):
        if self.window is not None and self.window.winfo_exists():
            self.window.attributes("-topmost", False)
            self.window.withdraw()

    def _on_configure(self, event):
        if event.widget is not self.window:
            return
        if self._resize_after_id is not None:
            self.window.after_cancel(self._resize_after_id)
        self._resize_after_id = self.window.after(500, self._persist_geometry)

    def _persist_geometry(self):
        self._resize_after_id = None
        if self.window is None or not self.window.winfo_exists():
            return
        match = _GEOMETRY_RE.match(self.window.geometry())
        if not match:
            return
        w, h, x, y = map(int, match.groups())
        self.app_settings["window_geometry"]["sorting"] = {"width": w, "height": h, "x": x, "y": y}
        self.on_settings_changed(self.app_settings)

    def _on_close_clicked(self):
        self.hide()
        if self.on_closed_by_user:
            self.on_closed_by_user()

    def _retry_clicked(self):
        if self.on_retry_save:
            self.on_retry_save()

    # --- Visning av resultater ---
    #
    # Alle disse kan i prinsippet kalles før vinduet noensinne er vist (f.eks.
    # attempt_save() kalt rett etter en av-lagring som skjer FØR sorting_view.show()
    # rekker å bygge widgetene) -- derfor _ensure_built() først i hver, i stedet for
    # å stole på at kalleren alltid har kalt show() tidligere.

    def show_number(self, value: int) -> None:
        self._ensure_built()
        self.number_label.configure(text=str(value), text_color="#2ecc71")
        self.status_label.configure(text="")

    def show_invalid_parameter(self, scanned_code: str) -> None:
        self._ensure_built()
        self.number_label.configure(text="?", text_color="#e67e22")
        self.status_label.configure(
            text=f"Ugyldig sorteringsparameter for {scanned_code}", text_color="#e67e22",
        )

    def show_not_in_list(self) -> None:
        self._ensure_built()
        self.number_label.configure(text="", text_color="#e74c3c")
        self.status_label.configure(text="IKKE I UTTAKSLISTEN", text_color="#e74c3c")

    def show_error(self, text: str) -> None:
        self._ensure_built()
        self.status_label.configure(text=text, text_color="#e74c3c")

    def set_pending_save(self, pending: bool) -> None:
        self._ensure_built()
        if pending:
            self.save_status_label.configure(
                text="LAGRING BLOKKERT -- lukk filen i Excel for å fortsette lagring",
            )
            self.retry_button.pack(pady=(6, 0))
        else:
            self.save_status_label.configure(text="")
            self.retry_button.pack_forget()
