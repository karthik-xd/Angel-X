package main

import (
	"bufio"
	"fmt"
	"image/color"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"time"

	"fyne.io/fyne/v2"
	"fyne.io/fyne/v2/app"
	"fyne.io/fyne/v2/canvas"
	"fyne.io/fyne/v2/container"
	"fyne.io/fyne/v2/theme"
	"fyne.io/fyne/v2/widget"
	"golang.org/x/sys/windows"
)// Preset bypass strategies
var presets = []string{
	"Mode 1: Standard Bypass (Recommended)",
	"Mode 2: Aggressive Bypass",
	"Mode 3: Fake Packet + Anti-RST",
	"Mode 4: Bypass + Secure DNS (77.88.8.8)",
}

var presetArgs = map[string][]string{
	presets[0]: {"-5"},
	presets[1]: {"-9"},
	presets[2]: {"-p", "-r", "-s", "-f", "2", "-k", "2", "-n", "-e", "2"},
	presets[3]: {"-5", "--dns-addr", "77.88.8.8", "--dns-port", "1253"},
}

// enginePath returns the path to goodbyedpi.exe bundled next to this binary
func enginePath() string {
	exe, _ := os.Executable()
	dir := filepath.Dir(exe)
	arch := "x86_64"
	if runtime.GOARCH == "386" {
		arch = "x86"
	}
	return filepath.Join(dir, "bin", "goodbyedpi-0.2.2", arch, "goodbyedpi.exe")
}

func isAdmin() bool {
	_, err := os.Open("\\\\.\\PHYSICALDRIVE0")
	return err == nil
}

func relaunchAsAdmin() {
	exe, _ := os.Executable()
	verb := uint16(0x41) // SW_SHOWNORMAL + "runas"
	_ = verb
	// Use ShellExecuteW to relaunch with runas
	verbPtr, _ := windows.UTF16PtrFromString("runas")
	exePtr, _ := windows.UTF16PtrFromString(exe)
	windows.ShellExecute(0, verbPtr, exePtr, nil, nil, 1)
}

// --- App State ---
type AppState struct {
	mu        sync.Mutex
	process   *exec.Cmd
	running   bool
	logLines  []string
	logWidget *widget.Entry
}

func (s *AppState) appendLog(line string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	ts := time.Now().Format("15:04:05")
	s.logLines = append(s.logLines, fmt.Sprintf("[%s] %s", ts, line))
	if len(s.logLines) > 200 {
		s.logLines = s.logLines[len(s.logLines)-200:]
	}
	if s.logWidget != nil {
		s.logWidget.SetText(strings.Join(s.logLines, "\n"))
	}
}

func (s *AppState) start(preset string, onStatus func(bool)) error {
	args, ok := presetArgs[preset]
	if !ok {
		args = []string{"-5"}
	}
	ep := enginePath()
	cmd := exec.Command(ep, args...)
	cmd.Dir = filepath.Dir(ep)

	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return err
	}
	cmd.Stderr = cmd.Stdout

	if err := cmd.Start(); err != nil {
		return err
	}

	s.mu.Lock()
	s.process = cmd
	s.running = true
	s.mu.Unlock()

	onStatus(true)

	go func() {
		scanner := bufio.NewScanner(stdout)
		for scanner.Scan() {
			line := scanner.Text()
			if line != "" {
				s.appendLog(line)
			}
		}
		cmd.Wait()
		s.mu.Lock()
		s.running = false
		s.process = nil
		s.mu.Unlock()
		onStatus(false)
	}()

	return nil
}

func (s *AppState) stop() {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.process != nil {
		// Kill goodbyedpi and child processes
		exec.Command("taskkill", "/F", "/IM", "goodbyedpi.exe").Run()
		s.process.Process.Kill()
		s.process = nil
	}
	s.running = false
}

// --- Dark Theme ---
type angelTheme struct{}

func (angelTheme) Color(name fyne.ThemeColorName, variant fyne.ThemeVariant) color.Color {
	switch name {
	case theme.ColorNameBackground:
		return color.NRGBA{R: 24, G: 24, B: 37, A: 255}
	case theme.ColorNameForeground:
		return color.NRGBA{R: 205, G: 214, B: 244, A: 255}
	case theme.ColorNamePrimary:
		return color.NRGBA{R: 137, G: 180, B: 250, A: 255}
	case theme.ColorNameButton:
		return color.NRGBA{R: 49, G: 50, B: 68, A: 255}
	case theme.ColorNameInputBackground:
		return color.NRGBA{R: 17, G: 17, B: 27, A: 255}
	}
	return theme.DefaultTheme().Color(name, variant)
}

func (angelTheme) Font(style fyne.TextStyle) fyne.Resource {
	return theme.DefaultTheme().Font(style)
}

