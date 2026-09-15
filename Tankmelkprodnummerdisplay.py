"""Tankmelk Scanner -- hovedprogram.

Leser strekkode-/datamatrix-skanninger (via pynput -- skanneren fungerer som et
HID-tastatur) og kryssjekker dem mot en Excel-liste, i to modi:

- Uttaksmodus (standard): slår opp produsentnr og viser hvilke analyser som skal
  kjøres, med duplikatvarsel og utklippstavle-kopiering -- som før.
- Sorteringsmodus (valgfri, alltid AV ved oppstart): brukes til fysisk sortering
  av innkommende prøver i baner 1-15, med enorm tallvisning og lydvarsler.
"""

import csv
import os
import re
import threading
import time
import traceback
from datetime import datetime

import customtkinter as ctk
from tkinter import messagebox
from pynput import keyboard

import audio
import excel_io
import settings as settings_module
from ui import setup_wizard
from ui.settings_dialog import open_settings_dialog
from ui.sorting_view import SortingView

DUPLICATE_FILE = "TANKMELK DUPLIKATER.csv"
_GEOMETRY_RE = re.compile(r"(\d+)x(\d+)\+(-?\d+)\+(-?\d+)")


class AppState:
    def __init__(self):
        self.input_buffer = ""
        self.last_key_time = time.time()
        self.code_format = None
        self.excel: excel_io.ExcelSession | None = None
        self.scanned_codes = set()
        self.duplicate_check_enabled = True
        self.sorteringsmodus_enabled = False
        self.settings = settings_module.load()
        self.pending_save = False
        self.pending_save_after_id = None
        self.window_geo_after_id = None


state = AppState()

root = None
result_label = None
duplicate_check_var = None
sorting_var = None
sorting_view: SortingView | None = None
# Vises alltid i hovedvinduet (uavhengig av modus/om sorteringsvinduet er skjult),
# slik at en blokkert lagring aldri blir usynlig for brukeren.
main_save_status_label = None


# --- Kjernefunksjoner ---

def extract_search_str(scanned_code: str) -> str | None:
    """Trekker ut søkestrengen fra en skannet kode, basert på valgt kodeformat.
    Viser feilmelding og returnerer None ved feil lengde."""
    if state.code_format == "datamatrix":
        if len(scanned_code) == 34:
            return scanned_code[1:9]
        update_result_window(
            f"FEIL: Forventet 34 tegn (Datamatrix)\nMottok: {len(scanned_code)} tegn", "red"
        )
        return None
    elif state.code_format == "strekkode":
        if len(scanned_code) == 10:
            return scanned_code[0:8]
        update_result_window(
            f"FEIL: Forventet 10 siffer (Strekkode)\nMottok: {len(scanned_code)} tegn", "red"
        )
        return None
    update_result_window("FEIL: Kodeformat ikke valgt", "red")
    return None


def process_scanned_code(scanned_code: str) -> None:
    if state.sorteringsmodus_enabled:
        handle_sorting_scan(scanned_code)
    else:
        handle_normal_scan(scanned_code)


