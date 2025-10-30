import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pynput import keyboard
import threading
import time
import csv
import os
from datetime import datetime

# --- Globale variabler ---
INPUT_BUFFER = ""
LAST_KEY_TIME = time.time()
EXCEL_DATA = None
PRODUCER_COLUMN = None
ANALYSIS_COLUMNS = []
SCANNED_CODES = set()
DUPLICATE_FILE = "TANKMELK 2025 DUPLIKATER.csv"
DUPLICATE_CHECK_ENABLED = True
CODE_FORMAT = None  # "strekkode" (10 siffer) eller "datamatrix" (36 tegn)

# --- Kjernefunksjoner ---

def select_excel_file():
    """Åpner en filvelger for å la brukeren velge en Excel-fil."""
    global EXCEL_DATA
    filepath = filedialog.askopenfilename(
        title="Velg Excel-fil for kryssjekking",
        filetypes=[("Excel Files", "*.xlsx *.xls")]
    )
    if not filepath:
        update_result_window("Avsluttet: Ingen fil valgt.", "red")
        root.after(2000, root.destroy)
        return False

    try:
        # Leser Excel-filen og sikrer at kodene behandles som tekst
        EXCEL_DATA = pd.read_excel(filepath, dtype=str, header=0)
        update_result_window(f"Fil lastet!\nVelger kolonner...", "blue")
        return True
    except Exception as e:
        update_result_window(f"Feil ved lesing av fil:\n{e}", "red")
        return False

def select_code_format():
    """Lar brukeren velge kodeformat."""
    global CODE_FORMAT
    
    format_dialog = tk.Toplevel(root)
    format_dialog.title("Velg kodeformat")
    format_dialog.attributes("-topmost", True)
    format_dialog.geometry("400x200")
    
    tk.Label(format_dialog, text="Velg hvilket kodeformat som skal skannes:", 
             font=("Helvetica", 11, "bold"), wraplength=350).pack(pady=20)
    
    format_var = tk.StringVar()
    
    tk.Radiobutton(format_dialog, text="Strekkode (10 siffer)", 
                   variable=format_var, value="strekkode", 
                   font=("Helvetica", 10)).pack(pady=5)
    tk.Radiobutton(format_dialog, text="Datamatrix (34 tegn)", 
                   variable=format_var, value="datamatrix", 
                   font=("Helvetica", 10)).pack(pady=5)
    
    def confirm_format():
        global CODE_FORMAT
        if format_var.get():
            CODE_FORMAT = format_var.get()
            format_dialog.destroy()
        else:
            messagebox.showwarning("Ingen valg", "Vennligst velg et kodeformat!")
    
    tk.Button(format_dialog, text="Bekreft", command=confirm_format, 
              font=("Helvetica", 10, "bold"), bg="#4CAF50", fg="white").pack(pady=15)
    
    format_dialog.wait_window()
    
    return CODE_FORMAT is not None