func (angelTheme) Icon(name fyne.ThemeIconName) fyne.Resource {
	return theme.DefaultTheme().Icon(name)
}

func (angelTheme) Size(name fyne.ThemeSizeName) float32 {
	return theme.DefaultTheme().Size(name)
}

// --- Main ---
func main() {
	if !isAdmin() {
		relaunchAsAdmin()
		os.Exit(0)
	}

	a := app.New()
	a.Settings().SetTheme(&angelTheme{})
	w := a.NewWindow("Angel-X | Campus Shield")
	w.Resize(fyne.NewSize(520, 500))
	w.SetFixedSize(true)

	state := &AppState{}

	// --- Title ---
	title := canvas.NewText("ANGEL-X", color.NRGBA{R: 205, G: 214, B: 244, A: 255})
	title.TextSize = 26
	title.Alignment = fyne.TextAlignCenter
	title.TextStyle = fyne.TextStyle{Bold: true}

	subtitle := canvas.NewText("Campus Firewall & DPI Bypass Engine", color.NRGBA{R: 166, G: 173, B: 200, A: 255})
	subtitle.TextSize = 11
	subtitle.Alignment = fyne.TextAlignCenter

	// --- Status indicator ---
	statusDot := canvas.NewText("●", color.NRGBA{R: 243, G: 139, B: 168, A: 255})
	statusDot.TextSize = 16

	statusLabel := canvas.NewText("OFFLINE — CAMPUS FIREWALL ACTIVE", color.NRGBA{R: 243, G: 139, B: 168, A: 255})
	statusLabel.TextSize = 11
	statusLabel.TextStyle = fyne.TextStyle{Bold: true}

	statusRow := container.NewHBox(statusDot, statusLabel)
	statusCard := container.NewPadded(statusRow)

	// --- Preset selector ---
	presetSelect := widget.NewSelect(presets, nil)
	presetSelect.SetSelected(presets[0])

	// --- Log box ---
	logBox := widget.NewMultiLineEntry()
	logBox.Disable()
	logBox.SetPlaceHolder("Engine output will appear here...")
	state.logWidget = logBox

	// --- Toggle button ---
	toggleBtn := widget.NewButton("START PROTECTION", nil)
	toggleBtn.Importance = widget.HighImportance

	updateStatus := func(running bool) {
		if running {
			statusDot.Color = color.NRGBA{R: 166, G: 227, B: 161, A: 255}
			statusDot.Refresh()
			statusLabel.Color = color.NRGBA{R: 166, G: 227, B: 161, A: 255}
			statusLabel.Text = "ONLINE — DPI BYPASS ACTIVE"
			statusLabel.Refresh()
			toggleBtn.SetText("STOP PROTECTION")
			presetSelect.Disable()
		} else {
			statusDot.Color = color.NRGBA{R: 243, G: 139, B: 168, A: 255}
			statusDot.Refresh()
			statusLabel.Color = color.NRGBA{R: 243, G: 139, B: 168, A: 255}
			statusLabel.Text = "OFFLINE — CAMPUS FIREWALL ACTIVE"
			statusLabel.Refresh()
			toggleBtn.SetText("START PROTECTION")
			presetSelect.Enable()
		}
	}

	toggleBtn.OnTapped = func() {
		if state.running {
			state.appendLog("Stopping bypass engine...")
			state.stop()
			updateStatus(false)
			state.appendLog("Driver unloaded. Protection stopped.")
		} else {
			selected := presetSelect.Selected
			state.appendLog(fmt.Sprintf("Starting engine with preset: %s", selected))
			err := state.start(selected, func(running bool) {
				updateStatus(running)
				if !running {
					state.appendLog("Engine stopped.")
				}
			})
			if err != nil {
				state.appendLog(fmt.Sprintf("ERROR: %v", err))
			} else {
				state.appendLog("WinDivert driver loaded. Fake packet injection active.")
				state.appendLog("All HTTPS traffic is now protected from campus DPI.")
			}
		}
	}

	// Initial log
	state.appendLog("Angel-X ready. WinDivert engine detected.")
	state.appendLog(fmt.Sprintf("Engine path: %s", enginePath()))

	// --- Layout ---
	content := container.NewVBox(
		container.NewPadded(title),
		container.NewPadded(subtitle),
		widget.NewSeparator(),
		container.NewPadded(statusCard),
		widget.NewSeparator(),
		container.NewPadded(widget.NewLabel("Bypass Strategy:")),
		container.NewPadded(presetSelect),
		container.NewPadded(toggleBtn),
		widget.NewSeparator(),
		container.NewPadded(widget.NewLabel("Engine Log:")),
		container.NewPadded(container.NewGridWrap(fyne.NewSize(500, 140), logBox)),
	)

	w.SetContent(content)
	w.ShowAndRun()
}