def handle_normal_scan(scanned_code: str) -> None:
    if state.duplicate_check_enabled and scanned_code in state.scanned_codes:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(DUPLICATE_FILE, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([scanned_code, timestamp])
        audio.play_cue("mottatt_duplikat", state.settings["volume"])
        messagebox.showwarning("Duplikat funnet!", f"Koden:\n{scanned_code}\nhar allerede blitt skannet!")
        return

    state.scanned_codes.add(scanned_code)

    search_str = extract_search_str(scanned_code)
    if search_str is None:
        return

    row = state.excel.find_matching_row(search_str)
    if row is None:
        audio.play_cue("ikke_i_uttaksliste", state.settings["volume"])
        update_result_window("IKKE I UTTAKSLISTEN", "red")
        return

    found_code = state.excel.get_producer_value(row)
    root.clipboard_clear()
    root.clipboard_append(found_code)

    analyses = state.excel.get_analyses_to_perform(row)
    result_text = found_code
    if analyses:
        result_text += "\n\n--- ANALYSER ---\n" + "\n".join(f"• {a}" for a in analyses)
    update_result_window(result_text, "green")


def handle_sorting_scan(scanned_code: str) -> None:
    search_str = extract_search_str(scanned_code)
    if search_str is None:
        return

    row = state.excel.find_matching_row(search_str)

    if row is None:
        sorting_view.show_not_in_list()
        audio.play_cue("ikke_i_uttaksliste", state.settings["volume"])
        state.excel.register_unmatched_scan(scanned_code)
        attempt_save()
        return

    # Les og vis/spill sorteringsparameteret FØR vi muterer/lagrer -- operatøren
    # skal ikke stå og vente på en disk-skriving før banen vises/høres.
    parameter = state.excel.get_sorteringsparameter(row)
    if parameter is not None:
        sorting_view.show_number(parameter)
        audio.play_cue(str(parameter), state.settings["volume"])
    else:
        sorting_view.show_invalid_parameter(scanned_code)

    new_count = state.excel.increment_mottaksstatus(row)
    if new_count > 1:
        if parameter is not None:
            # Kjede etter tallcue'en i stedet for å avbryte den (winsound spiller
            # kun én lyd om gangen).
            root.after(audio.CUE_CHAIN_GAP_MS, lambda: audio.play_cue(
                "mottatt_duplikat", state.settings["volume"], purge=False
            ))
        else:
            audio.play_cue("mottatt_duplikat", state.settings["volume"])

    attempt_save()


def attempt_save() -> None:
    ok = state.excel.save()
    state.pending_save = not ok
    if sorting_view is not None:
        sorting_view.set_pending_save(state.pending_save)
    if main_save_status_label is not None:
        main_save_status_label.configure(
            text="LAGRING BLOKKERT -- lukk filen i Excel" if state.pending_save else ""
        )
    if state.pending_save_after_id is not None:
        root.after_cancel(state.pending_save_after_id)
        state.pending_save_after_id = None
    if state.pending_save:
        state.pending_save_after_id = root.after(3000, attempt_save)


# --- Tastaturhåndtering ---

def on_key_release(key) -> None:
    current_time = time.time()
    time_diff = current_time - state.last_key_time
    state.last_key_time = current_time

    if time_diff > 0.2 and state.input_buffer:
        state.input_buffer = ""

    if key == keyboard.Key.enter:
        buffer = state.input_buffer
        if state.code_format == "datamatrix" and len(buffer) == 34:
            root.after(0, process_scanned_code, buffer)
        elif state.code_format == "strekkode" and len(buffer) == 10:
            root.after(0, process_scanned_code, buffer)
        elif buffer:
            expected = "34 tegn" if state.code_format == "datamatrix" else "10 siffer"
            root.after(0, update_result_window,
                       f"FEIL: Forventet {expected}\nMottok: {len(buffer)} tegn", "red")
        state.input_buffer = ""
    elif hasattr(key, "char") and key.char:
        state.input_buffer += key.char


def start_keyboard_listener() -> None:
    with keyboard.Listener(on_release=on_key_release) as listener:
        listener.join()


# --- GUI ---

def toggle_duplicate_check() -> None:
    state.duplicate_check_enabled = duplicate_check_var.get()


def toggle_sorteringsmodus() -> None:
    if sorting_var.get():
        if state.excel.sorting_col_idx is None:
            messagebox.showwarning(
                "Sorteringsparameter-kolonne mangler",
                "Sorteringsparameter-kolonne er ikke valgt. Kan ikke bruke sorteringsmodus.",
            )
            sorting_var.set(False)
            return
        state.sorteringsmodus_enabled = True
        sorting_view.show()
        # Hovedvinduet skal ikke lenger kjempe om å ligge øverst -- sorteringsvisningen
        # er det viktige nå.
        root.attributes("-topmost", False)
        state.excel.ensure_sorting_columns()
        attempt_save()
    else:
        state.sorteringsmodus_enabled = False
        sorting_view.hide()
        root.attributes("-topmost", True)
        root.lift()
        root.focus_force()


def _on_sorting_view_closed_by_user() -> None:
    sorting_var.set(False)
    state.sorteringsmodus_enabled = False
    root.attributes("-topmost", True)
    root.lift()
    root.focus_force()


def open_settings() -> None:
    def on_save(new_settings):
        state.settings = new_settings
        settings_module.save(state.settings)

    open_settings_dialog(root, state.settings, on_save)


def update_result_window(text: str, color: str = "black") -> None:
    if result_label is not None:
        result_label.configure(text=text, text_color=color)
    else:
        print(f"Resultat: {text}")


def _persist_settings(_settings: dict | None = None) -> None:
    # SortingView kaller denne med sine (samme objekt som state.settings) som
    # argument; _on_main_configure/_persist_main_geometry kaller den uten.
    settings_module.save(state.settings)


def _on_main_configure(event) -> None:
    if event.widget is not root:
        return
    if state.window_geo_after_id is not None:
        root.after_cancel(state.window_geo_after_id)
    state.window_geo_after_id = root.after(500, _persist_main_geometry)


def _persist_main_geometry() -> None:
    state.window_geo_after_id = None
    match = _GEOMETRY_RE.match(root.geometry())
    if not match:
        return
    w, h, x, y = map(int, match.groups())
    state.settings["window_geometry"]["normal"] = {"width": w, "height": h, "x": x, "y": y}
    _persist_settings()


def run_setup_wizard() -> bool:
    print("[oppsett] Velger kodeformat...")
    code_format = setup_wizard.select_code_format(root)
    if not code_format:
        print("[oppsett] Avbrutt: ingen kodeformat valgt.")
        return False
    state.code_format = code_format
    print(f"[oppsett] Kodeformat: {code_format}")

    filepath = setup_wizard.select_excel_file(root)
    if not filepath:
        print("[oppsett] Avbrutt: ingen fil valgt.")
        return False
    print(f"[oppsett] Fil valgt: {filepath}")

    try:
        state.excel = excel_io.ExcelSession(filepath)
    except excel_io.UnsupportedFileType as e:
        messagebox.showerror("Feil filtype", str(e))
        return False
    except Exception as e:
        traceback.print_exc()
        messagebox.showerror("Feil ved lesing av fil", str(e))
        return False
    print(f"[oppsett] Fil lastet, kolonner: {state.excel.column_names()}")

    column_names = state.excel.column_names()

    producer_column = setup_wizard.select_producer_column(root, column_names)
    if not producer_column:
        print("[oppsett] Avbrutt: ingen produsentkolonne valgt.")
        return False
    state.excel.select_producer_column(producer_column)
    print(f"[oppsett] Produsentkolonne: {producer_column}")

    analysis_columns = setup_wizard.select_analysis_columns(root, column_names, producer_column)
    state.excel.select_analysis_columns(analysis_columns)
    print(f"[oppsett] Analysekolonner: {analysis_columns}")

    sorting_column = setup_wizard.select_sorting_column(root, column_names, producer_column)
    state.excel.select_sorting_column(sorting_column)
    print(f"[oppsett] Sorteringsparameter-kolonne: {sorting_column}")

    state.settings["last_excel_path"] = filepath
    state.settings["last_code_format"] = code_format
    _persist_settings()

    print("[oppsett] Ferdig, starter hovedvindu...")
    return True


def setup_gui() -> None:
    global root, result_label, duplicate_check_var, sorting_var, sorting_view, main_save_status_label

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("green")

    root = ctk.CTk()
    root.title("Tankmelk Scanner")
    root.attributes("-topmost", True)

    geo = state.settings["window_geometry"]["normal"]
    if geo.get("x") is not None and geo.get("y") is not None:
        root.geometry(f"{geo['width']}x{geo['height']}+{geo['x']}+{geo['y']}")
    else:
        window_width, window_height = geo["width"], geo["height"]
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        center_x = int(screen_width / 2 - window_width / 2)
        center_y = int(screen_height / 2 - window_height / 2)
        root.geometry(f"{window_width}x{window_height}+{center_x}+{center_y}")

    control_frame = ctk.CTkFrame(root)
    control_frame.pack(fill="x", padx=10, pady=10)

    duplicate_check_var = ctk.BooleanVar(value=True)
    ctk.CTkCheckBox(
        control_frame, text="Duplikatkontroll aktivert", variable=duplicate_check_var,
        command=toggle_duplicate_check, font=ctk.CTkFont(size=14, weight="bold"),
    ).pack(side="left", padx=10, pady=8)

    sorting_var = ctk.BooleanVar(value=False)
    ctk.CTkCheckBox(
        control_frame, text="Sorteringsmodus", variable=sorting_var,
        command=toggle_sorteringsmodus, font=ctk.CTkFont(size=14, weight="bold"),
    ).pack(side="left", padx=10, pady=8)

    ctk.CTkButton(control_frame, text="Innstillinger", command=open_settings, width=110).pack(
        side="right", padx=10, pady=8
    )

    result_label = ctk.CTkLabel(
        root, text="Vennligst velg Excel-fil...", font=ctk.CTkFont(size=28, weight="bold"),
        wraplength=550, justify="center",
    )
    result_label.pack(expand=True, fill="both", padx=20, pady=20)

    main_save_status_label = ctk.CTkLabel(
        root, text="", font=ctk.CTkFont(size=13, weight="bold"), text_color="#e74c3c",
    )
    main_save_status_label.pack(side="bottom", pady=(0, 8))

    root.withdraw()

    try:
        wizard_ok = run_setup_wizard()
    except Exception:
        traceback.print_exc()
        messagebox.showerror(
            "Uventet feil under oppsett",
            "Noe gikk galt under oppsettet. Se detaljer i konsoll-vinduet.",
        )
        root.destroy()
        return

    if wizard_ok:
        if not os.path.exists(DUPLICATE_FILE):
            with open(DUPLICATE_FILE, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(["ScannetKode", "Tidspunkt"])

        sorting_view = SortingView(
            root, state.settings, _persist_settings, _on_sorting_view_closed_by_user, attempt_save,
        )

        root.deiconify()
        # Etter en lengre withdraw()/Toplevel-sekvens (oppsett-wizarden) blir
        # hovedvinduet noen ganger stående usynlig/bak andre vinduer på Windows
        # med mindre vi eksplisitt løfter det og re-setter topmost.
        root.attributes("-topmost", True)
        root.lift()
        root.focus_force()
        root.update()
        root.bind("<Configure>", _on_main_configure)
        format_text = "Datamatrix (34 tegn)" if state.code_format == "datamatrix" else "Strekkode (10 siffer)"
        update_result_window(f"Klar for skanning!\n\nFormat: {format_text}", "blue")
        print("[hovedvindu] Vist og klart.")

        listener_thread = threading.Thread(target=start_keyboard_listener, daemon=True)
        listener_thread.start()

        root.mainloop()
    else:
        root.destroy()


if __name__ == "__main__":
    setup_gui()
