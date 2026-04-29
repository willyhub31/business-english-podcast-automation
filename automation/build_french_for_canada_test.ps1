param(
    [string]$OutputRoot = "runs",
    [string]$BackgroundVideo = "video background.mp4"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-WavDurationSeconds {
    param([string]$Path)
    $durationText = & ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 $Path
    return [double]::Parse($durationText.Trim(), [System.Globalization.CultureInfo]::InvariantCulture)
}

function New-SilenceWav {
    param(
        [double]$DurationSeconds,
        [string]$Path
    )

    & ffmpeg -y -f lavfi -i "anullsrc=r=22050:cl=mono" -t $DurationSeconds $Path | Out-Null
}

function New-ShiftedVoiceWav {
    param(
        [string]$InputPath,
        [string]$OutputPath
    )

    & ffmpeg -y -i $InputPath -af "rubberband=pitch=0.78,atempo=1.03" $OutputPath | Out-Null
}

function Invoke-FFmpegChecked {
    param([string[]]$Arguments)
    & ffmpeg @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "ffmpeg failed with exit code $LASTEXITCODE"
    }
}

Add-Type -AssemblyName System.Speech

$root = (Resolve-Path (Get-Location)).Path
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$runDir = Join-Path $root "$OutputRoot\${timestamp}_french_for_canada_test"
$sectionsDir = Join-Path $runDir "segments"
$assetsDir = Join-Path $runDir "assets"
New-Item -ItemType Directory -Force -Path $runDir, $sectionsDir, $assetsDir | Out-Null

$transcript = @(
    [pscustomobject]@{ Speaker = "Sophie"; Text = "Salut Leo, tu as l'air prêt pour Montréal aujourd'hui."; PauseAfter = 0.45 }
    [pscustomobject]@{ Speaker = "Leo"; Text = "Salut Sophie. Oui, aujourd'hui on aide les nouveaux arrivants avec trois phrases vraiment utiles pour le Canada."; PauseAfter = 0.55 }
    [pscustomobject]@{ Speaker = "Sophie"; Text = "Première phrase: je viens d'arriver au Canada. C'est simple, poli, et très naturel."; PauseAfter = 0.5 }
    [pscustomobject]@{ Speaker = "Leo"; Text = "Deuxième phrase: est-ce que vous pouvez parler plus lentement s'il vous plaît? Parfait quand l'accent québécois va un peu trop vite."; PauseAfter = 0.6 }
    [pscustomobject]@{ Speaker = "Sophie"; Text = "Troisième phrase: j'aimerais prendre rendez-vous. Tu peux l'utiliser à la banque, à la clinique, ou pour l'administration."; PauseAfter = 0.65 }
    [pscustomobject]@{ Speaker = "Leo"; Text = "Petit dialogue. Bonjour, je viens d'arriver au Canada et je cherche un appartement."; PauseAfter = 0.4 }
    [pscustomobject]@{ Speaker = "Sophie"; Text = "Très bien. Est-ce que vous pouvez parler plus lentement, s'il vous plaît? Je comprends un peu, mais pas encore tout."; PauseAfter = 0.5 }
    [pscustomobject]@{ Speaker = "Leo"; Text = "Bien sûr. Et si vous voulez visiter, j'aimerais prendre rendez-vous pour demain à quatorze heures."; PauseAfter = 0.65 }
    [pscustomobject]@{ Speaker = "Sophie"; Text = "Tu vois? Ce n'est pas du français parfait de manuel. C'est du français utile pour la vraie vie."; PauseAfter = 0.55 }
    [pscustomobject]@{ Speaker = "Leo"; Text = "Répète avec nous. Je viens d'arriver au Canada."; PauseAfter = 1.0 }
    [pscustomobject]@{ Speaker = "Sophie"; Text = "Est-ce que vous pouvez parler plus lentement, s'il vous plaît?"; PauseAfter = 1.0 }
    [pscustomobject]@{ Speaker = "Leo"; Text = "J'aimerais prendre rendez-vous."; PauseAfter = 0.7 }
    [pscustomobject]@{ Speaker = "Sophie"; Text = "Si tu veux plus de français pour le Canada, on continue avec des scènes de travail, de logement et de vie quotidienne."; PauseAfter = 0.0 }
)

$textTranscriptPath = Join-Path $runDir "french_for_canada_test_transcript.txt"
$transcript | ForEach-Object { "{0}: {1}" -f $_.Speaker, $_.Text } | Set-Content -Path $textTranscriptPath -Encoding UTF8

$speakerVoice = "Microsoft Hortense Desktop"
$culture = [System.Globalization.CultureInfo]::GetCultureInfo("fr-FR")

