"""Oppsett-dialogene som kjøres i rekkefølge ved oppstart: kodeformat, Excel-fil,
produsentkolonne, analysekolonner, og (valgfritt) sorteringsparameter-kolonne.
"""

import customtkinter as ctk
from tkinter import filedialog, messagebox


def _bring_to_front(dialog) -> None:
    """Windows lar av og til en ny Toplevel havne usynlig/bak andre vinduer,
    spesielt etter at flere -topmost-vinduer er åpnet/lukket i rekkefølge --
    appen ser da ut til å henge fordi den venter på en dialog ingen ser."""
    dialog.update_idletasks()
    dialog.lift()
    dialog.focus_force()


def select_code_format(root) -> str | None:
    dialog = ctk.CTkToplevel(root)
    dialog.title("Velg kodeformat")
    dialog.attributes("-topmost", True)
    dialog.geometry("420x220")
    dialog.grab_set()

    result = {"value": None}

    ctk.CTkLabel(
        dialog, text="Velg hvilket kodeformat som skal skannes:",
        font=ctk.CTkFont(size=15, weight="bold"), wraplength=380,
    ).pack(pady=20)

    format_var = ctk.StringVar()
    ctk.CTkRadioButton(
        dialog, text="Strekkode (10 siffer)", variable=format_var, value="strekkode",
        font=ctk.CTkFont(size=14),
    ).pack(pady=6)
    ctk.CTkRadioButton(
        dialog, text="Datamatrix (34 tegn)", variable=format_var, value="datamatrix",
        font=ctk.CTkFont(size=14),
    ).pack(pady=6)

    def confirm():
        if format_var.get():
            result["value"] = format_var.get()
            dialog.destroy()
        else:
            messagebox.showwarning("Ingen valg", "Vennligst velg et kodeformat!")

    ctk.CTkButton(
        dialog, text="Bekreft", command=confirm, font=ctk.CTkFont(size=14, weight="bold"),
    ).pack(pady=15)

    _bring_to_front(dialog)
    dialog.wait_window()
    return result["value"]


def select_excel_file(root) -> str | None:
    filepath = filedialog.askopenfilename(
        title="Velg Excel-fil for kryssjekking",
        filetypes=[("Excel Files", "*.xlsx *.xlsm")],
    )
    return filepath or None


def _select_single_column(root, title: str, prompt: str, column_names: list[str],
                           allow_skip: bool = False) -> str | None:
    dialog = ctk.CTkToplevel(root)
    dialog.title(title)
    dialog.attributes("-topmost", True)
    dialog.geometry("420x520")
    dialog.grab_set()

    result = {"value": None, "confirmed": False}

    ctk.CTkLabel(
        dialog, text=prompt, font=ctk.CTkFont(size=14, weight="bold"), wraplength=380,
    ).pack(pady=10)

    scroll = ctk.CTkScrollableFrame(dialog, width=360, height=340)
    scroll.pack(padx=10, pady=10, fill="both", expand=True)

    selected = ctk.StringVar()
    for name in column_names:
        ctk.CTkRadioButton(
            scroll, text=name, variable=selected, value=name, font=ctk.CTkFont(size=13),
        ).pack(anchor="w", padx=10, pady=4)

    def confirm():
        if selected.get():
            result["value"] = selected.get()
            result["confirmed"] = True
            dialog.destroy()
        else:
            messagebox.showwarning("Ingen valg", "Vennligst velg en kolonne!")

    def skip():
        result["value"] = None
        result["confirmed"] = True
        dialog.destroy()

    button_row = ctk.CTkFrame(dialog, fg_color="transparent")
    button_row.pack(pady=10)
    ctk.CTkButton(
        button_row, text="Bekreft", command=confirm, font=ctk.CTkFont(size=14, weight="bold"),
    ).pack(side="left", padx=6)
    if allow_skip:
        ctk.CTkButton(
            button_row, text="Hopp over", command=skip, fg_color="gray40",
            font=ctk.CTkFont(size=14),
        ).pack(side="left", padx=6)

    _bring_to_front(dialog)
    dialog.wait_window()
    if not result["confirmed"]:
        return None
    return result["value"]


def select_producer_column(root, column_names: list[str]) -> str | None:
    return _select_single_column(
        root, "Velg produsentkolonne",
        "Velg kolonnen som inneholder produsent/prøvenummer:",
        column_names, allow_skip=False,
    )


def select_analysis_columns(root, column_names: list[str], producer_column: str) -> list[str]:
    dialog = ctk.CTkToplevel(root)
    dialog.title("Velg analysekolonner")
    dialog.attributes("-topmost", True)
    dialog.geometry("420x520")
    dialog.grab_set()

    result = {"value": []}

    ctk.CTkLabel(
        dialog, text="Velg kolonner som inneholder analyseinformasjon:",
        font=ctk.CTkFont(size=14, weight="bold"), wraplength=380,
    ).pack(pady=10)

    scroll = ctk.CTkScrollableFrame(dialog, width=360, height=340)
    scroll.pack(padx=10, pady=10, fill="both", expand=True)

    check_vars = {}
    for name in column_names:
        if name == producer_column:
            continue
        var = ctk.BooleanVar()
        check_vars[name] = var
        ctk.CTkCheckBox(scroll, text=name, variable=var, font=ctk.CTkFont(size=13)).pack(
            anchor="w", padx=10, pady=4
        )

    def confirm():
        result["value"] = [name for name, var in check_vars.items() if var.get()]
        dialog.destroy()

    ctk.CTkButton(
        dialog, text="Bekreft valg", command=confirm, font=ctk.CTkFont(size=14, weight="bold"),
    ).pack(pady=10)

    _bring_to_front(dialog)
    dialog.wait_window()
    return result["value"]


def select_sorting_column(root, column_names: list[str], producer_column: str) -> str | None:
    candidates = [name for name in column_names if name != producer_column]
    return _select_single_column(
        root, "Velg sorteringsparameter-kolonne",
        "Velg kolonnen som inneholder sorteringsparameter (verdier 1-15).\n"
        "Kun nødvendig hvis du planlegger å bruke Sorteringsmodus denne økten "
        "-- trykk 'Hopp over' ellers.",
        candidates, allow_skip=True,
    )
