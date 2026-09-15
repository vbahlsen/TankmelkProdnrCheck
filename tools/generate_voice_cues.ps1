<#
.SYNOPSIS
    Genererer de 17 faste lydvarslene ("1".."15", "ikke_i_uttaksliste", "mottatt_duplikat")
    som .wav-filer med en norsk stemme, til bruk i Tankmelk Scanner.

.DESCRIPTION
    Kjøres én gang per maskin (eller på nytt hvis lydfilene mangler/skal fornyes).
    Bruker Windows' nyere WinRT-talesyntese (Windows.Media.SpeechSynthesis), som ser
    norske "OneCore"-stemmer -- i motsetning til den eldre SAPI5-motoren
    (System.Speech.Synthesis / pyttsx3), som på denne typen maskin kun fant en engelsk
    stemme. Faller tilbake til SAPI5 hvis WinRT-veien ikke er tilgjengelig.

    Filene lagres i %APPDATA%\TankmelkScanner\voice_cues\<key>.wav
#>

$ErrorActionPreference = "Stop"

$OutDir = Join-Path $env:APPDATA "TankmelkScanner\voice_cues"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$Aa = [char]0x00E5  # "å" -- skrevet som unicode-escape for å unngå encoding-problemer når skriptet leses av PowerShell 5.1

$Cues = [ordered]@{
    "1"  = "en"
    "2"  = "to"
    "3"  = "tre"
    "4"  = "fire"
    "5"  = "fem"
    "6"  = "seks"
    "7"  = "sju"
    "8"  = "${Aa}tte"
    "9"  = "ni"
    "10" = "ti"
    "11" = "elleve"
    "12" = "tolv"
    "13" = "tretten"
    "14" = "fjorten"
    "15" = "femten"
    "ikke_i_uttaksliste" = "Ikke i uttaksliste"
    "mottatt_duplikat"   = "Mottatt duplikat"
}

function Await($WinRtTask, [Type]$ResultType) {
    $asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
        $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    })[0]
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    return $netTask.Result
}

function Try-GenerateWithWinRT {
    try {
        [Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType = WindowsRuntime] | Out-Null
        [Windows.Storage.Streams.DataReader, Windows.Storage.Streams, ContentType = WindowsRuntime] | Out-Null
    } catch {
        Write-Warning "WinRT-talesyntese er ikke tilgjengelig på denne maskinen: $_"
        return $false
    }

    $synth = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer
    $norwegian = $synth.AllVoices | Where-Object { $_.Language -like "nb-NO" -or $_.Language -like "no-NO" -or $_.Language -like "nn-NO" } | Select-Object -First 1

    if (-not $norwegian) {
        Write-Warning "Fant ingen norsk stemme via WinRT (Windows.Media.SpeechSynthesis.AllVoices)."
        return $false
    }

    Write-Host "Bruker WinRT-stemme: $($norwegian.DisplayName) ($($norwegian.Language))"
    $synth.Voice = $norwegian

    foreach ($key in $Cues.Keys) {
        $text = $Cues[$key]
        $outPath = Join-Path $OutDir "$key.wav"
        Write-Host "  -> $key.wav  ('$text')"

        $stream = Await ($synth.SynthesizeTextToStreamAsync($text)) ([Windows.Media.SpeechSynthesis.SpeechSynthesisStream])

        $reader = New-Object Windows.Storage.Streams.DataReader($stream)
        Await ($reader.LoadAsync([uint32]$stream.Size)) ([uint32]) | Out-Null
        $bytes = New-Object byte[] ($stream.Size)
        $reader.ReadBytes($bytes)

        [System.IO.File]::WriteAllBytes($outPath, $bytes)
        $reader.Dispose()
        $stream.Dispose()
    }

    $synth.Dispose()
    return $true
}

function Generate-WithSAPI5Fallback {
    Add-Type -AssemblyName System.Speech
    $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
    $voice = $synth.GetInstalledVoices() | Where-Object {
        $_.VoiceInfo.Culture.Name -like "nb-NO" -or $_.VoiceInfo.Culture.Name -like "no-NO"
    } | Select-Object -First 1

    if ($voice) {
        $synth.SelectVoice($voice.VoiceInfo.Name)
        Write-Host "Bruker SAPI5-stemme: $($voice.VoiceInfo.Name)"
    } else {
        Write-Warning "Ingen norsk SAPI5-stemme funnet heller. Bruker standardstemme (sannsynligvis engelsk uttale av norsk tekst)."
    }

    foreach ($key in $Cues.Keys) {
        $text = $Cues[$key]
        $outPath = Join-Path $OutDir "$key.wav"
        Write-Host "  -> $key.wav  ('$text')"
        $synth.SetOutputToWaveFile($outPath)
        $synth.Speak($text)
        $synth.SetOutputToNull()
    }
    $synth.Dispose()
}

Write-Host "Genererer lydvarsler til: $OutDir"

if (-not (Try-GenerateWithWinRT)) {
    Write-Host "Faller tilbake til eldre SAPI5-motor (System.Speech)..."
    Generate-WithSAPI5Fallback
}

Write-Host "Ferdig. $($Cues.Count) lydfiler generert i $OutDir"
