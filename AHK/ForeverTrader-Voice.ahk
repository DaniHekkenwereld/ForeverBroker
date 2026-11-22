#Requires AutoHotkey v2.0.18+
#SingleInstance Force
Persistent
; ForeverTrader voice bridge (AutoHotkey v2). No memory reading, no blind clicks.
; Bind WoW with F6 while the game's window is focused.
; F7: test Auction House audio. F8: test mailbox audio. F9: stop this script.
CoordMode "Pixel", "Screen"
SetTimer MonitorForeverTrader, 850
ftWindow := 0
candidate := ""
stableCount := 0
announced := ""
voice := 0
nextSpeakAt := 0
try voice := ComObject("SAPI.SpVoice")
catch {
    voice := 0
    MsgBox "Windows-spraak is niet beschikbaar. De meldingen gebruiken pieptonen.", "ForeverTrader"
}

F6:: {
    global ftWindow, candidate, stableCount, announced
    ftWindow := WinGetID("A")
    candidate := ""
    stableCount := 0
    announced := ""
    TrayTip "ForeverTrader", "WoW-venster gekoppeld. Statusmeldingen actief.", 1
}
F7:: SpeakCue("AH", true)
F8:: SpeakCue("MAIL", true)
F9:: ExitApp

MonitorForeverTrader() {
    global ftWindow, candidate, stableCount, announced, nextSpeakAt
    if !ftWindow || !WinExist("ahk_id " ftWindow) || !WinActive("ahk_id " ftWindow) {
        candidate := ""
        stableCount := 0
        return
    }
    try {
        WinGetClientPos(&x, &y, &w, &h, "ahk_id " ftWindow)
    } catch {
        return
    }
    if w < 300 || h < 240
        return
    ; The addon draws 18x18 solid colors + a second signature square.
    ; Two independent adjacent colors prevent false triggers from game scenery.
    state := FindCue(x, y, w, h, 0xFF2954, 0x660021)
    if !state
        state := FindCue(x, y, w, h, 0x12D98C, 0x05401A)
    if state != candidate {
        candidate := state
        stableCount := 1
    } else {
        stableCount += 1
    }
    if stableCount < 2 || state == announced
        return
    ; Avoid announcing an unknown/no-active cue.
    if state == "" {
        announced := ""
        return
    }
    if A_TickCount < nextSpeakAt
        return
    announced := state
    nextSpeakAt := A_TickCount + 15000
    SpeakCue(state)
}

FindCue(x, y, w, h, primary, secondary) {
    ; Look for the status marker anywhere in the visible game window. The
    ; neighboring 18x18 signature provides a second independent check.
    left := x, top := y, right := x+w-1, bottom := y+h-1
    loop 12 {
        try {
            found := PixelSearch(&px, &py, left, top, right, bottom, primary, 10)
        } catch {
            return ""
        }
        if !found
            return ""
        if px+28 <= right {
            try {
                c := PixelGetColor(px+28, py)
            } catch {
                c := 0
            }
            if ColorNear(c, secondary, 12)
                return primary == 0xFF2954 ? "MAIL" : "AH"
        }
        ; Ignore an accidental lookalike pixel and keep searching to the right.
        left := px+1
        if left >= right
            break
    }
    return ""
}
ColorNear(a, b, tolerance) {
    ar := (a >> 16) & 255, ag := (a >> 8) & 255, ab := a & 255
    br := (b >> 16) & 255, bg := (b >> 8) & 255, bb := b & 255
    return Abs(ar-br) <= tolerance && Abs(ag-bg) <= tolerance && Abs(ab-bb) <= tolerance
}
SpeakCue(kind, test := false) {
    global voice
    if kind == "AH" {
        msg := "Loop naar het Auction House"
        hz := 840
    } else if kind == "MAIL" {
        msg := "Loop naar de mailbox"
        hz := 520
    } else return
    try {
        if voice
            voice.Speak(msg, 3) ; async + purge previous speech
        else
            SoundBeep(hz, 220)
    } catch {
        SoundBeep(hz, 220)
    }
    if test
        TrayTip "ForeverTrader", "Testmelding: " msg, 1
}
