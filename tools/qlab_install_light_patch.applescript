-- Create TMPREVIEW (Generic RGB + Intensity) in the front QLab workspace Light Patch.
-- Requires Accessibility permission for "System Events" (System Settings → Privacy).

on run argv
	set instrumentName to "TMPREVIEW"
	if (count of argv) > 0 then set instrumentName to item 1 of argv

	tell application id "com.figure53.QLab.5"
		activate
		tell front workspace
			set edit mode to true
			set show mode to false
		end tell
	end tell
	delay 0.4

	tell application "System Events"
		tell process "QLab"
			set frontmost to true
			my closeStrayDialogs()
			my openWorkspaceSettings()
			delay 0.8
			set settingsWindow to my findSettingsWindow()
			if settingsWindow is missing value then error "Workspace Settings Fenster nicht gefunden"

			if my instrumentExists(instrumentName, settingsWindow) then
				my clickDone(settingsWindow)
				return "exists"
			end if

			my createInstrument(instrumentName, settingsWindow)
			my clickDone(settingsWindow)
			return "created"
		end tell
	end tell
end run

on closeStrayDialogs()
	tell application "System Events"
		tell process "QLab"
			repeat 3 times
				if exists window "Auto-Patch" then
					perform action "AXRaise" of window "Auto-Patch"
					delay 0.1
					key code 53
					delay 0.2
				else
					exit repeat
				end if
			end repeat
		end tell
	end tell
end closeStrayDialogs

on openWorkspaceSettings()
	tell application "System Events"
		tell process "QLab"
			try
				click menu item "Light Patch" of menu "Window" of menu bar 1
			on error
				try
					click menu item "Workspace Settings" of menu "File" of menu bar 1
				on error
					click menu item "Arbeitsbereich-Einstellungen…" of menu "Ablage" of menu bar 1
				end try
			end try
		end tell
	end tell
end openWorkspaceSettings

on findSettingsWindow()
	tell application "System Events"
		tell process "QLab"
			repeat with w in windows
				set wName to name of w as text
				if wName contains "Settings" or wName contains "Einstellungen" then return w
			end repeat
		end tell
	end tell
	return missing value
end findSettingsWindow

on instrumentExists(instrumentName, settingsWindow)
	tell application "System Events"
		tell process "QLab"
			repeat with o in outlines of settingsWindow
				try
					repeat with r in rows of o
						try
							set rowText to value of r as text
							if rowText contains instrumentName then return true
						end try
					end repeat
				end try
			end repeat
			repeat with t in tables of settingsWindow
				try
					repeat with r in rows of t
						try
							set rowText to value of r as text
							if rowText contains instrumentName then return true
						end try
					end repeat
				end try
			end repeat
		end tell
	end tell
	return false
end instrumentExists

on createInstrument(instrumentName, settingsWindow)
	tell application "System Events"
		tell process "QLab"
			set ws to settingsWindow
			try
				click button "New Instrument  ⌘N" of ws
			on error
				click button "New Instrument ⌘N" of ws
			end try
			delay 0.4
			set value of text field 1 of ws to instrumentName
			delay 0.2
			my pickRgbDefinition(ws)
			delay 0.2
			try
				click button "Auto-Patch Selected..." of ws
			on error
				click button "Auto-Patch Selected…" of ws
			end try
			delay 0.5
			my confirmAutoPatch(ws)
			delay 0.3
		end tell
	end tell
end createInstrument

on pickRgbDefinition(settingsWindow)
	tell application "System Events"
		tell process "QLab"
			set ws to settingsWindow
			set defButton to missing value
			repeat with b in buttons of ws
				try
					set bName to name of b as text
					if bName is not "missing value" and bName is not in {"New Instrument  ⌘N", "New Instrument ⌘N", "New Group  ⌘G", "Delete Selected  ⌘⌫", "Auto-Patch Selected...", "Auto-Patch Selected…", "Add to Group...", "Done", "Export...", "Fertig"} then
						if bName does not contain "Import" then set defButton to b
					end if
				end try
			end repeat
			if defButton is not missing value then
				click defButton
				delay 0.5
				keystroke "g"
				delay 0.2
				keystroke "Generic"
				delay 0.3
				key code 125
				delay 0.2
				keystroke "RGB with Intensity"
				delay 0.3
				keystroke return
				delay 0.2
			end if
		end tell
	end tell
end pickRgbDefinition

on confirmAutoPatch(settingsWindow)
	tell application "System Events"
		tell process "QLab"
			if exists sheet 1 of settingsWindow then
				keystroke return
				delay 0.3
				return
			end if
			if exists window "Auto-Patch" then
				keystroke return
				delay 0.3
			end if
		end tell
	end tell
end confirmAutoPatch

on clickDone(settingsWindow)
	tell application "System Events"
		tell process "QLab"
			try
				click button "Done" of settingsWindow
			on error
				click button "Fertig" of settingsWindow
			end try
		end tell
	end tell
end clickDone
