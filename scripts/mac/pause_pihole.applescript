-- Pause Pi-hole for 5 minutes (it turns blocking back on by itself).
-- Source of truth: /srv/containers/edq/scripts/mac/pause_pihole.applescript on udragon.
-- Build on a Mac:  osacompile -o "$HOME/Applications/Pause Pi-hole.app" pause_pihole.applescript
-- Runs the command on udragon over SSH (key auth, no password). Tries the LAN name
-- first, then the Tailscale name so it also works away from the office.
on run
	set pauseCmd to "docker exec pihole pihole disable 5m"
	set sshBase to "/usr/bin/ssh -o BatchMode=yes -o ConnectTimeout=5 "
	try
		do shell script sshBase & "udragon " & quoted form of pauseCmd
	on error
		try
			do shell script sshBase & "udragon-ts " & quoted form of pauseCmd
		on error errMsg
			display notification errMsg with title "Pi-hole" subtitle "Could not pause"
			return
		end try
	end try
	display notification "Ad blocking is off for 5 minutes, then it turns back on by itself." with title "Pi-hole paused"
end run