def select_columns():
    """Lar brukeren velge produsentkolonne og analysekolonner."""
    global PRODUCER_COLUMN, ANALYSIS_COLUMNS
    
    if EXCEL_DATA is None:
        return False
    
    column_names = list(EXCEL_DATA.columns)
    
    # Dialog for å velge produsentkolonne
    producer_dialog = tk.Toplevel(root)
    producer_dialog.title("Velg produsentkolonne")
    producer_dialog.attributes("-topmost", True)
    producer_dialog.geometry("400x500")
    
    tk.Label(producer_dialog, text="Velg kolonnen som inneholder produsent/prøvenummer:", 
             font=("Helvetica", 10, "bold"), wraplength=350).pack(pady=10)
    
    producer_var = tk.StringVar()
    producer_listbox = tk.Listbox(producer_dialog, height=15)
    producer_listbox.pack(padx=10, pady=10, fill="both", expand=True)
    
    for col in column_names:
        producer_listbox.insert(tk.END, col)
    
    def confirm_producer():
        selection = producer_listbox.curselection()
        if selection:
            producer_var.set(column_names[selection[0]])
            producer_dialog.destroy()
        else:
            messagebox.showwarning("Ingen valg", "Vennligst velg en kolonne!")
    
    tk.Button(producer_dialog, text="Bekreft", command=confirm_producer, 
              font=("Helvetica", 10, "bold")).pack(pady=10)
    
    producer_dialog.wait_window()
    
    if not producer_var.get():
        return False
    
    PRODUCER_COLUMN = producer_var.get()
    
    # Dialog for å velge analysekolonner
    analysis_dialog = tk.Toplevel(root)
    analysis_dialog.title("Velg analysekolonner")
    analysis_dialog.attributes("-topmost", True)
    analysis_dialog.geometry("400x500")
    
    tk.Label(analysis_dialog, text="Velg kolonner som inneholder analyseinformasjon:", 
             font=("Helvetica", 10, "bold"), wraplength=350).pack(pady=10)
    
    # Frame for scrollbar og checkboxes
    list_frame = tk.Frame(analysis_dialog)
    list_frame.pack(fill="both", expand=True, padx=10, pady=5)
    
    # Scrollbar og canvas for checkboxes
    canvas = tk.Canvas(list_frame)
    scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
    scrollable_frame = tk.Frame(canvas)
    
    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    
    check_vars = {}
    for col in column_names:
        if col != PRODUCER_COLUMN:
            var = tk.BooleanVar()
            check_vars[col] = var
            tk.Checkbutton(scrollable_frame, text=col, variable=var, 
                          font=("Helvetica", 9)).pack(anchor="w", padx=20, pady=2)
    
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    
    # Bekreft-knapp nederst
    def confirm_analysis():
        ANALYSIS_COLUMNS.clear()
        for col, var in check_vars.items():
            if var.get():
                ANALYSIS_COLUMNS.append(col)
        analysis_dialog.destroy()
    
    tk.Button(analysis_dialog, text="Bekreft valg", command=confirm_analysis, 
              font=("Helvetica", 10, "bold"), bg="#4CAF50", fg="white").pack(pady=10)
    
    analysis_dialog.wait_window()
    
    return True