$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.SelectVoice($speakerVoice)
$synth.Rate = 0
$synth.Volume = 100

$srtEntries = New-Object System.Collections.Generic.List[string]
$concatEntries = New-Object System.Collections.Generic.List[string]
$currentTime = 0.0
$itemIndex = 1

for ($i = 0; $i -lt $transcript.Count; $i++) {
    $entry = $transcript[$i]
    $baseName = "{0:d2}_{1}" -f ($i + 1), $entry.Speaker.ToLower()
    $rawWav = Join-Path $sectionsDir "$baseName.raw.wav"
    $voiceWav = Join-Path $sectionsDir "$baseName.wav"

    $prompt = $entry.Text
    $builder = New-Object System.Text.StringBuilder
    [void]$builder.Append("<speak version='1.0' xml:lang='fr-FR'>")
    [void]$builder.Append("<voice xml:lang='fr-FR' name='$speakerVoice'>")
    [void]$builder.Append([System.Security.SecurityElement]::Escape($prompt))
    [void]$builder.Append("</voice></speak>")
    $ssml = $builder.ToString()

    $synth.SetOutputToWaveFile($rawWav)
    $synth.SpeakSsml($ssml)
    $synth.SetOutputToNull()

    if ($entry.Speaker -eq "Leo") {
        New-ShiftedVoiceWav -InputPath $rawWav -OutputPath $voiceWav
    } else {
        Copy-Item -LiteralPath $rawWav -Destination $voiceWav -Force
    }

    $duration = Get-WavDurationSeconds -Path $voiceWav
    $start = $currentTime
    $end = $start + $duration

    $startTs = [TimeSpan]::FromSeconds($start).ToString("hh\:mm\:ss\,fff")
    $endTs = [TimeSpan]::FromSeconds($end).ToString("hh\:mm\:ss\,fff")
    $subtitleText = $entry.Text -replace "\s+", " "
    $srtEntries.Add("$itemIndex`r`n$startTs --> $endTs`r`n$subtitleText`r`n")
    $itemIndex++

    $concatEntries.Add("file '$($voiceWav.Replace('\','/'))'")
    $currentTime = $end

    if ($entry.PauseAfter -gt 0) {
        $silenceWav = Join-Path $sectionsDir ("{0:d2}_pause.wav" -f ($i + 1))
        New-SilenceWav -DurationSeconds $entry.PauseAfter -Path $silenceWav
        $concatEntries.Add("file '$($silenceWav.Replace('\','/'))'")
        $currentTime += [double]$entry.PauseAfter
    }
}

$srtPath = Join-Path $runDir "french_for_canada_test.srt"
$srtEntries -join "`r`n" | Set-Content -Path $srtPath -Encoding UTF8

$concatPath = Join-Path $runDir "french_for_canada_test.concat.txt"
[System.IO.File]::WriteAllText($concatPath, ($concatEntries -join "`n") + "`n", [System.Text.Encoding]::ASCII)

$wavPath = Join-Path $runDir "french_for_canada_test.wav"
$mp3Path = Join-Path $runDir "french_for_canada_test.mp3"
$videoPath = Join-Path $runDir "french_for_canada_test.mp4"
$framePath = Join-Path $runDir "french_for_canada_test_frame.png"

Invoke-FFmpegChecked -Arguments @("-y", "-f", "concat", "-safe", "0", "-i", $concatPath, "-c", "copy", $wavPath)
Invoke-FFmpegChecked -Arguments @("-y", "-i", $wavPath, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-codec:a", "libmp3lame", "-b:a", "192k", $mp3Path)

$backgroundPath = Join-Path $root $BackgroundVideo
if (Test-Path $backgroundPath) {
    Invoke-FFmpegChecked -Arguments @(
        "-y", "-stream_loop", "-1", "-i", $backgroundPath, "-i", $mp3Path,
        "-vf", "scale=1920:1080,crop=1920:1080,subtitles='$($srtPath.Replace('\','/').Replace(':','\:'))'",
        "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-crf", "21",
        "-c:a", "aac", "-b:a", "192k", "-shortest", $videoPath
    )
    Invoke-FFmpegChecked -Arguments @("-y", "-i", $videoPath, "-vf", "select=eq(n\,60)", "-vframes", "1", "-update", "1", $framePath)
}

$summary = [pscustomobject]@{
    transcript = $textTranscriptPath
    srt = $srtPath
    wav = $wavPath
    mp3 = $mp3Path
    mp4 = $(if (Test-Path $videoPath) { $videoPath } else { $null })
}
$summary | ConvertTo-Json | Set-Content -Path (Join-Path $runDir "build_summary.json") -Encoding UTF8
Write-Output ($summary | ConvertTo-Json -Depth 3)
