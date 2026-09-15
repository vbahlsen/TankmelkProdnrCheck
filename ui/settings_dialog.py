"""Innstillingsdialog: volum for lydvarsler, med testknapp.

Tempo/hastighet finnes bevisst ikke her -- cue'ene er ferdig innspilte lydfiler
med fast tempo (se audio.py / tools/generate_voice_cues.ps1), så justerbar
talehastighet gir ikke mening lenger.
"""

import customtkinter as ctk

import audio


def open_settings_dialog(root, app_settings: dict, on_save) -> None:
    dialog = ctk.CTkToplevel(root)
    dialog.title("Innstillinger")
    dialog.attributes("-topmost", True)
    dialog.geometry("420x260")
    dialog.grab_set()

    volume_var = ctk.DoubleVar(value=app_settings.get("volume", 0.8))

    ctk.CTkLabel(
        dialog, text="Volum for lydvarsler", font=ctk.CTkFont(size=15, weight="bold"),
    ).pack(pady=(20, 5))

    value_label = ctk.CTkLabel(dialog, text=f"{int(volume_var.get() * 100)} %", font=ctk.CTkFont(size=13))
    value_label.pack()

    def on_slide(value):
        value_label.configure(text=f"{int(float(value) * 100)} %")

    ctk.CTkSlider(
        dialog, from_=0.0, to=1.0, variable=volume_var, command=on_slide, width=300,
    ).pack(pady=10)

    missing = audio.missing_cue_files()
    if missing:
        ctk.CTkLabel(
            dialog,
            text=f"OBS: {len(missing)} lydfil(er) mangler. Kjør "
            "tools/generate_voice_cues.ps1 på nytt.",
            font=ctk.CTkFont(size=12), text_color="#e74c3c", wraplength=380,
        ).pack(pady=5)

    def test_sound():
        audio.play_test(volume_var.get())

    def save_and_close():
        app_settings["volume"] = volume_var.get()
        on_save(app_settings)
        dialog.destroy()

    button_row = ctk.CTkFrame(dialog, fg_color="transparent")
    button_row.pack(pady=15)
    ctk.CTkButton(button_row, text="Test", command=test_sound, font=ctk.CTkFont(size=13)).pack(
        side="left", padx=6
    )
    ctk.CTkButton(
        button_row, text="Lagre", command=save_and_close, font=ctk.CTkFont(size=13, weight="bold"),
    ).pack(side="left", padx=6)
