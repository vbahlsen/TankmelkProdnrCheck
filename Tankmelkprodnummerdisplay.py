import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox
from pynput import keyboard
import threading
import time
import csv
import os
from datetime import datetime

# --- Globale variabler ---
INPUT_BUFFER = ""
LAST_KEY_TIME = time.time()
CSV_DATA = None
CSV_COLUMN_NAME = None
SCANNED_CODES = set()
DUPLICATE_FILE = "TANKMELK 2025 DUPLIKATER.csv"

# --- Kjernefunksjoner ---

def select_csv_file():
    """Åpner en filvelger for å la brukeren velge en .csv-fil."""
    global CSV_DATA, CSV_COLUMN_NAME
    filepath = filedialog.askopenfilename(
        title="Velg CSV-fil for kryssjekking",
        filetypes=[("CSV Files", "*.csv")]
    )
    if not filepath:
        update_result_window("Avsluttet: Ingen fil valgt.", "red")
        root.after(2000, root.destroy) # Lukk programmet hvis ingen fil er valgt
        return False

    try:
        # Leser CSV-filen og sikrer at kodene behandles som tekst
        CSV_DATA = pd.read_csv(filepath, dtype=str, header=0)
        CSV_COLUMN_NAME = CSV_DATA.columns[0] # Antar at koden er i første kolonne
        update_result_window(f"Fil lastet!\nKlar for scanning...", "blue")
        return True
    except Exception as e:
        update_result_window(f"Feil ved lesing av fil:\n{e}", "red")
        return False

def process_scanned_code(scanned_code):
    """Behandler den skannede koden og kryssjekker mot CSV-data."""
    # 1. Sjekk for duplikater
    if scanned_code in SCANNED_CODES:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(DUPLICATE_FILE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([scanned_code, timestamp])
        messagebox.showwarning("Duplikat funnet!", f"Koden:\n{scanned_code}\nhar allerede blitt skannet!")
        return

    SCANNED_CODES.add(scanned_code)

    # 2. Hent ut søkestrengen (siffer 2-9)
    if len(scanned_code) >= 9:
        search_str = scanned_code[1:9]
    else:
        update_result_window("FEIL: Koden er for kort", "red")
        return

    # 3. Søk i CSV-filen
    try:
        match = CSV_DATA[CSV_DATA[CSV_COLUMN_NAME].str.startswith(search_str, na=False)]
        
        if not match.empty:
            found_code = match.iloc[0][CSV_COLUMN_NAME]
            
            # NYTT: Kopier den funnede koden til utklippstavlen
            root.clipboard_clear()
            root.clipboard_append(found_code)
            
            update_result_window(found_code, "green")
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
        if len(INPUT_BUFFER) == 36:
            root.after(0, process_scanned_code, INPUT_BUFFER)
        INPUT_BUFFER = ""
    elif hasattr(key, 'char') and key.char:
        INPUT_BUFFER += key.char

def start_keyboard_listener():
    """Starter lytteren i en egen tråd."""
    with keyboard.Listener(on_release=on_key_release) as listener:
        listener.join()

# --- GUI-oppsett (Tkinter) ---

def setup_gui():
    """Setter opp hovedvinduet for resultater."""
    global root, result_label
    root = tk.Tk()
    root.title("Resultatvisning")
    root.attributes("-topmost", True)
    
    window_width = 600
    window_height = 300
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    center_x = int(screen_width/2 - window_width / 2)
    center_y = int(screen_height/2 - window_height / 2)
    root.geometry(f'{window_width}x{screen_height}+{center_x}+{center_y}')

    result_label = tk.Label(root, text="Vennligst velg CSV-fil...", font=("Helvetica", 40, "bold"), wraplength=550)
    result_label.pack(expand=True, fill="both", padx=20, pady=20)
    
    root.withdraw()

    if select_csv_file():
        if not os.path.exists(DUPLICATE_FILE):
            with open(DUPLICATE_FILE, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["ScannetKode", "Tidspunkt"])
        
        root.deiconify()
        listener_thread = threading.Thread(target=start_keyboard_listener, daemon=True)
        listener_thread.start()
        root.mainloop()

def update_result_window(text, color="black"):
    """Oppdaterer teksten og fargen i resultatvinduet."""
    if 'label' in globals():
        result_label.config(text=text, fg=color)
    else:
        print(f"Resultat: {text}")

# --- Start scriptet ---
if __name__ == "__main__":
    setup_gui()
