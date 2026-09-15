# Tankmelk Scanner

Leser strekkode-/Datamatrix-skanninger (skanneren fungerer som et vanlig
tastatur) og slår dem opp mot en Excel-liste. Har to modi:

- **Uttaksmodus** (standard): slår opp produsentnummer og viser hvilke
  analyser som skal kjøres, med duplikatvarsel og automatisk kopiering til
  utklippstavlen.
- **Sorteringsmodus** (valgfri, alltid AV ved oppstart): brukes til fysisk
  sortering av innkommende prøver i baner 1-15, med stor tallvisning og
  talte lydvarsler.

## 1. Installer Python

Programmet krever **Python 3.11 eller nyere**.

1. Last ned Python fra [python.org/downloads](https://www.python.org/downloads/).
2. Kjør installasjonsprogrammet. Huk av for **"Add python.exe to PATH"** på
   første skjermbilde før du klikker Install.
3. Sjekk at installasjonen fungerer ved å åpne en terminal (PowerShell) og
   skrive:

   ```
   python --version
   ```

   Dette skal skrive ut noe sånt som `Python 3.12.4`.

## 2. Installer avhengigheter

Åpne en terminal i prosjektmappen (der `Tankmelkprodnummerdisplay.py`
ligger) og kjør:

```
pip install -r requirements.txt
```

Dette installerer `customtkinter`, `openpyxl` og `pynput`.

## 3. (Valgfritt) Generer talte lydvarsler

Sorteringsmodus spiller av talte tall (1-15) og varsler
("Ikke i uttaksliste", "Mottatt duplikat"). Disse lydfilene må genereres én
gang per maskin (kjøres automatisk med Windows' innebygde talesyntese,
ingen ekstra avhengigheter):

```
powershell -ExecutionPolicy Bypass -File tools\generate_voice_cues.ps1
```

Filene lagres i `%APPDATA%\TankmelkScanner\voice_cues\`. Mangler filene,
fungerer resten av programmet fortsatt normalt (bare uten lyd).

## 4. Kjør programmet

```
python Tankmelkprodnummerdisplay.py
```

### Førstegangsoppsett

Ved oppstart vises en oppsettsveiviser der du velger:

1. **Kodeformat** — Datamatrix (34 tegn) eller strekkode (10 siffer),
   avhengig av hva skanneren din leser.
2. **Excel-fil** — filen med produsentlisten (`.xlsx`/`.xlsm`).
3. **Produsentkolonne** — kolonnen som inneholder produsentnummeret det
   skal slås opp mot.
4. **Analysekolonner** — kolonnene som viser hvilke analyser som skal
   kjøres for en gitt rad.
5. **Sorteringsparameter-kolonne** (valgfri) — kolonnen med bane-nummer
   (1-15), kun nødvendig for sorteringsmodus.

Valgene huskes til neste gang programmet startes.

### Bruk

- Skann en kode med skanneren — resultatet vises automatisk i vinduet, og
  produsentnummeret kopieres til utklippstavlen.
- **Duplikatkontroll aktivert**: varsler (lyd + dialogboks) hvis samme kode
  skannes to ganger, og logger duplikatet til
  `TANKMELK DUPLIKATER.csv`.
- **Sorteringsmodus**: bytt til stor tallvisning for fysisk sortering av
  prøver i baner 1-15. Krever at sorteringsparameter-kolonne er valgt i
  oppsettet.
- **Innstillinger**-knappen: juster volum på lydvarsler m.m.

Excel-fila lagres automatisk til disk etter hver skanning. Er fila åpen i
Excel (låst), vises en advarsel i vinduet, og lagringen forsøkes på nytt
automatisk til den lykkes — ingen skanninger går tapt i mellomtiden.

En sikkerhetskopi av Excel-fila (`<filnavn>.<tidsstempel>.bak.xlsx`) tas
automatisk ved første lagring i en økt.
