# Synthetic German fixture only; never captures a real microphone.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$fixtureRoot = Split-Path -Parent $PSScriptRoot
$fixtureDirectory = Join-Path $fixtureRoot '.local'
New-Item -ItemType Directory -Force $fixtureDirectory | Out-Null
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $synth.SelectVoice('Microsoft Hedda Desktop')
    $format = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
    $synth.SetOutputToWaveFile((Join-Path $fixtureDirectory 'fictional-founder.wav'), $format)
    $synth.Speak('Unser Startup heißt Solar. Wir entwickeln Software für kleine Unternehmen. Unser Produkt hilft, den Energieverbrauch zu senken.')
} finally { $synth.Dispose() }
Push-Location $fixtureRoot
try {
@'
import wave
with wave.open('.local/fictional-founder.wav','rb') as source:
    params=source.getparams(); data=source.readframes(source.getnframes())
with wave.open('.local/browser-microphone.wav','wb') as target:
    target.setparams(params)
    silence=params.framerate*params.nchannels*params.sampwidth
    target.writeframes(bytes(silence*12)+data+bytes(silence*55))
'@ | & (Join-Path $fixtureRoot '.venv/Scripts/python.exe') -
} finally { Pop-Location }