def process_scanned_code(scanned_code):
    """Behandler den skannede koden og kryssjekker mot Excel-data."""
    global DUPLICATE_CHECK_ENABLED
    
    # 1. Sjekk for duplikater (hvis aktivert)
    if DUPLICATE_CHECK_ENABLED and scanned_code in SCANNED_CODES:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(DUPLICATE_FILE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([scanned_code, timestamp])
        messagebox.showwarning("Duplikat funnet!", f"Koden:\n{scanned_code}\nhar allerede blitt skannet!")
        return

    SCANNED_CODES.add(scanned_code)

    # 2. Hent ut søkestrengen basert på valgt format
    if CODE_FORMAT == "datamatrix":
        if len(scanned_code) == 34:
            # Datamatrix: 34 tegn, søk på posisjon 1-8 (tegn 2-9)
            # Format: 5111904530127082512110442044108000
            # Søker på: 11190453
            search_str = scanned_code[1:9]
        else:
            update_result_window(f"FEIL: Forventet 34 tegn (Datamatrix)\nMottok: {len(scanned_code)} tegn", "red")
            return
    elif CODE_FORMAT == "strekkode":
        if len(scanned_code) == 10:
            # Strekkode: 10 siffer, søk på posisjon 0-7 (tegn 1-8)
            search_str = scanned_code[0:8]
        else:
            update_result_window(f"FEIL: Forventet 10 siffer (Strekkode)\nMottok: {len(scanned_code)} tegn", "red")
            return
    else:
        update_result_window("FEIL: Kodeformat ikke valgt", "red")
        return

    # 3. Søk i Excel-filen
    try:
        match = EXCEL_DATA[EXCEL_DATA[PRODUCER_COLUMN].str.startswith(search_str, na=False)]
        
        if not match.empty:
            found_code = match.iloc[0][PRODUCER_COLUMN]
            
            # Kopier den funnede koden til utklippstavlen
            root.clipboard_clear()
            root.clipboard_append(found_code)
            
            # Finn hvilke analyser som skal utføres
            row_data = match.iloc[0]
            analyses_to_perform = []
            
            for col in ANALYSIS_COLUMNS:
                cell_value = row_data[col]
                # Sjekk om cellen ikke er tom (NaN, None, eller tom streng)
                if pd.notna(cell_value) and str(cell_value).strip():
                    analyses_to_perform.append(col)
            
            # Bygg resultatvisning
            result_text = found_code
            if analyses_to_perform:
                result_text += "\n\n--- ANALYSER ---\n" + "\n".join(f"• {analysis}" for analysis in analyses_to_perform)
            
            update_result_window(result_text, "green")
        else:
            update_result_window("IKKE I UTTAKSLISTEN", "red")
            
    except Exception as e:
        update_result_window(f"Søkefeil:\n{e}", "red")


# --- Håndtering av tastatur-input ---

def on_key_release(key):
    """Funksjon som kalles hver gang en tast slippes."""
    global INPUT_BUFFER, LAST_KEY_TIME

    current_time = time.time()
    time_diff = current_time - LAST_KEY_TIME
    LAST_KEY_TIME = current_time

    if time_diff > 0.2 and INPUT_BUFFER:
        INPUT_BUFFER = ""

    if key == keyboard.Key.enter:
        # Behandle koden basert på valgt format
        if CODE_FORMAT == "datamatrix" and len(INPUT_BUFFER) == 34:
            root.after(0, process_scanned_code, INPUT_BUFFER)
        elif CODE_FORMAT == "strekkode" and len(INPUT_BUFFER) == 10:
            root.after(0, process_scanned_code, INPUT_BUFFER)
        elif INPUT_BUFFER:
            # Feil lengde for valgt format
            expected = "34 tegn" if CODE_FORMAT == "datamatrix" else "10 siffer"
            root.after(0, update_result_window, 
                      f"FEIL: Forventet {expected}\nMottok: {len(INPUT_BUFFER)} tegn", "red")
        INPUT_BUFFER = ""
    elif hasattr(key, 'char') and key.char:
        INPUT_BUFFER += key.char

def start_keyboard_listener():
    """Starter lytteren i en egen tråd."""
    with keyboard.Listener(on_release=on_key_release) as listener:
        listener.join()

# --- GUI-oppsett (Tkinter) ---

def toggle_duplicate_check():
    """Slår duplikatkontroll av/på."""
    global DUPLICATE_CHECK_ENABLED
    DUPLICATE_CHECK_ENABLED = duplicate_check_var.get()

def setup_gui():
    """Setter opp hovedvinduet for resultater."""
    global root, result_label, duplicate_check_var
    root = tk.Tk()
    root.title("Tankmelk Scanner")
    root.attributes("-topmost", True)
    
    window_width = 600
    window_height = 400
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    center_x = int(screen_width/2 - window_width / 2)
    center_y = int(screen_height/2 - window_height / 2)
    root.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')

    # Ramme for checkbox øverst
    control_frame = tk.Frame(root, bg="#f0f0f0", relief="ridge", borderwidth=2)
    control_frame.pack(fill="x", padx=10, pady=10)
    
    duplicate_check_var = tk.BooleanVar(value=True)
    duplicate_checkbox = tk.Checkbutton(
        control_frame, 
        text="Duplikatkontroll aktivert", 
        variable=duplicate_check_var,
        command=toggle_duplicate_check,
        font=("Helvetica", 11, "bold"),
        bg="#f0f0f0"
    )
    duplicate_checkbox.pack(pady=5)

    # Resultatområde
    result_label = tk.Label(root, text="Vennligst velg Excel-fil...", 
                           font=("Helvetica", 28, "bold"), wraplength=550,
                           justify="center")
    result_label.pack(expand=True, fill="both", padx=20, pady=20)
    
    root.withdraw()

    if select_code_format() and select_excel_file() and select_columns():
        if not os.path.exists(DUPLICATE_FILE):
            with open(DUPLICATE_FILE, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["ScannetKode", "Tidspunkt"])
        
        root.deiconify()
        format_text = "Datamatrix (34 tegn)" if CODE_FORMAT == "datamatrix" else "Strekkode (10 siffer)"
        update_result_window(f"Klar for scanning!\n\nFormat: {format_text}", "blue")
        listener_thread = threading.Thread(target=start_keyboard_listener, daemon=True)
        listener_thread.start()
        root.mainloop()
    else:
        root.destroy()

def update_result_window(text, color="black"):
    """Oppdaterer teksten og fargen i resultatvinduet."""
    if 'result_label' in globals():
        result_label.config(text=text, fg=color)
    else:
        print(f"Resultat: {text}")

# --- Start scriptet ---
if __name__ == "__main__":
    setup_gui()
